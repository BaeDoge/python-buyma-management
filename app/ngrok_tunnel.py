"""Open an HTTPS ngrok tunnel to the local OAuth callback server on port 8000.

Set NGROK_AUTHTOKEN in the current shell before running this script.
This helper only creates the tunnel; it does not start uvicorn.
"""
from __future__ import annotations
import os
import time
import ngrok

def main() -> None:
    if not os.environ.get("NGROK_AUTHTOKEN"):
        raise SystemExit("NGROK_AUTHTOKEN 환경변수가 없습니다. ngrok 대시보드의 토큰을 설정하세요.")
    listener = ngrok.forward("127.0.0.1:8000", authtoken_from_env=True)
    print(f"HTTPS 터널 주소: {listener.url()}")
    print("BUYMA Redirect URI: 위 주소 + /callback (BUYMA 등록값과 .env 값이 완전히 같아야 함)")
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
