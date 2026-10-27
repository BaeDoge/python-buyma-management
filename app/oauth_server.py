from __future__ import annotations

import json
import os
import secrets
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from buyma_price_competitor.config import ROOT

load_dotenv(ROOT / ".env")

app = FastAPI(title="BUYMA OAuth")
state_value: str | None = None

BASE_URL = os.getenv(
    "BUYMA_API_BASE_URL",
    "https://personal-shopper-api.buyma.com",
).rstrip("/")


@app.get("/", response_class=HTMLResponse)
def home():
    return '<h2>BUYMA OAuth</h2><a href="/login">BUYMA OAuth 시작</a>'


@app.get("/login")
def login():
    global state_value
    state_value = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": os.environ["BUYMA_CLIENT_ID"],
        "redirect_uri": os.environ["BUYMA_REDIRECT_URI"],
        "state": state_value,
    }
    return RedirectResponse(
        f"{BASE_URL}/oauth/authorize?{urlencode(params)}"
    )


@app.get("/callback", response_class=HTMLResponse)
def callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        safe_error = str(error).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<h2>OAuth 실패</h2><p>BUYMA가 인증을 거부했거나 인증이 완료되지 않았습니다.</p><pre>{safe_error}</pre>"
    if not code or state != state_value:
        return "<h2>OAuth 실패</h2><p>code 또는 state가 올바르지 않습니다.</p>"

    response = requests.post(
        f"{BASE_URL}/oauth/token",
        json={
            "code": code,
            "client_id": os.environ["BUYMA_CLIENT_ID"],
            "client_secret": os.environ["BUYMA_CLIENT_SECRET"],
            "grant_type": "authorization_code",
            "redirect_uri": os.environ["BUYMA_REDIRECT_URI"],
        },
        timeout=30,
    )
    if not response.ok:
        # Do not print or persist client_secret, code, or tokens in logs/pages.
        return (
            "<h2>OAuth 토큰 발급 실패</h2>"
            f"<p>BUYMA 토큰 엔드포인트가 HTTP {response.status_code}를 반환했습니다.</p>"
            "<p>환경, Client ID/Secret, Redirect URI 일치 여부를 확인하세요.</p>"
        )

    try:
        token_data = response.json()
    except ValueError:
        return "<h2>OAuth 토큰 발급 실패</h2><p>BUYMA 응답이 JSON 형식이 아닙니다.</p>"
    if not isinstance(token_data, dict) or not token_data.get("access_token"):
        return "<h2>OAuth 토큰 발급 실패</h2><p>응답에 access_token이 없습니다.</p>"

    token_path = ROOT / "secrets" / "tokens.json"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(
        json.dumps(token_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return "<h2>BUYMA OAuth 성공</h2><p>secrets/tokens.json에 저장되었습니다.</p>"
