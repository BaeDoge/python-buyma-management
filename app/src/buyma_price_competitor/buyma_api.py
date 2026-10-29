from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import requests


class BuymaAPIError(RuntimeError):
    pass


class BuymaClient:
    def __init__(self, token_path: Path, base_url: str):
        self.token_path = token_path
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def validate_token_file(self) -> None:
        """Check local OAuth token structure without making a network request."""
        self._token()

    def _token(self) -> str:
        if not self.token_path.exists():
            raise FileNotFoundError(
                f"BUYMA OAuth token이 없습니다: {self.token_path}"
            )
        try:
            data = json.loads(self.token_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"BUYMA OAuth token 파일을 읽을 수 없습니다: {self.token_path}") from exc
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise RuntimeError("tokens.json에 access_token이 없습니다. OAuth를 다시 진행하세요.")
        return str(token)

    REQUIRED_FIELDS = {
        "control", "name", "comments", "brand_id", "category_id",
        "price", "available_until", "buying_area_id", "shipping_area_id",
        "images", "shipping_methods", "options", "variants",
    }

    def validate_payload(
        self,
        stored_payload: dict[str, Any],
        *,
        expected_product_id: str | None = None,
    ) -> None:
        product = stored_payload.get("product")
        if not isinstance(product, dict):
            raise ValueError("저장된 payload에 product 객체가 없습니다.")
        missing = sorted(self.REQUIRED_FIELDS - product.keys())
        if missing:
            raise ValueError(
                "BUYMA API 필수 필드 누락: " + ", ".join(missing)
                + ". 이 상품 payload는 아직 가격 변경에 사용할 수 없습니다."
            )
        if not product.get("id") and not product.get("reference_number"):
            raise ValueError("payload에 id 또는 reference_number가 없습니다.")
        if expected_product_id is not None:
            if product.get("id") is None:
                raise ValueError(
                    f"payload에 BUYMA 상품 id가 없습니다 (대상={expected_product_id}). "
                    "다른 상품 수정 방지를 위해 reference_number만으로는 요청하지 않습니다."
                )
            if str(product["id"]) != str(expected_product_id):
                raise ValueError(
                    f"payload 상품 ID 불일치: 저장값={product['id']}, "
                    f"대상={expected_product_id}. 잘못된 상품 수정 방지를 위해 중단합니다."
                )
        if product.get("control") not in {"publish", "draft", "suspend"}:
            raise ValueError(
                f"payload의 control 값이 유효하지 않습니다: {product.get('control')!r}. "
                "기존 상품 상태를 확인한 전체 payload를 사용하세요."
            )

    def update_price(
        self,
        stored_payload: dict[str, Any],
        new_price: int,
        *,
        expected_product_id: str | None = None,
    ) -> dict[str, Any]:
        body = deepcopy(stored_payload)
        self.validate_payload(body, expected_product_id=expected_product_id)
        product = body["product"]
        # This updater operates only on products observed publicly. Never let a
        # price-only run accidentally draft or suspend a live listing.
        if product.get("control") != "publish":
            raise BuymaAPIError(
                "가격 변경 요청은 control='publish'인 공개 상품 payload만 허용합니다. "
                "상품 상태 변경 위험이 있어 API 요청을 보내지 않았습니다."
            )
        product["price"] = int(new_price)

        response = self.session.post(
            f"{self.base_url}/api/v1/products.json",
            headers={
                "X-Buyma-Personal-Shopper-Api-Access-Token": self._token(),
            },
            json=body,
            timeout=60,
        )

        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text}

        if response.status_code != 201:
            raise BuymaAPIError(
                f"BUYMA Product API HTTP {response.status_code}: {data}"
            )
        return data
