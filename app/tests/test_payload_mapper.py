from buyma_price_competitor.payload_mapper import convert_source_product


def sample_source():
    return {
        "id": 123,
        "status": "publish",
        "name": "Sample",
        "comment": "Description",
        "brand": {"id": 7},
        "category_id": 8,
        "price": 12000,
        "period": "2027-12-31T23:59:59+09:00",
        "purchase_area": {"area_cd": "2002003", "city_cd": "000"},
        "shipping_area": {"area_cd": "2002003", "city_cd": "000"},
        "item_images": [{"position": 1, "zoom_url": "https://example.test/a.jpg"}],
        "shipping_methods": [{"id": 11, "price": 0, "bill_type": "sender"}],
        "colors": [{"master_id": 2, "name": "Black", "id": 20}],
        "sizes": [{"master_id": 0, "name": "FREE", "id": 30, "details": []}],
        "colorsizes": [[{"id": 40, "selectable": 1}]],
        "capacity_amount": "1",
        "include_duty": True,
        "duty_type": "prepaid",
        "timesale": None,
    }


def test_maps_real_seller_source_shape_to_api_payload():
    product, missing = convert_source_product(sample_source(), "123")

    assert missing == []
    assert product["control"] == "publish"
    assert product["price"] == 12000
    assert product["available_until"] == "2027/12/31"
    assert product["buying_area_id"] == "2002003000"
    assert product["shipping_area_id"] == "2002003000"
    assert product["images"] == [{"path": "https://example.test/a.jpg", "position": 1}]
    assert product["shipping_methods"] == [{"shipping_method_id": 11}]
    assert product["options"] == [
        {"type": "size", "value": "FREE", "master_id": 0, "position": 1},
        {"type": "color", "value": "Black", "master_id": 2, "position": 1},
    ]
    assert product["variants"] == [{
        "options": [{"type": "size", "value": "FREE"}, {"type": "color", "value": "Black"}],
        "stock_type": "purchase_for_order",
        "stocks": None,
    }]
    assert product["order_quantity"] == 1


def test_maps_unavailable_variant_without_inventing_stock():
    source = sample_source()
    source["colorsizes"] = [[{"id": 40, "selectable": 0}]]

    product, missing = convert_source_product(source, "123")

    assert missing == []
    assert product["variants"][0]["stock_type"] == "out_of_stock"
    assert product["variants"][0]["stocks"] is None
    assert "order_quantity" not in product


def test_active_timesale_is_not_marked_ready_for_base_price_update():
    source = sample_source()
    source["timesale"] = {"status": "on", "price": 11900}

    product, missing = convert_source_product(source, "123")

    assert product["price"] == 12000
    assert any("active_timesale" in field for field in missing)


def test_does_not_invent_unknown_fields():
    product, missing = convert_source_product(
        {"id": 123, "status": "publish", "name": "Sample", "price": 12000}, "123"
    )

    assert product["price"] == 12000
    assert "options" in missing
    assert "variants" in missing
    assert "shipping_methods" in missing
    assert "buying_area_id" in missing


def test_rejects_mismatched_product_id():
    _, missing = convert_source_product({"id": 456}, "123")
    assert "id(product ID mismatch)" in missing


def test_maps_buyma_documented_public_status_to_publish_control():
    source = sample_source()
    source["status"] = "public"

    product, missing = convert_source_product(source, "123")

    assert product["control"] == "publish"
    assert missing == []
