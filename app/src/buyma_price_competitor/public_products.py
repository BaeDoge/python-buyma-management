from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urljoin

from playwright.async_api import Locator, Page


BASE_URL = "https://www.buyma.com"


def normalize_seller(value: str | None) -> str:
    if value is None:
        return ""
    value = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", "", value).casefold()


def parse_price(value: object) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^0-9]", "", str(value))
    return int(digits) if digits else None


def extract_product_id(value: object) -> str | None:
    if not value:
        return None
    text = str(value)
    patterns = (
        r"/(?:items?|item)/([0-9]+)",
        r"/my/sell/([0-9]+)",
        r"(?:^|[^0-9])([0-9]{7,12})(?:[^0-9]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def extract_seller_id(value: object) -> str | None:
    if not value:
        return None
    match = re.search(r"/buyer/([0-9]+)", str(value))
    return match.group(1) if match else None


@dataclass
class PublicProduct:
    name: str | None
    price: int | None
    seller_name: str | None
    seller_id: str | None
    product_id: str | None
    is_timesale: bool
    body_index: int


class PublicProductCollector:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger

    async def _field_text(self, body: Locator, selector: str) -> str:
        try:
            return (await body.locator(selector).inner_text()).strip()
        except Exception:
            return ""

    async def _price(self, body: Locator) -> int | None:
        try:
            element = body.locator(self.settings.product_price_selector).first
            attr = self.settings.product_price_attribute
            value = await element.get_attribute(attr)
            if value:
                parsed = parse_price(value)
                if parsed is not None:
                    return parsed
            return parse_price(await element.inner_text())
        except Exception:
            return None

    async def _seller(self, body: Locator) -> tuple[str | None, str | None]:
        try:
            element = body.locator(self.settings.product_seller).first
            name = (await element.inner_text()).strip()
            href = await element.get_attribute("href")
            return name or None, extract_seller_id(href)
        except Exception:
            return None, None

    async def _product_id(self, body: Locator) -> str | None:
        # 설정 selector보다 먼저 상품 카드 내부의 공개 item URL을 폭넓게 검사한다.
        try:
            links = body.locator(self.settings.product_link)
            for i in range(await links.count()):
                href = await links.nth(i).get_attribute("href")
                product_id = extract_product_id(href)
                if product_id:
                    return product_id
        except Exception:
            pass

        # data-* 속성에 ID가 들어오는 경우도 대응
        for attr in ("data-product-id", "data-item-id", "data-id"):
            try:
                value = await body.get_attribute(attr)
                product_id = extract_product_id(value)
                if product_id:
                    return product_id
            except Exception:
                pass
        return None

    def is_own_seller(self, product: PublicProduct) -> bool:
        # seller ID를 최우선으로 사용한다.
        if self.settings.own_seller_id and product.seller_id:
            return str(product.seller_id) == str(self.settings.own_seller_id)

        # seller ID가 DOM에서 사라져도 이름으로 fallback.
        return normalize_seller(product.seller_name) == normalize_seller(
            self.settings.own_seller_name
        )

    async def collect(self, page: Page) -> list[PublicProduct]:
        cards = page.locator(self.settings.product_card)
        count = await cards.count()
        products: list[PublicProduct] = []

        for index in range(count):
            body = cards.nth(index)
            name = await self._field_text(body, self.settings.product_name)
            price = await self._price(body)
            seller_name, seller_id = await self._seller(body)
            product_id = await self._product_id(body)

            try:
                is_timesale = await body.locator(
                    self.settings.product_timesale
                ).count() > 0
            except Exception:
                is_timesale = False

            products.append(
                PublicProduct(
                    name=name or None,
                    price=price,
                    seller_name=seller_name,
                    seller_id=seller_id,
                    product_id=product_id,
                    is_timesale=is_timesale,
                    body_index=index,
                )
            )

        return products

    async def open_public(self, page: Page, url: str) -> bool:
        for attempt in range(1, self.settings.max_retry + 1):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if "/my/" in page.url:
                    raise RuntimeError(f"공개 URL이 /my/로 이동함: {page.url}")
                await page.wait_for_timeout(self.settings.page_wait_ms)
                return True
            except Exception as exc:
                self.logger.warning(
                    "[%s/%s] 공개 페이지 접속 실패: %s",
                    attempt, self.settings.max_retry, exc
                )
            if attempt < self.settings.max_retry:
                await page.wait_for_timeout(2000)
        return False
