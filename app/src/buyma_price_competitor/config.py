from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parents[3]
)
load_dotenv(ROOT / ".env")


def _get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


@dataclass(frozen=True)
class Settings:
    root: Path
    config_path: Path
    own_seller_name: str
    own_seller_id: str
    price_delta: int
    max_change: int
    headless: bool
    slow_mo: int
    max_retry: int
    page_wait_ms: int
    chrome_paths: list[str]
    buyma_base_url: str
    google_sheet_url: str
    google_price_sheet: str
    google_history_sheet: str
    google_url_column: str
    google_scopes: list[str]
    google_service_account: Path
    buyma_tokens: Path
    product_payloads: Path
    logs_dir: Path
    reports_dir: Path
    migration_debug_dir: Path
    product_card: str
    product_name: str
    product_price_selector: str
    product_price_attribute: str
    product_seller: str
    product_timesale: str
    product_link: str

    @classmethod
    def load(cls, config_path: str | Path = "config.yaml") -> "Settings":
        path = Path(config_path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise FileNotFoundError(
                f"설정 파일이 없습니다: {path}\n"
                "config.example.yaml을 config.yaml로 복사한 뒤 값을 입력하세요."
            )

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        selectors = _get(data, "selectors", default={}) or {}
        price_cfg = _get(data, "app", "price", default={}) or {}
        browser = _get(data, "app", "browser", default={}) or {}
        seller = _get(data, "app", "own_seller", default={}) or {}
        google = _get(data, "google", default={}) or {}
        paths = _get(data, "paths", default={}) or {}
        buyma = _get(data, "app", "buyma", default={}) or {}

        price_selector = selectors.get("product_price", {})
        if isinstance(price_selector, dict):
            price_attr = str(price_selector.get("attribute", "price"))
            price_css = str(price_selector.get("selector", ".product_name a"))
        else:
            price_attr = "price"
            price_css = str(price_selector or ".product_name a")

        def abs_path(value: str) -> Path:
            p = Path(value)
            return p if p.is_absolute() else ROOT / p

        return cls(
            root=ROOT,
            config_path=path,
            own_seller_name=str(seller.get("name", "BestShip")),
            own_seller_id=str(seller.get("id", "12217668")),
            price_delta=int(price_cfg.get("delta", 1000)),
            max_change=int(price_cfg.get("max_change", 10000)),
            headless=bool(browser.get("headless", False)),
            slow_mo=int(browser.get("slow_mo", 250)),
            max_retry=int(browser.get("max_retry", 5)),
            page_wait_ms=int(browser.get("page_wait_ms", 1500)),
            chrome_paths=[str(v) for v in (browser.get("executable_paths") or [])],
            buyma_base_url=str(buyma.get("base_url", "https://personal-shopper-api.buyma.com")).rstrip("/"),
            google_sheet_url=str(google.get("sheet_url", "")),
            google_price_sheet=str(google.get("price_sheet", "[2]최저가")),
            google_history_sheet=str(google.get("history_sheet", "[5] 최저가 적용이력")),
            google_url_column=str(google.get("url_column", "URL")),
            google_scopes=list(google.get("scopes") or ["https://www.googleapis.com/auth/spreadsheets"]),
            google_service_account=abs_path(str(paths.get("google_service_account", "secrets/service_account.json"))),
            buyma_tokens=abs_path(str(paths.get("buyma_tokens", "secrets/tokens.json"))),
            product_payloads=abs_path(str(paths.get("product_payloads", "data/buyma_products.json"))),
            logs_dir=abs_path(str(paths.get("logs", "logs"))),
            reports_dir=abs_path(str(paths.get("reports", "reports"))),
            migration_debug_dir=abs_path(str(paths.get("migration_debug", "data/migration_debug"))),
            product_card=str(selectors.get("product_card", ".product_body")),
            product_name=str(selectors.get("product_name", ".product_name a")),
            product_price_selector=price_css,
            product_price_attribute=price_attr,
            product_seller=str(selectors.get("product_seller", ".product_Buyer a")),
            product_timesale=str(selectors.get("product_timesale", ".product_timesale_label")),
            product_link=str(selectors.get("product_link", "a[href]")),
        )

    def env(self, key: str, required: bool = False) -> str | None:
        value = os.getenv(key)
        if required and not value:
            raise RuntimeError(f".env에 {key}가 없습니다.")
        return value
