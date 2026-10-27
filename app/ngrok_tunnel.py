"""Open an HTTPS ngrok tunnel to the local OAuth callback server on port 8000.

Loads NGROK_AUTHTOKEN from the project-root .env file.
This helper only creates the tunnel; it does not start uvicorn.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import ngrok
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> None:
    if not os.environ.get("NGROK_AUTHTOKEN"):
        raise SystemExit(
            f"NGROK_AUTHTOKEN 환경변수가 없습니다. .env 파일을 확인하세요: {ROOT / '.env'}"
        )

    listener = ngrok.forward("127.0.0.1:8000", authtoken_from_env=True)
    print(f"HTTPS 터널 주소: {listener.url()}")
    print(
        "BUYMA Redirect URI: 위 주소 + /callback "
        "(BUYMA 등록값과 .env의 BUYMA_REDIRECT_URI가 완전히 같아야 함)"
    )
    print("OAuth 서버는 별도 터미널에서 실행해야 합니다. 종료: Ctrl+C")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        ngrok.disconnect()


if __name__ == "__main__":
    main()
