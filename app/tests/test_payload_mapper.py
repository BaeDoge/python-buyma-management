from buyma_price_competitor.payload_mapper import convert_source_product


def test_maps_known_scalar_fields_and_api_shaped_collections():
    source = {
        "id": 123,
        "status": "public",
        "name": "Sample",
        "comment": "Description",
        "brand": {"id": 7},
        "category_id": 8,
        "price": 12000,
        "period": "2027-12-31",
        "purchase_area": {"id": 9},
        "shipping_area": {"id": 10},
        "item_images": [{"url": "https://example.test/a.jpg"}],
        "shipping_methods": [{"id": 11}],
        "options": [{"type": "size", "value": "FREE", "master_id": 0, "position": 1}],
        "variants": [{"options": [{"type": "size", "value": "FREE"}],
                      "stock_type": "purchase_for_order", "stocks": None}],
    }
    product, missing = convert_source_product(source, "123")

    assert missing == []
    assert product["control"] == "publish"
    assert product["price"] == 12000
    assert product["available_until"] == "2027/12/31"
    assert product["images"] == [{"path": "https://example.test/a.jpg", "position": 1}]
    assert product["shipping_methods"] == [{"shipping_method_id": 11}]


def test_does_not_invent_unknown_fields():
    product, missing = convert_source_product(
        {"id": 123, "status": "public", "name": "Sample", "price": 12000}, "123"
    )

    assert product["price"] == 12000
    assert "options" in missing
    assert "variants" in missing
    assert "shipping_methods" in missing
    assert "buying_area_id" in missing


def test_rejects_mismatched_product_id():
    _, missing = convert_source_product({"id": 456}, "123")
    assert "id(product ID mismatch)" in missing
