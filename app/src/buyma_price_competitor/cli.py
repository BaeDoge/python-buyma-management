"""Single-run CLI for the one BESTSHIP store."""
from __future__ import annotations
import asyncio
from typing import Any

from .buyma_api import BuymaClient
from .config import Settings
from .logging_utils import setup_logging
from .payload_store import load
from .runner import run_price_competition


def ask_amount(label: str, default: int) -> int:
    while True:
        raw = input(f"{label} [기본 {default:,}원]: ").strip()
        try:
            value = default if not raw else int(raw.replace(",", ""))
        except ValueError:
            print("숫자로 입력해 주세요.")
            continue
        if value <= 0:
            print("1원 이상의 금액을 입력해 주세요.")
            continue
        return value


def valid_payload_count(settings: Settings) -> tuple[int, int]:
    path = settings.product_payloads
    if not path.exists():
        return 0, 0
    payloads: dict[str, Any] = load(path)
    client = BuymaClient(settings.buyma_tokens, settings.buyma_base_url)
    valid = 0
    for product_id, entry in payloads.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("product"), dict):
            continue
        try:
            client.validate_payload({"product": entry["product"]}, expected_product_id=str(product_id))
            if entry["product"].get("control") != "publish":
                continue
        except (ValueError, TypeError):
            continue
        valid += 1
    return valid, len(payloads)


def run(settings: Settings, logger, apply: bool, delta: int, maximum: int) -> None:
    logger.info(
        "시작 | BESTSHIP | %s | delta=%s | max_change=%s",
        "APPLY" if apply else "DRY RUN", delta, maximum
    )
    asyncio.run(run_price_competition(
        settings, logger, apply=apply, price_delta=delta, max_change=maximum
    ))


def main() -> int:
    try:
        settings = Settings.load()
        logger = setup_logging(settings.logs_dir)
    except Exception as exc:
        print(f"설정 오류: {exc}")
        print("config.example.yaml을 config.yaml로 복사하고 Google Sheets URL을 설정하세요.")
        input("Enter를 누르면 종료합니다.")
        return 2

    while True:
        print("\n" + "=" * 56)
        print("BESTSHIP 최저가 관리")
        print("=" * 56)
        print(f"상품 시트: {settings.google_price_sheet} / URL: {settings.google_url_column}")
        print("1. 가격 비교 결과 확인 (DRY RUN, 실제 변경 없음)")
        print("2. 조건에 맞는 가격을 BUYMA 공식 API로 변경")
        print("0. 종료")
        choice = input("선택: ").strip()
        if choice == "0":
            return 0
        if choice not in {"1", "2"}:
            print("1, 2, 0 중에서 선택하세요.")
            continue

        apply = choice == "2"
        if apply:
            if not settings.buyma_tokens.exists():
                print(f"OAuth 토큰 파일을 찾을 수 없습니다: {settings.buyma_tokens}")
                print("현재 연결된 토큰 파일을 복원하거나 필요한 경우에만 OAuth를 다시 연결하세요.")
                input("Enter를 누르면 메뉴로 돌아갑니다.")
                continue
            try:
                BuymaClient(settings.buyma_tokens, settings.buyma_base_url).validate_token_file()
                valid, total = valid_payload_count(settings)
            except Exception as exc:
                print(f"사전 점검 실패: {type(exc).__name__}: {exc}")
                input("Enter를 누르면 메뉴로 돌아갑니다.")
                continue
            if valid == 0:
                print("가격 변경을 중단했습니다. 유효한 전체 API 상품 payload가 없습니다.")
                print("data/buyma_products.json에 검증된 product 객체가 필요합니다.")
                print("가격 비교는 가능하지만 payload가 없는 상품의 가격은 API로 변경할 수 없습니다.")
                input("Enter를 누르면 메뉴로 돌아갑니다.")
                continue
            print(f"상품 payload 검사: 유효 {valid}개 / 전체 {total}개")
            print("payload가 없거나 상품 ID가 일치하지 않는 상품은 변경하지 않습니다.")
            print("BUYMA API 요청 접수는 실제 반영 완료를 뜻하지 않습니다.")

        delta = ask_amount("경쟁 최저가보다 낮출 금액", settings.price_delta)
        maximum = ask_amount("허용할 최대 가격 인하 폭", settings.max_change)
        if apply:
            confirm = input(f"실제 API 요청을 승인하려면 APPLY-{delta}-{maximum} 입력: ").strip()
            if confirm != f"APPLY-{delta}-{maximum}":
                print("확인 문구가 달라 취소했습니다. 가격 변경 요청은 보내지 않았습니다.")
                continue

        try:
            run(settings, logger, apply, delta, maximum)
            print("\n완료. reports 폴더의 CSV와 logs 폴더의 실행 기록을 확인하세요.")
        except KeyboardInterrupt:
            print("\n실행을 중단했습니다.")
        except Exception as exc:
            logger.exception("실행 실패")
            print(f"실행 실패: {type(exc).__name__}: {exc}")
        input("Enter를 누르면 메뉴로 돌아갑니다.")


if __name__ == "__main__":
    raise SystemExit(main())
