"""Interactive menu for one-time setup and occasional product discovery.

This is not part of the recurring price-refresh path. Payload migration may
open a BUYMA web session and should only be selected deliberately.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(label: str, command: list[str], login_note: str, api_note: str) -> None:
    print(f"\n=== {label} ===")
    print(f"BUYMA 웹 로그인: {login_note}")
    print(f"BUYMA 공식 API: {api_note}")
    input("준비가 되었으면 Enter를 누르세요. 취소하려면 Ctrl+C: ")
    result = subprocess.run(command, cwd=ROOT)
    print(f"\n작업 종료 코드: {result.returncode}")
    input("Enter를 누르면 메뉴로 돌아갑니다.")


def main() -> None:
    python = sys.executable
    while True:
        print("\n" + "=" * 58)
        print("BUYMA 최초 1회 설정 / 신규 상품 처리")
        print("정기 최저가 갱신은 refresh_prices.py 를 사용하세요.")
        print("=" * 58)
        print("1. BUYMA OAuth 권한 승인/토큰 발급 (최초 1회 또는 재승인 시)")
        print("2. 공개 페이지에서 상품 ID 수집 (비로그인, 공식 API 미사용)")
        print("3. 상품 payload 수집 시도 (웹 로그인 필요, 필요한 경우에만)")
        print("0. 종료")
        choice = input("선택: ").strip()

        if choice == "1":
            print("OAuth 서버 실행 후 브라우저에서 http://127.0.0.1:8000 을 열어 승인하세요.")
            print("승인 완료 후 이 터미널에서 Ctrl+C로 서버를 종료하면 메뉴로 돌아옵니다.")
            run(
                "BUYMA OAuth 승인",
                [python, "-m", "uvicorn", "oauth_server:app", "--host", "127.0.0.1", "--port", "8000"],
                "브라우저에서 BUYMA 계정 인증이 필요합니다.",
                "토큰 발급을 위한 OAuth endpoint를 사용합니다.",
            )
        elif choice == "2":
            run(
                "공개 상품 ID 수집",
                [python, "migration.py"],
                "하지 않습니다. 공개 페이지를 조회합니다.",
                "사용하지 않습니다.",
            )
        elif choice == "3":
            print("주의: 이 작업은 BUYMA에 로그인하고 상품 편집 페이지를 조회합니다.")
            print("정기 실행에서는 사용하지 마세요. source-only 결과는 API payload가 아닙니다.")
            run(
                "payload 수집 시도",
                [python, "payload_migration.py"],
                "필요합니다. 상품별 편집 페이지를 조회합니다.",
                "API 가격 변경 요청은 보내지 않습니다.",
            )
        elif choice == "0":
            return
        else:
            print("잘못된 선택입니다.")


if __name__ == "__main__":
    main()
