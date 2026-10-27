from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "https://personal-shopper-api.buyma.com"


def load_settings(config_path: Path) -> tuple[str, Path]:
    base_url = DEFAULT_BASE_URL
    token_path = ROOT / "secrets" / "tokens.json"

    if config_path.exists():
        try:
            import yaml
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            base_url = str(
                cfg.get("app", {}).get("buyma", {}).get("base_url", base_url)
            ).rstrip("/")
            configured_token = cfg.get("paths", {}).get("buyma_tokens")
            if configured_token:
                p = Path(str(configured_token))
                token_path = p if p.is_absolute() else ROOT / p
        except Exception as exc:
            raise RuntimeError(f"설정 파일을 읽지 못했습니다: {config_path} ({type(exc).__name__})") from exc
    return base_url, token_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="BUYMA API 연결/토큰 확인 전용. 상품 등록·수정·삭제 요청은 보내지 않습니다."
    )
    parser.add_argument("--config", default=str(ROOT / "config.yaml"), help="설정 파일 경로 (기본: config.yaml)")
    args = parser.parse_args()

    try:
        base_url, token_path = load_settings(Path(args.config))
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            print("오류: API 주소는 유효한 HTTPS URL이어야 합니다.")
            return 2
        if not token_path.exists():
            print(f"실패: 토큰 파일을 찾을 수 없습니다: {token_path}")
            print("OAuth 완료 후 tokens.json이 있는지 확인하세요.")
            return 2
        try:
            token_data = json.loads(token_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"실패: tokens.json을 읽을 수 없습니다 ({type(exc).__name__}).")
            return 2
        token = token_data.get("access_token") if isinstance(token_data, dict) else None
        if not isinstance(token, str) or not token.strip():
            print("실패: tokens.json에 access_token이 없습니다.")
            return 2

        # Read-only endpoint only. Do not print the response body because order
        # records may contain personal or transaction information.
        url = f"{base_url.rstrip('/')}/api/v1/orders.json"
        print(f"API 환경: {parsed.netloc}")
        print("요청: GET /api/v1/orders.json?page=1&per_page=1 (읽기 전용)")
        print(f"토큰 파일: {token_path}")
        print("토큰 값: 출력하지 않음")
        try:
            response = requests.get(
                url,
                params={"page": 1, "per_page": 1},
                headers={
                    "Accept": "application/json",
                    "X-Buyma-Personal-Shopper-Api-Access-Token": token,
                },
                timeout=(10, 30),
            )
        except requests.RequestException as exc:
            print(f"연결 실패: {type(exc).__name__}: 네트워크, DNS, TLS 또는 API 주소를 확인하세요.")
            return 3

        print(f"HTTP 상태: {response.status_code}")
        if response.status_code == 200:
            print("결과: API 연결 및 해당 읽기 API 인증 성공")
            print("주의: 주문 조회 권한 확인 결과이며, 상품 수정 가능 여부까지 증명하지는 않습니다.")
            return 0
        if response.status_code == 401:
            print("결과: 인증 실패. 토큰이 잘못되었거나 해당 환경과 맞지 않을 수 있습니다.")
        elif response.status_code == 403:
            print("결과: 접근 거부. 앱 권한, 판매자 계정 승인 또는 API 접근 권한을 확인하세요.")
        elif response.status_code == 404:
            print("결과: 엔드포인트 또는 API 주소를 확인해야 합니다.")
        elif response.status_code == 429:
            print("결과: 요청 제한에 도달했습니다. 잠시 후 재시도하세요.")
        else:
            print("결과: API가 오류 응답을 반환했습니다.")
        try:
            data = response.json()
            errors = data.get("errors") if isinstance(data, dict) else None
            if errors:
                print("API 오류 상세:", json.dumps(errors, ensure_ascii=False)[:1000])
        except ValueError:
            pass
        print("개인정보 보호를 위해 응답 본문 전체는 출력하지 않았습니다.")
        return 1
    except Exception as exc:
        print(f"테스트 준비 실패: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
