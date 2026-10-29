from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from playwright.async_api import async_playwright

from .browser import launch_chrome
from .buyma_api import BuymaClient
from .google_sheets import GoogleSheetClient
from .payload_store import load, save
from .pricing import decide
from .public_products import PublicProductCollector


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _sheet_urls(df: pd.DataFrame, column: str, limit: int | None) -> list[str]:
    """Read the current URL list, ignoring blank and exact duplicate rows."""
    urls: list[str] = []
    seen: set[str] = set()
    for value in df[column].tolist():
        if pd.isna(value):
            continue
        url = str(value).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls[:limit] if limit is not None else urls


async def run_price_competition(
    settings,
    logger,
    *,
    apply: bool = False,
    price_delta: int | None = None,
    max_change: int | None = None,
    limit: int | None = None,
    target_product_id: str | None = None,
) -> None:
    """Compare all current Google Sheet URLs, then process each BESTSHIP product once.

    Competitor prices are read from public BUYMA pages because the public Personal
    Shopper API specification exposes product update requests, not a competitor-price
    search endpoint. Any actual price change is sent only through the official API.
    """
    delta = 10 if price_delta is None else price_delta
    maximum = 100 if max_change is None else max_change

    sheets = GoogleSheetClient(
        settings.google_service_account,
        settings.google_scopes,
        settings.google_sheet_url,
    )
    df = sheets.read_df(settings.google_price_sheet)
    if settings.google_url_column not in df.columns:
        raise ValueError(f"Google Sheet에 {settings.google_url_column} 컬럼이 없습니다.")

    urls = _sheet_urls(df, settings.google_url_column, limit)
    if not urls:
        logger.info("Google Sheet URL 컬럼에 처리할 URL이 없습니다.")
        return

    payloads: dict[str, Any] = {}
    if settings.product_payloads.exists():
        try:
            payloads = load(settings.product_payloads)
        except Exception as exc:
            logger.error("상품 payload 파일을 읽을 수 없습니다: %s", exc)
            if apply:
                raise

    api_client = None
    if apply:
        if not settings.buyma_tokens.exists():
            raise FileNotFoundError(
                f"BUYMA OAuth 토큰이 없습니다: {settings.buyma_tokens}. "
                "연결된 BESTSHIP 토큰 파일을 확인하세요."
            )
        api_client = BuymaClient(settings.buyma_tokens, settings.buyma_base_url)
        api_client.validate_token_file()

    collector = PublicProductCollector(settings, logger)
    # Keyed by BUYMA product ID to ensure one decision and at most one API request
    # per product in a run, even when the same item appears on multiple sheet URLs.
    candidates: dict[str, dict[str, Any]] = {}
    url_results: list[dict[str, Any]] = []

    async with async_playwright() as playwright:
        page, context, browser = await launch_chrome(
            playwright,
            settings.chrome_paths,
            settings.headless,
            settings.slow_mo,
        )
        try:
            for index, url in enumerate(urls, start=1):
                logger.info("[%s/%s] URL: %s", index, len(urls), url)
                if not await collector.open_public(page, url):
                    url_results.append({
                        "URL": url,
                        "상품ID": "",
                        "적용 여부": False,
                        "비고": "공개 페이지 접속 실패",
                    })
                    continue

                products = [
                    product for product in await collector.collect(page)
                    if product.price is not None
                ]
                own_products = [
                    product for product in products
                    if collector.is_own_seller(product)
                    and (target_product_id is None or str(product.product_id) == str(target_product_id))
                ]
                competitor_prices = [
                    int(product.price) for product in products
                    if not collector.is_own_seller(product) and product.price is not None
                ]

                if not own_products:
                    url_results.append({
                        "URL": url,
                        "상품ID": "",
                        "적용 여부": False,
                        "비고": "BESTSHIP 상품이 없습니다.",
                    })
                    logger.warning("  BESTSHIP 상품이 없습니다.")
                    continue

                if not competitor_prices:
                    url_results.append({
                        "URL": url,
                        "상품ID": "",
                        "적용 여부": False,
                        "비고": "비교 가능한 경쟁 매장 가격이 없습니다.",
                    })
                    logger.warning("  비교 가능한 경쟁 매장 가격이 없습니다.")
                    continue

                lowest = min(competitor_prices)
                for own in own_products:
                    if not own.product_id:
                        url_results.append({
                            "URL": url,
                            "상품명": own.name,
                            "상품ID": "",
                            "현재가": own.price,
                            "최저가": lowest,
                            "적용 여부": False,
                            "비고": "BESTSHIP 상품 ID를 확인하지 못했습니다.",
                        })
                        continue

                    pid = str(own.product_id)
                    item = candidates.setdefault(pid, {
                        "상품ID": pid,
                        "상품명": own.name,
                        "판매자": "BestShip",
                        "판매자ID": settings.own_seller_id,
                        "현재가": int(own.price),
                        "관측된 현재가": {int(own.price)},
                        "최저가": lowest,
                        "비교 URL": [],
                        "타임세일": False,
                    })
                    item["비교 URL"].append(url)
                    item["관측된 현재가"].add(int(own.price))
                    item["최저가"] = min(int(item["최저가"]), lowest)
                    item["타임세일"] = bool(item["타임세일"] or own.is_timesale)
                    if not item.get("상품명") and own.name:
                        item["상품명"] = own.name

        finally:
            await browser.close()

    results: list[dict[str, Any]] = list(url_results)
    changed = skipped = already_lowest = 0
    run_time = now_text()
    run_mode = "APPLY" if apply else "DRY RUN"

    for pid, item in candidates.items():
        current = int(item["현재가"])
        lowest = int(item["최저가"])
        urls_for_item = list(dict.fromkeys(item["비교 URL"]))
        result: dict[str, Any] = {
            "실행시각": run_time,
            "실행모드": run_mode,
            "URL": " | ".join(urls_for_item),
            "상품명": item["상품명"],
            "상품ID": pid,
            "판매자": item["판매자"],
            "판매자ID": item["판매자ID"],
            "현재가": current,
            "최저가": lowest,
            "신규가": None,
            "가격 차이": None,
            "적용 여부": False,
            "비고": "",
        }

        # If public pages disagree about the live price, do not make a decision
        # from a possibly stale or inconsistent page snapshot.
        observed_prices = sorted(item["관측된 현재가"])
        if len(observed_prices) > 1:
            result["비고"] = f"같은 상품의 현재가가 URL마다 다름: {observed_prices}; 변경 보류"
            skipped += 1
            results.append(result)
            logger.warning("%s: %s", pid, result["비고"])
            continue

        if item["타임세일"]:
            result["비고"] = "타임 세일 상품은 자동 변경하지 않음"
            skipped += 1
            results.append(result)
            continue

        decision = decide(current, lowest, delta, maximum)
        result["신규가"] = decision.new_price
        result["가격 차이"] = decision.change
        result["비고"] = decision.reason
        logger.info(
            "상품 %s | 현재 %s / 경쟁 최저 %s / 계산 가격 %s / %s",
            pid, f"{current:,}", f"{lowest:,}",
            f"{decision.new_price:,}" if decision.new_price is not None else "-",
            decision.reason,
        )

        if decision.reason == "이미 최저가":
            result["적용 여부"] = None
            already_lowest += 1
            results.append(result)
            continue
        if decision.new_price is None:
            skipped += 1
            results.append(result)
            continue
        if not apply:
            result["비고"] = f"DRY RUN / {decision.reason}"
            results.append(result)
            continue

        try:
            payload_entry = payloads.get(pid)
            stored_product = payload_entry.get("product") if isinstance(payload_entry, dict) else None
            if not isinstance(stored_product, dict):
                raise RuntimeError(
                    "공식 API용 전체 상품 payload가 없습니다. "
                    "source_product_data만 있는 경우 가격 변경에 사용할 수 없습니다."
                )
            if stored_product.get("control") != "publish":
                raise RuntimeError(
                    "상품 payload의 control이 'publish'가 아닙니다. "
                    "공개 상품의 상태를 바꿀 위험이 있어 요청하지 않았습니다."
                )

            api_response = api_client.update_price(
                {"product": stored_product},
                decision.new_price,
                expected_product_id=pid,
            )
            request_uid = api_response.get("request_uid")
            received_at = api_response.get("request_received_at")
            result["적용 여부"] = True
            result["request_uid"] = request_uid
            result["request_received_at"] = received_at
            result["비고"] = (
                f"BUYMA API 요청 접수: {current:,} -> {decision.new_price:,}; "
                f"request_uid={request_uid or '응답에 없음'}; "
                "최종 반영은 웹훅 또는 BUYMA 상품 화면에서 확인 필요"
            )
            payload_entry["last_request_uid"] = request_uid
            payload_entry["last_request_received_at"] = received_at
            payload_entry["last_requested_price"] = decision.new_price
            payload_entry["last_requested_at"] = now_text()
            changed += 1
            logger.info("BUYMA API 요청 접수: %s / request_uid=%s", pid, request_uid)
        except Exception as exc:
            result["비고"] = f"가격 변경 보류/실패: {exc}"
            skipped += 1
            logger.exception("상품 %s API 변경 실패", pid)

        results.append(result)

    if apply and payloads:
        save(settings.product_payloads, payloads)

    report_path = await write_results(settings, sheets, results)
    logger.info(
        "완료 | URL %s개 / BESTSHIP 상품 %s개 / API 요청 접수 %s / 이미 최저 %s / 스킵 %s",
        len(urls), len(candidates), changed, already_lowest, skipped,
    )
    logger.info("CSV 보고서 저장: %s", report_path)


async def write_results(settings, sheets, results: list[dict[str, Any]]):
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = settings.reports_dir / f"bestship_price_run_{stamp}.csv"
    pd.DataFrame(results).to_csv(report_path, index=False, encoding="utf-8-sig")

    if results:
        sheets.append_df(settings.google_history_sheet, pd.DataFrame(results))

    return report_path
