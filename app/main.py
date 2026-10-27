import argparse
import asyncio

from buyma_price_competitor.config import Settings
from buyma_price_competitor.logging_utils import setup_logging
from buyma_price_competitor.runner import run_price_competition


def main():
    parser = argparse.ArgumentParser(
        description="BUYMA 가격 경쟁 자동화"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="BUYMA Personal Shopper API로 실제 가격 변경. 기본값은 DRY RUN.",
    )
    parser.add_argument("--price-delta", type=int, default=None)
    parser.add_argument("--max-change", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--product-id", default=None, help="이 상품 ID만 비교/변경")
    parser.add_argument("--config", default="config.yaml")

    args = parser.parse_args()

    if args.price_delta is None:
        args.price_delta = int(input("B 입력 - 경쟁 최저가보다 낮게 설정할 금액(원): ").strip())
    if args.max_change is None:
        args.max_change = int(input("A 입력 - 허용할 최대 가격 변경 폭(원): ").strip())

    settings = Settings.load(args.config)
    logger = setup_logging(settings.logs_dir)

    logger.info("=== BUYMA 가격 경쟁 시작: %s ===", "APPLY" if args.apply else "DRY RUN")
    asyncio.run(
        run_price_competition(
            settings,
            logger,
            apply=args.apply,
            price_delta=args.price_delta,
            max_change=args.max_change,
            limit=args.limit,
            target_product_id=args.product_id,
        )
    )


if __name__ == "__main__":
    main()
