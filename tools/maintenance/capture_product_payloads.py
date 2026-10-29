"""BUYMA product source-data collector (one-time migration).

Optional maintenance task. Run from the project root with: uv run python tools/maintenance/capture_product_payloads.py
Requires BUYMA_LOGIN_ID and BUYMA_LOGIN_PASSWORD in .env. The script verifies the
session before processing and stops immediately if a product page redirects to login.
"""
from __future__ import annotations
import asyncio, json, logging, re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright
from buyma_price_competitor.browser import launch_chrome
from buyma_price_competitor.config import Settings
from buyma_price_competitor.logging_utils import setup_logging
from buyma_price_competitor.payload_store import load, save

BASE_URL = "https://www.buyma.com"
# Required fields for a genuine payload accepted by the existing API-update workflow.
REQUIRED_FIELDS = {"control", "name", "comments", "brand_id", "category_id", "price", "available_until", "buying_area_id", "shipping_area_id", "images", "shipping_methods", "options", "variants"}


def id_store_path(settings: Settings) -> Path:
    return settings.product_payloads.with_name("buyma_product_ids.json")


def edit_url(product_id: str) -> str:
    return f"{BASE_URL}/my/sell/{product_id}/edit"


def walk(value: Any, depth: int = 0) -> dict[str, Any] | None:
    """Find a payload that already matches the official API payload schema.

    BUYMA's page data endpoint uses a different schema, so this intentionally
    does not treat its `data` object as an official API payload.
    """
    if depth > 20:
        return None
    if isinstance(value, dict):
        if REQUIRED_FIELDS.issubset(value.keys()):
            return value
        for child in value.values():
            found = walk(child, depth + 1)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = walk(child, depth + 1)
            if found:
                return found
    return None


def unwrap_source_product(value: Any) -> dict[str, Any] | None:
    """Return the product object from /rorapi/sell/products/{id} response."""
    if not isinstance(value, dict):
        return None
    data = value.get("data")
    if isinstance(data, dict) and ("id" in data or "item_images" in data or "price" in data):
        return data
    # Some endpoint versions may return the product object directly.
    if "id" in value and ("item_images" in value or "price" in value):
        return value
    return None


def summarize_source_product(product: dict[str, Any]) -> dict[str, Any]:
    """Create a human-readable inventory of observed fields, not an API payload."""
    brand = product.get("brand")
    purchase_area = product.get("purchase_area")
    shipping_area = product.get("shipping_area")
    return {
        "id": product.get("id"),
        "name": product.get("name"),
        "comment_present": bool(product.get("comment")),
        "category_id": product.get("category_id"),
        "brand": brand if isinstance(brand, dict) else None,
        "price": product.get("price"),
        "period": product.get("period"),
        "purchase_area": purchase_area,
        "shipping_area": shipping_area,
        "item_images_count": len(product.get("item_images", [])) if isinstance(product.get("item_images"), list) else None,
        "shipping_methods_count": len(product.get("shipping_methods", [])) if isinstance(product.get("shipping_methods"), list) else None,
        "colors_count": len(product.get("colors", [])) if isinstance(product.get("colors"), list) else None,
        "sizes_count": len(product.get("sizes", [])) if isinstance(product.get("sizes"), list) else None,
        "colorsizes_present": isinstance(product.get("colorsizes"), list),
        "source_keys": sorted(product.keys()),
        "status": "source_data_only_not_official_api_payload",
    }


def clean_product(product: dict[str, Any], product_id: str) -> dict[str, Any]:
    result = dict(product)
    result["id"] = result.get("id") or int(product_id)
    for key in ("status", "list_price", "updated_at", "created_at"):
        result.pop(key, None)
    return result

def login_redirect(url: str, body: str = "") -> bool:
    path = urlparse(url).path.lower()
    if any(part in path for part in ("/login", "/signin", "/sign_in")):
        return True
    # A login form can be shown at a non-obvious URL too.
    if "/my/sell/" not in path and ("비밀번호" in body or "ログイン" in body or "로그인" in body):
        return "password" in body.lower() or "비밀번호" in body
    return False


async def first_visible(page, selectors: list[str]):
    for selector in selectors:
        try:
            item = page.locator(selector).first
            if await item.is_visible(timeout=700):
                return item
        except Exception:
            continue
    return None


async def verify_session(page, logger: logging.Logger) -> bool:
    try:
        await page.goto(f"{BASE_URL}/my/sell", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1000)
        body = (await page.locator("body").inner_text(timeout=5000))[:5000]
        if login_redirect(page.url, body):
            logger.warning("로그인 세션 검증 실패: %s", page.url)
            return False
        if "/my/" in urlparse(page.url).path and "sell" in urlparse(page.url).path:
            logger.info("로그인 세션 검증 성공: %s", page.url)
            return True
        logger.warning("로그인 여부를 확인할 수 없음: %s", page.url)
    except Exception as exc:
        logger.warning("로그인 세션 검증 오류: %s", exc)
    return False


async def login_once(page, settings: Settings, logger: logging.Logger) -> bool:
    await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
    if await verify_session(page, logger):
        return True
    login_id = settings.env("BUYMA_LOGIN_ID")
    login_pw = settings.env("BUYMA_LOGIN_PASSWORD")
    if not login_id or not login_pw:
        logger.error(".env에 BUYMA_LOGIN_ID와 BUYMA_LOGIN_PASSWORD를 설정하세요.")
        return False
    link = await first_visible(page, ["#js-pc-header-login-link", 'a[href*="login"]', 'a[href*="signin"]'])
    if link:
        try:
            await link.click(timeout=5000)
        except Exception:
            pass
    await page.wait_for_timeout(500)
    id_field = await first_visible(page, ["#txtLoginId", 'input[name="login_id"]', 'input[name="email"]', 'input[autocomplete="username"]', 'input[type="email"]'])
    pw_field = await first_visible(page, ["#txtLoginPass", 'input[name="password"]', 'input[autocomplete="current-password"]', 'input[type="password"]'])
    if not id_field or not pw_field:
        logger.error("로그인 입력란을 찾지 못했습니다. URL=%s", page.url)
        return False
    await id_field.fill(login_id)
    await pw_field.fill(login_pw)
    submit = await first_visible(page, ["#login_do", 'button[type="submit"]', 'input[type="submit"]'])
    if not submit:
        logger.error("로그인 버튼을 찾지 못했습니다. URL=%s", page.url)
        return False
    await submit.click()
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
    except PlaywrightTimeoutError:
        pass
    await page.wait_for_timeout(1500)
    if await verify_session(page, logger):
        return True
    if not settings.headless:
        logger.warning("추가 인증/CAPTCHA가 있다면 브라우저에서 직접 완료한 후 Enter를 누르세요.")
        try:
            await asyncio.to_thread(input, "로그인 완료 후 Enter: ")
        except (EOFError, KeyboardInterrupt):
            return False
        return await verify_session(page, logger)
    return False


async def capture_payload(page, product_id: str, settings: Settings, logger: logging.Logger) -> dict[str, Any]:
    found_products: list[dict[str, Any]] = []
    source_product: dict[str, Any] | None = None
    response_debug: list[dict[str, Any]] = []
    source_endpoint = re.compile(rf"/rorapi/sell/products/{re.escape(str(product_id))}(?:\?|$)")

    async def on_response(response):
        nonlocal source_product
        try:
            content_type = (response.headers.get("content-type") or "").lower()
            if "json" not in content_type:
                return
            # Keep diagnostics compact; the full product JSON is stored separately below.
            is_source_endpoint = bool(source_endpoint.search(response.url))
            data = await response.json()
            candidate = walk(data)
            found_source = unwrap_source_product(data) if is_source_endpoint else None
            response_debug.append({
                "url": response.url,
                "status": response.status,
                "official_payload_found": bool(candidate),
                "source_product_found": bool(found_source),
            })
            if candidate:
                found_products.append(candidate)
            if found_source:
                source_product = found_source
        except Exception as exc:
            response_debug.append({"url": response.url, "response_parse_error": str(exc)[:300]})

    page.on("response", on_response)
    try:
        target = edit_url(product_id)
        logger.info("  편집 페이지: %s", target)
        try:
            await page.goto(target, wait_until="domcontentloaded", timeout=35000)
        except PlaywrightTimeoutError:
            logger.warning("  페이지 로딩 timeout; 상태를 계속 확인합니다.")
        await page.wait_for_timeout(max(2500, settings.page_wait_ms * 2))
        body = ""
        try:
            body = await page.locator("body").inner_text(timeout=5000)
        except Exception:
            pass
        if login_redirect(page.url, body):
            return {"auth_lost": True, "url": page.url, "responses": response_debug}

        # Prefer a genuine payload only when it has every required API field.
        for candidate in reversed(found_products):
            if REQUIRED_FIELDS.issubset(candidate.keys()):
                return {
                    "product": clean_product(candidate, product_id),
                    "responses": response_debug,
                    "source": "response_matching_official_payload_schema",
                }

        # The currently observed BUYMA page endpoint returns {data: {...}, meta: ...}.
        # Store this as source data only; do not mislabel it as an official API payload.
        if source_product:
            return {
                "product": None,
                "source_product_data": source_product,
                "source_summary": summarize_source_product(source_product),
                "url": page.url,
                "responses": response_debug,
            }

        # Last chance: inspect JSON script blocks for a true full payload or source-shaped data.
        try:
            for script in await page.locator("script").all_text_contents():
                if len(script) > 2_000_000:
                    continue
                try:
                    parsed = json.loads(script)
                except Exception:
                    parsed = None
                    match = re.search(r"(\{.*\})", script, re.S)
                    if match:
                        try:
                            parsed = json.loads(match.group(1))
                        except Exception:
                            pass
                candidate = walk(parsed) if parsed is not None else None
                if candidate and REQUIRED_FIELDS.issubset(candidate.keys()):
                    return {"product": clean_product(candidate, product_id), "responses": response_debug, "source": "page_script"}
                source_candidate = unwrap_source_product(parsed)
                if source_candidate:
                    return {
                        "product": None,
                        "source_product_data": source_candidate,
                        "source_summary": summarize_source_product(source_candidate),
                        "url": page.url,
                        "responses": response_debug,
                    }
        except Exception:
            pass
        return {"product": None, "url": page.url, "title": await page.title(), "body_excerpt": body[:1500], "responses": response_debug}
    finally:
        page.remove_listener("response", on_response)


async def main() -> None:
    settings = Settings.load()
    logger = setup_logging(settings.logs_dir)
    ids_path = id_store_path(settings)
    if not ids_path.exists():
        raise FileNotFoundError(f"상품 ID 저장소가 없습니다: {ids_path}\n먼저 uv run migration.py 를 실행하세요.")
    ids = load(ids_path)
    payloads: dict[str, Any] = {}
    if settings.product_payloads.exists():
        try:
            payloads = load(settings.product_payloads)
        except Exception as exc:
            logger.warning("기존 payload 읽기 실패: %s", exc)

    # Distinguish a verified official-shaped payload from source-page data.
    for pid, entry in payloads.items():
        if not isinstance(entry, dict) or not isinstance(ids.get(pid), dict):
            continue
        product = entry.get("product")
        if isinstance(product, dict) and REQUIRED_FIELDS.issubset(product.keys()):
            ids[pid]["has_full_payload"] = True
        if isinstance(entry.get("source_product_data"), dict):
            ids[pid]["has_source_data"] = True

    targets = []
    for pid, info in ids.items():
        if not isinstance(info, dict) or info.get("has_full_payload"):
            continue
        # Only a verified full payload is complete. Source-only records must remain
        # eligible for a deliberate manual retry; they are never used by recurring runs.
        targets.append((str(pid), info))

    logger.info("=== BUYMA source payload migration 시작 ===")
    logger.info("상품 ID %d개 / 공식 payload 미확보 대상 %d개", len(ids), len(targets))
    if not targets:
        save(ids_path, ids)
        logger.info("수집 대상이 없습니다.")
        return

    settings.migration_debug_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        page, context, browser = await launch_chrome(playwright, settings.chrome_paths, settings.headless, settings.slow_mo)
        try:
            if not await login_once(page, settings, logger):
                logger.error("로그인 검증 실패. 작업을 시작하지 않고 중단합니다.")
                return
            for index, (pid, info) in enumerate(targets, 1):
                logger.info("[%d/%d] 상품 ID: %s", index, len(targets), pid)
                result = None
                for attempt in (1, 2):
                    try:
                        result = await capture_payload(page, pid, settings, logger)
                    except Exception as exc:
                        logger.warning("  시도 %d 오류: %s", attempt, exc)
                        result = {"error": str(exc), "url": page.url}
                    if result.get("auth_lost"):
                        logger.error("로그인 세션 만료/리다이렉트 감지: %s. 전체 작업을 중단합니다.", result.get("url"))
                        break
                    if result.get("product") or result.get("source_product_data"):
                        break
                    if attempt == 1:
                        logger.info("  상품 데이터 미발견. 1회 재시도합니다.")
                        await page.wait_for_timeout(1000)
                if result and result.get("auth_lost"):
                    break

                if result and result.get("product"):
                    # Only a payload containing every required field gets full-payload status.
                    product = result["product"]
                    payloads[pid] = {
                        "product": product,
                        "migration_status": "official_payload_shape_detected",
                        "migrated_at": datetime.now().isoformat(timespec="seconds"),
                        "source_url": edit_url(pid),
                        "responses": result.get("responses", []),
                    }
                    ids[pid]["has_full_payload"] = True
                    ids[pid]["payload_migrated_at"] = datetime.now().isoformat(timespec="seconds")
                    logger.info("  공식 payload 형태 저장: %s / 필드 %d개", pid, len(product))
                elif result and isinstance(result.get("source_product_data"), dict):
                    source_data = result["source_product_data"]
                    payloads[pid] = {
                        "source_product_data": source_data,
                        "source_summary": result.get("source_summary", summarize_source_product(source_data)),
                        "migration_status": "source_data_only_official_payload_mapping_incomplete",
                        "migrated_at": datetime.now().isoformat(timespec="seconds"),
                        "source_url": edit_url(pid),
                        "responses": result.get("responses", []),
                    }
                    ids[pid]["has_source_data"] = True
                    # Intentionally do NOT set has_full_payload: required API fields such as
                    # control/options/variants and area IDs have not been safely mapped.
                    raw_path = settings.migration_debug_dir / f"source_product_{pid}.json"
                    raw_path.write_text(json.dumps(source_data, ensure_ascii=False, indent=2), encoding="utf-8")
                    logger.info("  원본 상품 데이터 저장: %s / 필드 %d개 (공식 API payload 아님)", pid, len(source_data))
                else:
                    debug_path = settings.migration_debug_dir / f"payload_{pid}.json"
                    debug_path.write_text(json.dumps(result or {}, ensure_ascii=False, indent=2), encoding="utf-8")
                    try:
                        (settings.migration_debug_dir / f"payload_{pid}.html").write_text(await page.content(), encoding="utf-8")
                    except Exception:
                        pass
                    logger.warning("  상품 데이터 추출 실패: %s (진단 파일: %s)", pid, debug_path)

                # Checkpoint each product so an interruption does not lose progress.
                if result and (result.get("product") or result.get("source_product_data")):
                    save(settings.product_payloads, payloads)
                    save(ids_path, ids)
        finally:
            await browser.close()

    logger.info("=== source payload migration 종료 ===")
    logger.info("공식 payload 확보: %d개", sum(1 for item in ids.values() if isinstance(item, dict) and item.get("has_full_payload")))
    logger.info("원본 source 데이터 확보: %d개", sum(1 for item in ids.values() if isinstance(item, dict) and item.get("has_source_data")))
    logger.info("공식 payload 미완료 상품: %d개", sum(1 for item in ids.values() if isinstance(item, dict) and not item.get("has_full_payload")))

if __name__ == "__main__":
    asyncio.run(main())
