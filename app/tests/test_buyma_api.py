from __future__ import annotations

import json
from pathlib import Path

import pytest

from buyma_price_competitor.buyma_api import BuymaAPIError, BuymaClient


@pytest.fixture
def valid_stored_payload():
    return {
        "product": {
            "id": 123456789,
            "control": "publish",
            "name": "Test product",
            "comments": "Existing description",
            "brand_id": 1,
            "category_id": 2,
            "price": 12000,
            "available_until": "2027-12-31",
            "buying_area_id": 1,
            "shipping_area_id": 1,
            "images": [{"url": "https://example.invalid/image.jpg"}],
            "shipping_methods": [],
            "options": [],
            "variants": [],
        }
    }


def test_build_price_update_payload_changes_only_price(tmp_path, valid_stored_payload):
    client = BuymaClient(tmp_path / "tokens.json", "https://example.invalid")
    original = json.loads(json.dumps(valid_stored_payload))

    body = client.build_price_update_payload(
        valid_stored_payload, 11990, expected_product_id="123456789"
    )

    assert body["product"]["price"] == 11990
    assert body["product"]["id"] == 123456789
    assert body["product"]["name"] == original["product"]["name"]
    assert valid_stored_payload == original  # caller's stored data is not mutated


def test_missing_required_field_is_rejected_before_request(tmp_path, valid_stored_payload):
    client = BuymaClient(tmp_path / "tokens.json", "https://example.invalid")
    del valid_stored_payload["product"]["variants"]

    with pytest.raises(ValueError, match="variants"):
        client.build_price_update_payload(valid_stored_payload, 11990)


def test_wrong_product_id_is_rejected(tmp_path, valid_stored_payload):
    client = BuymaClient(tmp_path / "tokens.json", "https://example.invalid")

    with pytest.raises(ValueError, match="ID 불일치"):
        client.build_price_update_payload(
            valid_stored_payload, 11990, expected_product_id="999999999"
        )


@pytest.mark.parametrize("price", [0, -1])
def test_non_positive_price_is_rejected(tmp_path, valid_stored_payload, price):
    client = BuymaClient(tmp_path / "tokens.json", "https://example.invalid")

    with pytest.raises(ValueError, match="JPY"):
        client.build_price_update_payload(valid_stored_payload, price)


def test_update_price_posts_api_body_and_accepts_201(tmp_path, valid_stored_payload, monkeypatch):
    token_path = tmp_path / "tokens.json"
    token_path.write_text(json.dumps({"access_token": "test-token"}), encoding="utf-8")
    client = BuymaClient(token_path, "https://api.example.invalid")

    class FakeResponse:
        status_code = 201
        text = ""

        @staticmethod
        def json():
            return {"request_uid": "test-request-uid"}

    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(client.session, "post", fake_post)
    result = client.update_price(
        valid_stored_payload, 11990, expected_product_id="123456789"
    )

    assert captured["url"] == "https://api.example.invalid/api/v1/products.json"
    assert captured["headers"]["X-Buyma-Personal-Shopper-Api-Access-Token"] == "test-token"
    assert captured["json"]["product"]["price"] == 11990
    assert result["request_uid"] == "test-request-uid"


def test_non_201_response_raises_api_error(tmp_path, valid_stored_payload, monkeypatch):
    token_path = tmp_path / "tokens.json"
    token_path.write_text(json.dumps({"access_token": "test-token"}), encoding="utf-8")
    client = BuymaClient(token_path, "https://api.example.invalid")

    class FakeResponse:
        status_code = 400
        text = "bad request"

        @staticmethod
        def json():
            return {"error": "invalid payload"}

    monkeypatch.setattr(client.session, "post", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(BuymaAPIError, match="HTTP 400"):
        client.update_price(valid_stored_payload, 11990)
