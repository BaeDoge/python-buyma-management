from buyma_price_competitor.runner import resolve_target_url


def test_payload_readiness_message_contains_missing_fields():
    entry = {
        "migration_status": "mapping_incomplete",
        "mapping_missing_fields": ["shipping_methods", "options", "variants"],
        "source_summary": {"source_keys": ["id", "name", "price", "item_images"]},
    }
    message = (
        f"상태={entry['migration_status']}; "
        f"미확보 필드={', '.join(entry['mapping_missing_fields'])}; "
        f"원본 필드={', '.join(entry['source_summary']['source_keys'])}"
    )
    assert "mapping_incomplete" in message
    assert "shipping_methods" in message
    assert "options" in message
    assert "variants" in message
    assert "item_images" in message
