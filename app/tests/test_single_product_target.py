from __future__ import annotations

import json

import pytest

from buyma_price_competitor.runner import resolve_target_url


def test_single_product_uses_only_saved_source_url(tmp_path):
    id_store = tmp_path / "buyma_product_ids.json"
    id_store.write_text(
        json.dumps(
            {
                "138317608": {
                    "product_id": "138317608",
                    "source_url": "https://www.buyma.com/r/T0SE9%20LCF%200NO/",
                },
                "999999999": {
                    "product_id": "999999999",
                    "source_url": "https://www.buyma.com/r/another-item/",
                },
            }
        ),
        encoding="utf-8",
    )

    assert resolve_target_url(id_store, "138317608") == (
        "https://www.buyma.com/r/T0SE9%20LCF%200NO/"
    )


def test_single_product_missing_from_collected_ids_fails_without_fallback(tmp_path):
    id_store = tmp_path / "buyma_product_ids.json"
    id_store.write_text(json.dumps({"999999999": {"source_url": "https://example.invalid"}}))

    with pytest.raises(RuntimeError, match="138317608"):
        resolve_target_url(id_store, "138317608")


def test_single_product_without_saved_url_fails(tmp_path):
    id_store = tmp_path / "buyma_product_ids.json"
    id_store.write_text(json.dumps({"138317608": {"product_id": "138317608"}}))

    with pytest.raises(RuntimeError, match="원본 URL"):
        resolve_target_url(id_store, "138317608")


def test_missing_id_store_fails_and_does_not_scan_sheet(tmp_path):
    with pytest.raises(FileNotFoundError, match="상품 ID 저장소"):
        resolve_target_url(tmp_path / "missing.json", "138317608")
