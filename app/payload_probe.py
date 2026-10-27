"""One-product BUYMA response probe. Saves raw JSON from the product edit page for schema analysis.
Run: uv run payload_probe.py --product-id 135914558
"""
from __future__ import annotations
import argparse, asyncio, json, logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright
from buyma_price_competitor.browser import launch_chrome
from buyma_price_competitor.config import Settings
from buyma_price_competitor.logging_utils import setup_logging

BASE_URL = "https://www.buyma.com"

async def first_visible(page, selectors):
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if await loc.is_visible(timeout=700):
                return loc
        except Exception:
            pass
    return None

async def login_redirect(page):
    path = urlparse(page.url).path.lower()
    if any(x in path for x in ("/login", "/signin", "/sign_in")):
        return True
    try:
        body = (await page.locator("body").inner_text(timeout=3000))[:3000]
    except Exception:
        body = ""
    return "/my/sell/" not in path and ("ログイン" in body or "ログイン" in body) and ("password" in body.lower() or "パスワード" in body)

async def verify_session(page, logger):
    try:
        await page.goto(f"{BASE_URL}/my/sell", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(900)
        if await login_redirect(page):
            logger.warning("ログイン未確認: %s", page.url)
            return False
        ok = "/my/" in urlparse(page.url).path and "sell" in urlparse(page.url).path
        logger.info("ログイン確認 %s: %s", "成功" if ok else "不明", page.url)
        return ok
    except Exception as exc:
        logger.warning("ログイン確認エラー: %s", exc)
        return False

async def login_once(page, settings, logger):
    await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
    if await verify_session(page, logger):
        return True
    login_id = settings.env("BUYMA_LOGIN_ID")
    password = settings.env("BUYMA_LOGIN_PASSWORD")
    if not login_id or not password:
        logger.error(".env の BUYMA_LOGIN_ID / BUYMA_LOGIN_PASSWORD を確認してください")
        return False
    link = await first_visible(page, ["#js-pc-header-login-link", 'a[href*="login"]', 'a[href*="signin"]'])
    if link:
        try: await link.click(timeout=5000)
        except Exception: pass
    await page.wait_for_timeout(500)
    id_input = await first_visible(page, ["#txtLoginId", 'input[name="login_id"]', 'input[name="email"]', 'input[autocomplete="username"]', 'input[type="email"]'])
    pw_input = await first_visible(page, ["#txtLoginPass", 'input[name="password"]', 'input[autocomplete="current-password"]', 'input[type="password"]'])
    submit = await first_visible(page, ["#login_do", 'button[type="submit"]', 'input[type="submit"]'])
    if not id_input or not pw_input or not submit:
        logger.error("로그인 폼을 찾을 수 없습니다. URL=%s", page.url)
        return False
    await id_input.fill(login_id)
    await pw_input.fill(password)
    await submit.click()
    try: await page.wait_for_load_state("domcontentloaded", timeout=15000)
    except PlaywrightTimeoutError: pass
    await page.wait_for_timeout(1500)
    return await verify_session(page, logger)

def summarize(value: Any, depth=0):
    """Shape-only summary, omitting values to keep the log compact."""
    if depth >= 4:
        if isinstance(value, dict): return {"type":"object", "keys":list(value.keys())[:80]}
        if isinstance(value, list): return {"type":"array", "length":len(value), "sample_type":type(value[0]).__name__ if value else None}
        return type(value).__name__
    if isinstance(value, dict):
        return {k:summarize(v, depth+1) for k,v in list(value.items())[:100]}
    if isinstance(value, list):
        return {"type":"array", "length":len(value), "sample":summarize(value[0], depth+1) if value else None}
    return {"type":type(value).__name__, "value_preview":str(value)[:80] if isinstance(value,(str,int,float,bool)) or value is None else None}

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-id", default="135914558")
    args = parser.parse_args()
    settings = Settings.load()
    logger = setup_logging(settings.logs_dir)
    debug_dir = settings.migration_debug_dir
    debug_dir.mkdir(parents=True, exist_ok=True)
    pid = str(args.product_id)
    captured = []
    async with async_playwright() as p:
        page, context, browser = await launch_chrome(p, settings.chrome_paths, settings.headless, settings.slow_mo)
        try:
            if not await login_once(page, settings, logger):
                logger.error("로그인 세션을 검증할 수 없어 중단합니다.")
                return
            async def on_response(response):
                url = response.url
                # Product detail and edit initial data endpoints are the most relevant.
                if "/rorapi/sell/products/" not in url and "/rorapi/sell/initial_data" not in url and "/rorapi/sell/shipping_methods" not in url:
                    return
                try:
                    ctype = response.headers.get("content-type", "")
                    raw = await response.text()
                    item = {"url":url,"status":response.status,"content_type":ctype,"body_text":raw[:3_000_000]}
                    try:
                        parsed = json.loads(raw)
                        item["json_shape"] = summarize(parsed)
                    except Exception as exc:
                        item["json_parse_error"] = str(exc)
                    captured.append(item)
                    logger.info("JSON 응답 캡처: status=%s url=%s bytes=%d", response.status, url, len(raw))
                except Exception as exc:
                    logger.warning("응답 캡처 실패: %s (%s)", url, exc)
            page.on("response", on_response)
            target = f"{BASE_URL}/my/sell/{pid}/edit"
            logger.info("상품 편집 페이지 이동: %s", target)
            try: await page.goto(target, wait_until="domcontentloaded", timeout=35000)
            except PlaywrightTimeoutError: logger.warning("페이지 이동 timeout; 응답 수집을 계속합니다")
            await page.wait_for_timeout(max(4000, settings.page_wait_ms * 3))
            if await login_redirect(page):
                logger.error("상품 페이지에서 로그인 리다이렉트 감지: %s", page.url)
            else:
                logger.info("상품 페이지 URL=%s / title=%s", page.url, await page.title())
            # Ensure late async response handlers finish.
            await page.wait_for_timeout(500)
            out = debug_dir / f"response_{pid}.json"
            out.write_text(json.dumps({"product_id":pid,"page_url":page.url,"title":await page.title(),"captured_responses":captured}, ensure_ascii=False, indent=2), encoding="utf-8")
            html_path = debug_dir / f"response_{pid}.html"
            html_path.write_text(await page.content(), encoding="utf-8")
            logger.info("진단 결과 저장: %s (응답 %d개)", out, len(captured))
            logger.info("HTML 저장: %s", html_path)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
