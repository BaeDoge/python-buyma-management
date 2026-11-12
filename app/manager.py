"""BUYMA BESTSHIP price manager: one simple menu for collection and pricing."""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "app" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from buyma_price_competitor.config import Settings  # noqa: E402
from buyma_price_competitor.logging_utils import setup_logging  # noqa: E402
from buyma_price_competitor.runner import run_price_competition  # noqa: E402


def ask_amount(label: str, default: int) -> int:
    while True:
        raw = input(f"{label} [기본 {default:,}엔]: ").strip()
        try:
            value = default if not raw else int(raw.replace(",", ""))
        except ValueError:
            print("숫자로 입력해 주세요.")
            continue
        if value <= 0:
            print("1 이상의 금액을 입력해 주세요.")
            continue
        return value


def run_script(script: str, label: str) -> None:
    path = ROOT / "app" / script
    if not path.exists():
        print(f"실행 파일을 찾을 수 없습니다: {path}")
        return
    print(f"\n[{label}] 시작합니다.")
    result = subprocess.run([sys.executable, str(path)], cwd=ROOT)
    print(f"[{label}] 종료 코드: {result.returncode}")


def execute(settings: Settings, logger, *, apply: bool, delta: int, max_change: int,
            product_id: str | None = None, expected_new_price: int | None = None,
            approve_timesale: bool = False) -> list[dict[str, Any]]:
    return asyncio.run(
        run_price_competition(
            settings, logger, apply=apply, price_delta=delta,
            max_change=max_change, target_product_id=product_id,
            expected_new_price=expected_new_price,
            approve_timesale=approve_timesale,
        )
    ) or []


def find_product_result(results: list[dict[str, Any]], product_id: str) -> dict[str, Any] | None:
    for row in results:
        if str(row.get("상품ID") or "") == str(product_id):
            return row
    return None


def run_single_product_test(settings: Settings, logger) -> None:
    """Preview one selected product, then request one real API update only after exact confirmation."""
    product_id = input("테스트할 BUYMA 상품 ID: ").strip()
    if not product_id.isdigit():
        print("상품 ID는 숫자로 입력해 주세요.")
        return

    delta = ask_amount("경쟁 최저가보다 낮출 금액", settings.price_delta)
    max_change = ask_amount("허용할 최대 인하 폭", settings.max_change)

    print(f"\n상품 {product_id} 하나만 가격을 조회합니다. 먼저 DRY RUN으로 목표가를 계산합니다.")
    preview = execute(
        settings, logger, apply=False, delta=delta,
        max_change=max_change, product_id=product_id,
    )
    row = find_product_result(preview, product_id)
    if not row:
        print(f"상품 {product_id}의 가격 비교 결과를 찾지 못했습니다. URL 수집 결과와 상품 ID를 확인하세요.")
        return

    current = row.get("현재가")
    target = row.get("신규가")
    lowest = row.get("최저가")
    print("\n[단일 상품 변경 미리보기]")
    print(f"상품 ID : {product_id}")
    print(f"현재 가격: {current if current is not None else '-'} JPY")
    print(f"경쟁 최저가: {lowest if lowest is not None else '-'} JPY")
    print(f"변경 예정가: {target if target is not None else '-'} JPY")
    print(f"판정: {row.get('비고', '-')}")
    if target is None:
        print("변경할 가격이 없어 실제 API 요청은 보내지 않았습니다.")
        return

    print("\n위 가격으로 BUYMA 상품 하나를 변경합니다.")
    confirmation = input("실제 가격 변경을 진행할까요? (Y/N): ").strip().lower()
    if confirmation not in {"y", "yes"}:
        print("취소했습니다. BUYMA 가격은 변경되지 않았습니다.")
        return

    applied = execute(
        settings, logger, apply=True, delta=delta,
        max_change=max_change, product_id=product_id,
        expected_new_price=int(target),
    )
    applied_row = find_product_result(applied, product_id)
    if applied_row:
        print(f"결과: {applied_row.get('비고', '-')}")
    else:
        print("API 요청 결과를 찾지 못했습니다. logs/와 reports/를 확인하세요.")


def run_all_price_changes(settings: Settings, logger) -> None:
    delta = ask_amount("경쟁 최저가보다 낮출 금액", settings.price_delta)
    max_change = ask_amount("허용할 최대 인하 폭", settings.max_change)
    print("\n[전체 가격 변경]")
    print("Google Sheet에 등록된 URL 중 가격 변경 조건에 맞는 상품을 처리합니다.")
    confirmation = input("가격 변경을 시작할까요? (Y/N): ").strip().lower()
    if confirmation not in {"y", "yes"}:
        print("취소했습니다.")
        return
    execute(
        settings, logger, apply=True, delta=delta,
        max_change=max_change, approve_timesale=False,
    )


def main() -> int:
    try:
        settings = Settings.load()
        logger = setup_logging(settings.logs_dir)
    except Exception as exc:
        print(f"설정 오류: {exc}")
        print("config.example.yaml을 config.yaml로 복사하고 Google Sheet 설정을 입력하세요.")
        return 2

    while True:
        print("\n" + "=" * 54)
        print("BUYMA BESTSHIP 최저가 관리")
        print("=" * 54)
        print("1. 전체 상품 가격 비교 미리보기 (실제 변경 없음)")
        print("2. 단일 상품 가격 변경 테스트")
        print("3. 전체 상품 가격 변경")
        print("0. 종료")
        choice = input("선택: ").strip()

        try:
            if choice == "0":
                return 0
            if choice == "1":
                delta = ask_amount("경쟁 최저가보다 낮출 금액", settings.price_delta)
                maximum = ask_amount("허용할 최대 인하 폭", settings.max_change)
                execute(settings, logger, apply=False, delta=delta, max_change=maximum)
                print("미리보기 완료. reports/의 CSV에서 상품별 결과를 확인하세요.")
            elif choice == "2":
                run_single_product_test(settings, logger)
            elif choice == "3":
                run_all_price_changes(settings, logger)
            else:
                print("0~3 중에서 선택해 주세요.")
        except KeyboardInterrupt:
            print("\n현재 작업을 중단했습니다.")
        except Exception as exc:
            logger.exception("작업 실패")
            print(f"작업 실패: {type(exc).__name__}: {exc}")

        input("\nEnter를 누르면 메뉴로 돌아갑니다.")


if __name__ == "__main__":
    raise SystemExit(main())
