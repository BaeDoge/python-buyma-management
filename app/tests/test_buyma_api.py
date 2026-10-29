from __future__ import annotations

import pytest

from buyma_price_competitor.buyma_api import BuymaAPIError, BuymaClient


class NeverCalledSession:
    def post(self, *args, **kwargs):
        raise AssertionError("A guarded request must not reach the network")


def valid_payload(control: str = "suspend") -> dict:
    return {
        "product": {
            "id": 123456789,
            "control": control,
            "name": "Example product",
            "comments": "Example comments",
            "brand_id": 0,
            "category_id": 1,
            "price": 1000,
            "available_until": "2099/12/31",
            "buying_area_id": 1,
            "shipping_area_id": 1,
            "images": [{"path": "https://example.invalid/image.jpg", "position": 1}],
            "shipping_methods": [{"shipping_method_id": 1}],
            "options": [],
            "variants": [],
        }
    }


def test_price_update_never_suspends_or_drafts_public_listing(tmp_path):
    client = BuymaClient(tmp_path / "tokens.json", "https://example.invalid")
    client.session = NeverCalledSession()

    with pytest.raises(BuymaAPIError, match="control='publish'"):
        client.update_price(
            valid_payload(control="suspend"),
            900,
            expected_product_id="123456789",
        )
