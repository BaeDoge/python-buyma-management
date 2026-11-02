from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from playwright.async_api import async_playwright

from .browser import launch_chrome
from .buyma_api import BuymaClient
from .google_sheets import GoogleSheetClient
from .pricing import decide
from .public_products import PublicProductCollector



def collect_sheet_urls(sheets, settings, limit: int | None = None) -> list[str]:
    """Read unique comparison URLs directly from the configured Google Sheet."""
    df = sheets.read_df(settings.google_price_sheet)
    if df.empty:
        return []
    if settings.google_url_column not in df.columns:
        raise ValueError(f"Google Sheet에 {settings.google_url_column} 컬럼이 없습니다.")
    rows: list[str] = []
    seen_urls: set[str] = set()
    for raw_url in df[settings.google_url_column].tolist():
        if pd.isna(raw_url):
            continue
        url = str(raw_url).strip()
        if not url:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        rows.append(url)
    return rows if limit is None else rows[:limit]


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
    expected_new_price: int | None = None,
) -> None:
    delta = settings.price_delta if price_delta is None else price_delta
    maximum = settings.max_change if max_change is None else max_change

    sheets = GoogleSheetClient(
        settings.google_service_account,
        settings.google_scopes,
        settings.google_sheet_url,
    )
    # 단일/전체 모두 Google Sheet의 URL을 기준으로 공개 상품을 실시간 조회한다.
    # 상품 ID나 API payload 사전 수집 파일은 가격 변경의 선행 조건이 아니다.
    rows = collect_sheet_urls(sheets, settings, limit)
    if not rows:
        logger.info("Google Sheet URL 컬럼에 처리할 URL이 없습니다.")
        return []

    api_client = None
    if apply:
        if not settings.buyma_tokens.exists():
            raise FileNotFoundError(
                f"BUYMA OAuth token이 없습니다: {settings.buyma_tokens}. "
                "OAuth를 완료하고 tokens.json을 준비하세요."
            )
        api_client = BuymaClient(settings.buyma_tokens, settings.buyma_base_url)
        api_client.validate_token_file()

    collector = PublicProductCollector(settings, logger)

    results: list[dict[str, Any]] = []
    pending_updates: list[dict[str, Any]] = []
    changed = skipped = already_lowest = no_own = 0

    async with async_playwright() as playwright:
        page, context, browser = await launch_chrome(
            playwright,
            settings.chrome_paths,
            settings.headless,
            settings.slow_mo,
        )

        try:
            # 실제 변경 모드에서만 BUYMA 로그인 세션을 준비한다.
            # 공개 경쟁가 수집 및 DRY RUN에는 판매자 로그인이 필요하지 않다.
            if apply:
                from payload_migration import login_once
                if not await login_once(page, settings, logger):
                    raise RuntimeError("BUYMA 판매자 로그인 검증에 실패하여 가격 변경을 중단했습니다.")

            if not rows:
                logger.warning("Google Sheet URL 컬럼에 처리할 URL이 없습니다.")

            target_found = False
            for row_index, url in enumerate(rows, start=1):
                logger.info(
                    "[%s/%s] URL%s: %s",
                    row_index,
                    len(rows),
                    " (단일 상품 검색)" if target_product_id else "",
                    url,
                )

                try:
                    if not await collector.open_public(page, url):
                        logger.warning("  공개 페이지 접속 실패. 다음 URL로 넘어갑니다.")
                        if not target_product_id:
                            results.append({
                                "URL": url,
                                "적용 여부": False,
                                "비고": "공개 페이지 접속 실패",
                            })
                            skipped += 1
                        continue
                    products = await collector.collect(page)
                except Exception as exc:
                    logger.warning("  공개 페이지 처리 실패. 다음 URL로 넘어갑니다: %s", exc)
                    if not target_product_id:
                        results.append({
                            "URL": url,
                            "적용 여부": False,
                            "비고": f"공개 페이지 처리 실패: {exc}",
                        })
                        skipped += 1
                    continue

                valid = [p for p in products if p.price is not None]
                logger.info(
                    "  상품 %s개 / BestShip 후보 %s개",
                    len(valid),
                    sum(collector.is_own_seller(p) for p in valid),
                )

                if not valid:
                    if not target_product_id:
                        results.append({"URL": url, "적용 여부": False, "비고": "상품 없음"})
                        skipped += 1
                    continue

                if target_product_id:
                    # 지정 ID가 공개 카드에 나타났는지를 먼저 확인한다.
                    # 판매자 판별이 실패해도 다른 492개 URL을 계속 뒤지지 않도록 한다.
                    matched = [
                        p for p in valid
                        if str(p.product_id or "") == str(target_product_id)
                    ]
                    if not matched:
                        continue
                    target_found = True
                    own_products = [p for p in matched if collector.is_own_seller(p)]
                    if not own_products:
                        results.append({
                            "URL": url,
                            "상품ID": target_product_id,
                            "적용 여부": False,
                            "비고": (
                                "상품 ID는 찾았지만 BestShip 판매자 상품으로 확인되지 않아 "
                                "안전상 변경하지 않았습니다."
                            ),
                        })
                        logger.warning(
                            "상품 ID %s는 찾았지만 BestShip 판매자 확인 실패. 여기서 검색을 종료합니다.",
                            target_product_id,
                        )
                        break
                else:
                    own_products = [p for p in valid if collector.is_own_seller(p)]

                competitor_prices = [
                    p.price for p in valid if not collector.is_own_seller(p)
                ]

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
                        "상품ID": target_product_id or "",
                        "적용 여부": False,
                        "비고": "경쟁 판매자 없음",
                    })
                    skipped += 1
                    if target_product_id:
                        break
                    continue

                min_shop = min(competitor_prices)

                for own in own_products:
                    display_price = int(own.price)
                    product_id = str(own.product_id or "")
                    result = {
                        "URL": url,
                        "상품명": own.name,
                        "상품ID": own.product_id,
                        "판매자": own.seller_name,
                        "판매자ID": own.seller_id,
                        "현재가": display_price,
                        "화면가": display_price,
                        "商品価格": None,
                        "최저가": min_shop,
                        "신규가": None,
                        "가격 차이": None,
                        "타임세일/할인": "N",
                        "적용 여부": False,
                        "처리상태": "SKIPPED",
                        "비고": "",
                        "request_uid": None,
                        "request_received_at": None,
                        "원본 데이터 조회": "",
                    }

                    if not product_id:
                        result["비고"] = "공개 카드에서 상품 ID 확인 실패"
                        results.append(result)
                        skipped += 1
                        continue

                    live_product = None
                    special_price = bool(own.is_timesale)
                    current = display_price

                    # 실제 적용 모드에서는 판매자 원본의 price(商品価格)를 읽는다.
                    # 공개 페이지의 할인 표시 가격은 가격 변경 기준으로 사용하지 않는다.
                    if apply:
                        try:
                            from payload_migration import capture_payload
                            live_data = await capture_payload(page, product_id, settings, logger)
                            if live_data.get("auth_lost"):
                                raise RuntimeError("BUYMA 로그인 세션이 만료되었습니다. 가격 변경을 중단합니다.")
                            if isinstance(live_data.get("product"), dict):
                                live_product = live_data["product"]
                                missing_fields = []
                            elif isinstance(live_data.get("source_product_data"), dict):
                                from buyma_price_competitor.payload_mapper import convert_source_product
                                live_product, missing_fields = convert_source_product(
                                    live_data["source_product_data"], product_id
                                )
                            else:
                                raise RuntimeError(
                                    "판매자 페이지에서 최신 상품 원본 데이터를 가져오지 못했습니다. "
                                    f"URL={live_data.get('url', page.url)}"
                                )

                            if missing_fields:
                                raise RuntimeError(
                                    "최신 원본 데이터의 API 변환 필드가 부족합니다: "
                                    + ", ".join(missing_fields)
                                )
                            if str(live_product.get("id")) != product_id:
                                raise RuntimeError(
                                    f"최신 payload 상품 ID 불일치: {live_product.get('id')} != {product_id}"
                                )
                            source_price = int(live_product.get("price") or 0)
                            if source_price <= 0:
                                raise RuntimeError(
                                    f"판매자 원본 商品価格가 올바르지 않습니다: {live_product.get('price')!r}"
                                )

                            result["商品価格"] = source_price
                            special_price = special_price or source_price != display_price
                            current = source_price
                            result["원본 데이터 조회"] = "실시간 商品価格 및 API 필수 필드 검증 완료"
                        except Exception as exc:
                            result["비고"] = f"BUYMA 원본 상품 조회/검증 실패: {exc}"
                            result["처리상태"] = "SOURCE_VALIDATION_FAILED"
                            results.append(result)
                            skipped += 1
                            logger.exception("  원본 상품 검증 실패: %s", product_id)
                            continue
                    elif special_price:
                        # 미리보기에서는 할인 원본가를 조회하지 않으므로 안전하게 제외한다.
                        result["비고"] = (
                            "타임세일 표시 상품: 실제 商品価格 확인은 전체 변경 실행 시 수행"
                        )
                        result["처리상태"] = "SKIPPED_TIMESALE_PREVIEW"
                        results.append(result)
                        skipped += 1
                        continue

                    result["현재가"] = current
                    result["타임세일/할인"] = "Y" if special_price else "N"

                    if special_price and not settings.allow_timesale_price_update:
                        result["비고"] = (
                            "BUYMA 할인/타임세일로 화면가와 商品価格가 다르거나 타임세일 표시가 있어 제외 "
                            "(.env BUYMA_ALLOW_TIMESALE_PRICE_UPDATE=false)"
                        )
                        result["처리상태"] = "SKIPPED_TIMESALE"
                        results.append(result)
                        skipped += 1
                        logger.info(
                            "  %s | BUYMA 할인/타임세일 상품 제외: 화면가 %s / 商品価格 %s",
                            product_id, f"{display_price:,}",
                            f"{current:,}" if apply else "-",
                        )
                        continue

                    decision = decide(current, min_shop, delta, maximum)
                    result["신규가"] = decision.new_price
                    result["가격 차이"] = decision.change
                    result["비고"] = decision.reason

                    logger.info(
                        "  %s | 商品価格 %s / 화면가 %s / 경쟁최저 %s / 신규 %s / %s",
                        product_id,
                        f"{current:,}",
                        f"{display_price:,}",
                        f"{min_shop:,}",
                        f"{decision.new_price:,}" if decision.new_price else "-",
                        decision.reason,
                    )

                    if decision.reason == "이미 최저가":
                        result["적용 여부"] = None
                        result["처리상태"] = "ALREADY_LOWEST"
                        already_lowest += 1
                        results.append(result)
                        continue

                    if decision.new_price is None:
                        result["처리상태"] = "SKIPPED_PRICE_RULE"
                        skipped += 1
                        results.append(result)
                        continue

                    if apply and expected_new_price is not None and int(decision.new_price) != int(expected_new_price):
                        result["비고"] = (
                            f"미리보기 가격과 달라 요청 중단: 미리보기={expected_new_price:,}, "
                            f"현재 계산={decision.new_price:,}"
                        )
                        result["처리상태"] = "SKIPPED_PREVIEW_MISMATCH"
                        skipped += 1
                        results.append(result)
                        logger.warning(
                            "상품 %s 가격이 미리보기 이후 변경되어 API 요청을 중단했습니다.",
                            product_id,
                        )
                        continue

                    if not apply:
                        result["비고"] = f"DRY RUN / {decision.reason}"
                        result["처리상태"] = "PREVIEW_ONLY"
                        results.append(result)
                        continue

                    api_client.validate_payload(
                        {"product": live_product}, expected_product_id=product_id
                    )

                    if special_price:
                        result["처리상태"] = "WAITING_TIMESALE_CONFIRMATION"
                        result["비고"] = (
                            "BUYMA 할인/타임세일 예외 변경 후보: 전체 상품 조회 완료 후 확인 대기"
                        )
                        pending_updates.append({
                            "result": result,
                            "product": live_product,
                            "new_price": int(decision.new_price),
                            "product_id": product_id,
                            "current_price": current,
                        })
                        results.append(result)
                        logger.info(
                            "  %s | 예외 변경 후보로 보류: %s -> %s",
                            product_id, f"{current:,}", f"{decision.new_price:,}",
                        )
                        continue

                    try:
                        api_response = api_client.update_price(
                            {"product": live_product},
                            decision.new_price,
                            expected_product_id=product_id,
                        )
                        request_uid = api_response.get("request_uid")
                        request_received_at = api_response.get("request_received_at")
                        result["적용 여부"] = True
                        result["처리상태"] = "API_ACCEPTED"
                        result["비고"] = (
                            f"BUYMA API 요청 접수: {current:,} -> {decision.new_price:,}; "
                            f"request_uid={request_uid or '응답에 없음'} "
                            "(비동기 반영 완료 여부는 BUYMA에서 확인 필요)"
                        )
                        result["request_uid"] = request_uid
                        result["request_received_at"] = request_received_at
                        changed += 1
                        logger.info(
                            "  BUYMA API 요청 접수: 상품 %s / 가격 %s / request_uid=%s",
                            product_id, decision.new_price, request_uid,
                        )
                    except Exception as exc:
                        result["비고"] = f"BUYMA API 가격 변경 오류: {exc}"
                        result["처리상태"] = "API_FAILED"
                        skipped += 1
                        logger.exception("  API 가격 변경 실패: %s", product_id)

                    results.append(result)

                # 단일 상품 테스트는 목표 ID가 발견된 URL 하나만 처리하고 즉시 종료한다.
                if target_product_id:
                    logger.info("단일 상품 %s 처리 완료. 추가 URL은 조회하지 않습니다.", target_product_id)
                    break

            if target_product_id and not target_found:
                results.append({
                    "상품ID": target_product_id,
                    "적용 여부": False,
                    "비고": (
                        f"Google Sheets의 {len(rows)}개 URL을 확인했지만 "
                        "해당 상품 ID를 찾지 못했습니다."
                    ),
                })
                logger.warning(
                    "단일 상품 %s를 %s개 URL에서 찾지 못했습니다.",
                    target_product_id,
                    len(rows),
                )

        finally:
            await browser.close()

    if pending_updates:
        print("\\n[타임세일/할인 예외 변경 후보]")
        print(
            f"전체 {len(rows)}개 URL 조회 완료. "
            f"예외 변경 후보 {len(pending_updates)}개를 확인해 주세요."
        )
        for index, item in enumerate(pending_updates, start=1):
            row = item["result"]
            print(
                f"{index}. 상품 {item['product_id']} | "
                f"화면가 {row.get('화면가'):,}엔 | "
                f"商品価格 {item['current_price']:,}엔 | "
                f"경쟁최저 {row.get('최저가'):,}엔 | "
                f"변경 예정 {item['new_price']:,}엔"
            )
        print(
            "\\n주의: 예외 변경을 승인하면 BUYMA 할인/타임세일 가격이 종료되거나 "
            "변경될 수 있습니다."
        )
        confirmation = input(
            f"위 {len(pending_updates)}개 예외 상품의 가격 변경을 진행할까요? (Y/N): "
        ).strip().lower()
        if confirmation in {"y", "yes"}:
            for item in pending_updates:
                row = item["result"]
                try:
                    response = api_client.update_price(
                        {"product": item["product"]},
                        item["new_price"],
                        expected_product_id=item["product_id"],
                    )
                    request_uid = response.get("request_uid")
                    row["적용 여부"] = True
                    row["처리상태"] = "API_ACCEPTED"
                    row["request_uid"] = request_uid
                    row["request_received_at"] = response.get("request_received_at")
                    row["비고"] = (
                        f"사용자 승인 후 BUYMA API 요청 접수: "
                        f"{item['current_price']:,} -> {item['new_price']:,}; "
                        f"request_uid={request_uid or '응답에 없음'} "
                        "(비동기 반영 완료 여부는 BUYMA에서 확인 필요)"
                    )
                    changed += 1
                    logger.info(
                        "타임세일/할인 예외 API 요청 접수: 상품 %s / 가격 %s / request_uid=%s",
                        item["product_id"], item["new_price"], request_uid,
                    )
                except Exception as exc:
                    row["처리상태"] = "API_FAILED"
                    row["비고"] = f"사용자 승인 후 BUYMA API 가격 변경 오류: {exc}"
                    skipped += 1
                    logger.exception("예외 상품 API 가격 변경 실패: %s", item["product_id"])
        else:
            for item in pending_updates:
                item["result"]["처리상태"] = "CANCELLED_BY_USER"
                item["result"]["비고"] = "전체 조회 후 예외 변경 확인 단계에서 사용자가 취소했습니다."
                skipped += 1
            logger.info("타임세일/할인 예외 변경 %s건을 사용자가 취소했습니다.", len(pending_updates))

    report_path = await write_results(settings, sheets, results, changed, already_lowest, no_own)
    logger.info("CSV 결과 저장: %s", report_path)
    logger.info("Google Sheets 결과 탭 갱신: %s", settings.google_api_result_sheet)

    logger.info(
        "=== 완료 | API 요청 접수 %s / 이미 최저 %s / BestShip 없음 %s / 스킵 %s ===",
        changed,
        already_lowest,
        no_own,
        skipped,
    )
    return results


async def write_results(settings, sheets, results, changed, already_lowest, no_own):
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = settings.reports_dir / f"price_competition_{stamp}.csv"
    pd.DataFrame(results).to_csv(report_path, index=False, encoding="utf-8-sig")

    if results:
        history = pd.DataFrame(results)
        # 실행별 최종 결과는 전용 탭에 덮어쓰고, 기존 이력 탭에는 누적한다.
        sheets.replace_df(settings.google_api_result_sheet, history)
        sheets.append_df(settings.google_history_sheet, history)

    return report_path
