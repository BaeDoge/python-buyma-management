"""Optional maintenance tool: discover BESTSHIP product IDs for payload capture.

중요:
- BUYMA 웹 로그인을 하지 않습니다.
- Google Sheet의 상품 URL을 공개 페이지로 직접 엽니다.
- BESTSHIP (seller ID 12217668)을 공개 DOM에서 찾습니다.
- BestShip의 공개 상품 링크에서 product ID를 추출합니다.
- 로그인 전용 /my/sell/{id}/edit 페이지에는 접근하지 않습니다.

주의:
BUYMA Product API의 publish/draft/suspend 요청은 price만 보내는 방식이 아니라
필수 상품 필드를 함께 요구합니다. 따라서 이 migration은 "상품 ID 발견" 단계입니다.
기존에 저장된 full payload가 있다면 그것은 보존하며, 새 payload를 로그인 없이
생성하려고 하지 않습니다.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from playwright.async_api import async_playwright

from buyma_price_competitor.browser import launch_chrome
from buyma_price_competitor.config import Settings
from buyma_price_competitor.google_sheets import GoogleSheetClient
from buyma_price_competitor.logging_utils import setup_logging
from buyma_price_competitor.payload_store import load, save
from buyma_price_competitor.public_products import PublicProductCollector


def _id_store_path(settings: Settings):
    # 기존 payload 파일을 건드리지 않고 ID 전용 파일을 만든다.
    return settings.product_payloads.with_name("buyma_product_ids.json")


async def main():
    settings = Settings.load()
    logger = setup_logging(settings.logs_dir)

    sheets = GoogleSheetClient(
        settings.google_service_account,
        settings.google_scopes,
        settings.google_sheet_url,
    )

    df = sheets.read_df(settings.google_price_sheet)

    if df.empty:
        logger.info("Google Sheet이 비어 있습니다.")
        return

    id_store_path = _id_store_path(settings)

    if id_store_path.exists():
        try:
            discovered = load(id_store_path)
        except Exception:
            discovered = {}
    else:
        discovered = {}

    # 기존 payload 파일은 삭제/변경하지 않는다.
    existing_payloads = {}
    if settings.product_payloads.exists():
        try:
            existing_payloads = load(settings.product_payloads)
        except Exception:
            existing_payloads = {}

    skipped_existing = 0
    added_new = 0

    async with async_playwright() as p:
        page, context, browser = await launch_chrome(
            p,
            settings.chrome_paths,
            settings.headless,
            settings.slow_mo,
        )

        collector = PublicProductCollector(settings, logger)

        try:
            for index, row in enumerate(df.itertuples(index=False), start=1):
                url = str(getattr(row, settings.google_url_column)).strip()

                logger.info("[%s/%s] %s", index, len(df), url)

                if not url:
                    logger.warning("  상품 URL이 비어 있습니다.")
                    continue

                try:
                    # 로그인 없이 공개 상품 페이지 접근
                    if not await collector.open_public(page, url):
                        logger.warning("  공개 상품 페이지 접속 실패")
                        continue

                    products = await collector.collect(page)

                    if not products:
                        logger.warning("  공개 상품 카드가 없습니다.")
                        continue

                    own_products = [
                        product
                        for product in products
                        if collector.is_own_seller(product)
                    ]

                    if not own_products:
                        logger.warning(
                            "  BestShip 상품이 없습니다. "
                            "seller_id=%s, seller_name=%s",
                            settings.own_seller_id,
                            settings.own_seller_name,
                        )
                        continue

                    saved_count = 0

                    for product in own_products:
                        product_id = product.product_id

                        if not product_id:
                            logger.warning(
                                "  BestShip은 찾았지만 공개 상품 ID를 추출하지 못했습니다. "
                                "seller=%s, name=%s",
                                product.seller_id,
                                product.seller_name,
                            )
                            continue

                        product_id = str(product_id)

                        # Google Sheets may be regenerated frequently. Keep existing
                        # records (payload flags and request history included) unchanged.
                        # The URL is still scanned because it may contain new product IDs.
                        if product_id in discovered:
                            skipped_existing += 1
                            logger.info(
                                "  기존 상품 ID이므로 스킵: %s (저장 정보 유지)",
                                product_id,
                            )
                            continue

                        discovered[product_id] = {
                            "product_id": product_id,
                            "source_url": url,
                            "name": product.name,
                            "price": product.price,
                            "seller_name": product.seller_name,
                            "seller_id": product.seller_id,
                            "is_timesale": product.is_timesale,
                            "discovered_at": datetime.now().isoformat(
                                timespec="seconds"
                            ),
                            # 이미 full payload가 존재하면 연결 관계를 남긴다.
                            "has_full_payload": product_id in existing_payloads,
                        }

                        logger.info(
                            "  BestShip 상품 ID 발견: %s "
                            "(seller_id=%s, price=%s)",
                            product_id,
                            product.seller_id,
                            product.price,
                        )

                        saved_count += 1
                        added_new += 1

                    if saved_count:
                        save(id_store_path, discovered)
                        logger.info(
                            "  신규 상품 ID 저장 완료: %s",
                            id_store_path,
                        )

                except Exception as exc:
                    logger.exception("  URL 처리 실패: %s", exc)

        finally:
            await browser.close()

    logger.info(
        "=== migration 완료 | 신규 ID %d개 / 기존 ID 스킵 %d개 / 누적 ID %d개 ===",
        added_new,
        skipped_existing,
        len(discovered),
    )


if __name__ == "__main__":
    asyncio.run(main())
