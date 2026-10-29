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
    delta = settings.price_delta if price_delta is None else price_delta
    maximum = settings.max_change if max_change is None else max_change

    sheets = GoogleSheetClient(
        settings.google_service_account,
        settings.google_scopes,
        settings.google_sheet_url,
    )
    df = sheets.read_df(settings.google_price_sheet)
    if df.empty:
        logger.info("Google Sheet에 데이터가 없습니다.")
        return
    if settings.google_url_column not in df.columns:
        raise ValueError(f"Google Sheet에 {settings.google_url_column} 컬럼이 없습니다.")

    # 가격 변경은 BUYMA Personal Shopper API로만 수행한다.
    # 웹 로그인/편집 화면 자동화는 사용하지 않는다.
    payloads: dict[str, Any] = {}
    if settings.product_payloads.exists():
        try:
            payloads = load(settings.product_payloads)
        except Exception as exc:
            logger.warning("API payload 저장소를 읽지 못했습니다: %s", exc)

    api_client = None
    if apply:
        # Fail early instead of scraping hundreds of URLs when credentials are missing.
        if not settings.buyma_tokens.exists():
            raise FileNotFoundError(
                f"BUYMA OAuth token이 없습니다: {settings.buyma_tokens}. "
                "OAuth를 완료하고 tokens.json을 준비하세요."
            )
        api_client = BuymaClient(settings.buyma_tokens, settings.buyma_base_url)
        api_client.validate_token_file()
        if target_product_id:
            entry = payloads.get(str(target_product_id))
            product = entry.get("product") if isinstance(entry, dict) else None
            if not isinstance(product, dict):
                raise RuntimeError(
                    f"상품 {target_product_id}의 공식 API payload가 없습니다: "
                    f"{settings.product_payloads}. "
                    "가격 변경에는 BUYMA Product API 필수 필드를 갖춘 전체 payload가 필요합니다. "
                    "source_product_data만 저장된 경우에는 아직 API 수정에 사용할 수 없습니다."
                )
            api_client.validate_payload({"product": product}, expected_product_id=str(target_product_id))

    collector = PublicProductCollector(settings, logger)

    results: list[dict[str, Any]] = []
    changed = skipped = already_lowest = no_own = 0

    async with async_playwright() as playwright:
        page, context, browser = await launch_chrome(
            playwright,
            settings.chrome_paths,
            settings.headless,
            settings.slow_mo,
        )

        try:
            rows = list(df.itertuples(index=False))
            if limit is not None:
                rows = rows[:limit]

            for row_index, row in enumerate(rows, start=1):
                url = str(getattr(row, settings.google_url_column)).strip()
                logger.info("[%s/%s] URL: %s", row_index, len(rows), url)

                if not await collector.open_public(page, url):
                    results.append({
                        "URL": url,
                        "적용 여부": False,
                        "비고": "공개 페이지 접속 실패",
                    })
                    skipped += 1
                    continue

                products = await collector.collect(page)
                valid = [p for p in products if p.price is not None]

                logger.info(
                    "  상품 %s개 / BestShip 후보 %s개",
                    len(valid),
                    sum(collector.is_own_seller(p) for p in valid),
                )

                if not valid:
                    results.append({"URL": url, "적용 여부": False, "비고": "상품 없음"})
                    skipped += 1
                    continue

                competitor_prices = [
                    p.price for p in valid if not collector.is_own_seller(p)
                ]
                own_products = [p for p in valid if collector.is_own_seller(p)]
                if target_product_id:
                    own_products = [p for p in own_products if str(p.product_id) == str(target_product_id)]

                if not own_products:
                    logger.warning(
                        "  BestShip 상품 없음. 판매자 샘플: %s",
                        [(p.seller_name, p.seller_id) for p in valid[:10]],
                    )
                    results.append({
                        "URL": url,
                        "적용 여부": False,
                        "비고": "BestShip 상품이 없습니다.",
                    })
                    no_own += 1
                    continue

                if not competitor_prices:
                    results.append({
                        "URL": url,
                        "적용 여부": False,
                        "비고": "경쟁 판매자 없음",
                    })
                    skipped += 1
                    continue

                min_shop = min(competitor_prices)

                for own in own_products:
                    current = int(own.price)
                    result = {
                        "URL": url,
                        "상품명": own.name,
                        "상품ID": own.product_id,
                        "판매자": own.seller_name,
                        "판매자ID": own.seller_id,
                        "현재가": current,
                        "최저가": min_shop,
                        "신규가": None,
                        "가격 차이": None,
                        "적용 여부": False,
                        "비고": "",
                    }

                    if own.is_timesale:
                        result["비고"] = "타임 세일"
                        results.append(result)
                        skipped += 1
                        continue

                    if not own.product_id:
                        result["비고"] = "공개 카드에서 상품 ID 확인 실패"
                        results.append(result)
                        skipped += 1
                        continue

                    product_id = str(own.product_id)
                    decision = decide(current, min_shop, delta, maximum)
                    result["신규가"] = decision.new_price
                    result["가격 차이"] = decision.change
                    result["비고"] = decision.reason

                    logger.info(
                        "  %s | 현재 %s / 경쟁최저 %s / 신규 %s / %s",
                        product_id,
                        f"{current:,}",
                        f"{min_shop:,}",
                        f"{decision.new_price:,}" if decision.new_price else "-",
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

                    # DRY RUN에서는 API 요청을 보내지 않는다.
                    if not apply:
                        result["비고"] = f"DRY RUN / {decision.reason}"
                        results.append(result)
                        continue

                    try:
                        payload_entry = payloads.get(product_id)
                        stored_product = payload_entry.get("product") if isinstance(payload_entry, dict) else None
                        if not isinstance(stored_product, dict):
                            raise RuntimeError(
                                f"공식 API payload가 없습니다 ({settings.product_payloads}). "
                                "source_product_data는 API 수정용 payload가 아닙니다."
                            )

                        api_response = api_client.update_price(
                            {"product": stored_product},
                            decision.new_price,
                            expected_product_id=product_id,
                        )
                        request_uid = api_response.get("request_uid")
                        request_received_at = api_response.get("request_received_at")
                        result["적용 여부"] = True
                        result["비고"] = (
                            f"BUYMA API 요청 접수: {current:,} -> {decision.new_price:,}; "
                            f"request_uid={request_uid or '응답에 없음'} "
                            "(비동기 반영 완료 여부는 BUYMA에서 확인 필요)"
                        )
                        result["request_uid"] = request_uid
                        result["request_received_at"] = request_received_at
                        # Save the request metadata, but do not mutate the stored product price:
                        # API acceptance is asynchronous and does not prove the listing updated.
                        payload_entry["last_request_uid"] = request_uid
                        payload_entry["last_request_received_at"] = request_received_at
                        payload_entry["last_requested_price"] = decision.new_price
                        payload_entry["last_requested_at"] = now_text()
                        changed += 1
                        logger.info(
                            "  BUYMA API 요청 접수: 상품 %s / 가격 %s / request_uid=%s",
                            product_id, decision.new_price, request_uid,
                        )
                    except Exception as exc:
                        result["비고"] = f"BUYMA API 가격 변경 오류: {exc}"
                        skipped += 1
                        logger.exception("  API 가격 변경 실패: %s", product_id)

                    results.append(result)

        finally:
            await browser.close()

    if apply and payloads:
        save(settings.product_payloads, payloads)

    await write_results(settings, sheets, results, changed, already_lowest, no_own)

    logger.info(
        "=== 완료 | API 요청 접수 %s / 이미 최저 %s / BestShip 없음 %s / 스킵 %s ===",
        changed,
        already_lowest,
        no_own,
        skipped,
    )


async def write_results(settings, sheets, results, changed, already_lowest, no_own):
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = settings.reports_dir / f"price_competition_{stamp}.csv"
    pd.DataFrame(results).to_csv(report_path, index=False, encoding="utf-8-sig")

    if results:
        history = pd.DataFrame(results)
        sheets.replace_df(settings.google_history_sheet, history)

    return report_path
