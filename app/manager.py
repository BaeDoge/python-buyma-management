"""사용자용 단일 메뉴 진입점.

기본 작업은 DRY RUN이며, 실제 BUYMA 상품 변경은 준비된 payload와
사용자의 명시적 확인이 모두 있어야만 실행한다.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "app" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from buyma_price_competitor.buyma_api import BuymaClient  # noqa: E402
from buyma_price_competitor.config import Settings  # noqa: E402
from buyma_price_competitor.logging_utils import setup_logging  # noqa: E402
from buyma_price_competitor.payload_store import load  # noqa: E402
from buyma_price_competitor.runner import run_price_competition  # noqa: E402


def ask_positive_int(label: str, default: int) -> int:
    while True:
        raw = input(f"{label} [기본값 {default:,}]: ").strip()
        if not raw:
            value = default
        else:
            try:
                value = int(raw.replace(",", ""))
            except ValueError:
                print("숫자로 입력해 주세요.")
                continue
        if value < 1:
            print("1 이상의 금액을 입력해 주세요.")
            continue
        return value


def count_valid_payloads(settings: Settings) -> tuple[int, int]:
    """Return (valid payload count, total entries); does not make API requests."""
    if not settings.product_payloads.exists():
        return 0, 0
    try:
        payloads = load(settings.product_payloads)
    except Exception as exc:
        raise RuntimeError(
            f"상품 데이터 파일을 읽을 수 없습니다: {settings.product_payloads} ({type(exc).__name__})"
        ) from exc

    client = BuymaClient(settings.buyma_tokens, settings.buyma_base_url)
    valid = 0
    for product_id, entry in payloads.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("product"), dict):
            continue
        try:
            client.validate_payload(
                {"product": entry["product"]},
                expected_product_id=str(product_id),
            )
        except (ValueError, TypeError):
            continue
        valid += 1
    return valid, len(payloads)


def run_comparison(settings: Settings, logger, *, apply: bool, delta: int, max_change: int) -> None:
    logger.info(
        "=== BUYMA 가격 경쟁 시작: %s | delta=%s | max_change=%s ===",
        "APPLY" if apply else "DRY RUN",
        delta,
        max_change,
    )
    asyncio.run(
        run_price_competition(
            settings,
            logger,
            apply=apply,
            price_delta=delta,
            max_change=max_change,
        )
    )


def main() -> int:
    try:
        settings = Settings.load()
        logger = setup_logging(settings.logs_dir)
    except Exception as exc:
        print(f"초기 설정을 읽지 못했습니다: {exc}")
        print("config.example.yaml을 config.yaml로 복사한 뒤 설정을 확인하세요.")
        input("Enter를 누르면 종료합니다.")
        return 2

    while True:
        print("\n" + "=" * 62)
        print("BUYMA 최저가 관리")
        print(f"구글 시트: {settings.google_price_sheet} / URL 컬럼: {settings.google_url_column}")
        print("=" * 62)
        print("1. 가격 비교 및 결과 확인 (DRY RUN, 실제 가격 변경 없음)")
        print("2. 가격 비교 후 조건에 맞는 상품 가격 변경 (BUYMA API)")
        print("3. 연결 복구 / 선택적 상품 데이터 준비")
        print("0. 종료")
        choice = input("선택: ").strip()

        if choice == "0":
            return 0
        if choice == "3":
            print("\\n연결 복구와 선택적 데이터 준비 도구를 엽니다.")
            print("평소 가격 비교에는 이 메뉴를 실행할 필요가 없습니다.")
            subprocess.run([sys.executable, str(ROOT / "app" / "setup_once.py")], cwd=ROOT, check=False)
            continue
        if choice not in {"1", "2"}:
            print("1, 2, 3 또는 0을 선택해 주세요.")
            continue

        apply = choice == "2"
        if apply:
            print("\n[주의] 이 모드는 BUYMA 상품 가격 변경 API 요청을 실제로 보냅니다.")
            print("API 접수 후 반영까지 시간이 걸릴 수 있으며, 요청 접수는 반영 완료를 뜻하지 않습니다.")
            try:
                if not settings.buyma_tokens.exists():
                    print(f"OAuth 토큰 파일이 없습니다: {settings.buyma_tokens}")
                    print("먼저 OAuth 초기 연결을 진행하세요.")
                    input("Enter를 누르면 메뉴로 돌아갑니다.")
                    continue
                token_client = BuymaClient(settings.buyma_tokens, settings.buyma_base_url)
                token_client.validate_token_file()
                valid_count, total_count = count_valid_payloads(settings)
            except Exception as exc:
                print(f"실제 적용 사전 점검 실패: {exc}")
                input("Enter를 누르면 메뉴로 돌아갑니다.")
                continue
            if valid_count == 0:
                print("유효한 전체 상품 payload가 없습니다. 실제 가격 변경을 중단했습니다.")
                print("data/buyma_products.json에 BUYMA API 필수 필드를 갖춘 product 객체가 필요합니다.")
                input("Enter를 누르면 메뉴로 돌아갑니다.")
                continue
            print(f"유효한 수정용 payload: {valid_count:,} / 저장 항목 {total_count:,}")
            print("payload가 없는 상품은 가격 변경 대상에서 자동 제외됩니다.")

        delta = ask_positive_int("경쟁 최저가보다 낮출 금액(원)", settings.price_delta)
        max_change = ask_positive_int("허용할 최대 인하 폭(원)", settings.max_change)

        if apply:
            confirmation = input(
                f"실제 API 요청을 진행하려면 APPLY-{delta}-{max_change} 를 정확히 입력하세요: "
            ).strip()
            if confirmation != f"APPLY-{delta}-{max_change}":
                print("확인이 일치하지 않아 실제 변경을 취소했습니다.")
                continue

        try:
            run_comparison(
                settings,
                logger,
                apply=apply,
                delta=delta,
                max_change=max_change,
            )
            print("\n작업이 끝났습니다. logs/와 reports/에서 상세 결과를 확인하세요.")
        except KeyboardInterrupt:
            print("\n사용자가 실행을 중단했습니다.")
        except Exception as exc:
            logger.exception("가격 비교 실행 실패")
            print(f"실행 실패: {type(exc).__name__}: {exc}")
        input("Enter를 누르면 메뉴로 돌아갑니다.")


if __name__ == "__main__":
    raise SystemExit(main())
