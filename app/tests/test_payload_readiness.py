from buyma_price_competitor.payload_mapper import convert_source_product


def test_incomplete_live_source_data_fails_closed_with_missing_fields():
    product, missing = convert_source_product(
        {"id": "138317608", "name": "sample", "price": 1000},
        "138317608",
    )

    assert product["id"] == 138317608
    assert "images" in missing
    assert "shipping_methods" in missing
    assert "options" in missing
    assert "variants" in missing
