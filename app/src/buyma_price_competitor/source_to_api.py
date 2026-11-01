"""Strict conversion from BUYMA seller-page source data to Product API body.

The source endpoint and Product API use different schemas. This mapper only maps
values that are explicitly present in the captured source record. It never invents
brand/category/area/shipping/option/stock values. Missing or ambiguous fields are
reported together so the operator can fix the source mapping from a real capture.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


class PayloadMappingError(ValueError):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(
            "API payload로 변환할 수 없습니다. 원본 데이터에서 확인되지 않은 값: "
            + ", ".join(missing)
        )


def _first(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _id(value: Any) -> Any:
    if isinstance(value, dict):
        return _first(value, "id", "value")
    return value


def _images(source: Any) -> list[dict[str, Any]] | None:
    if not isinstance(source, list) or not source:
        return None
    result = []
    for index, item in enumerate(source, 1):
        if isinstance(item, str):
            path = item
        elif isinstance(item, dict):
            path = _first(item, "path", "url", "image_url", "src")
        else:
            path = None
        if not path:
            return None
        result.append({"path": path, "position": index})
    return result


def _shipping_methods(source: Any) -> list[dict[str, Any]] | None:
    if not isinstance(source, list) or not source:
        return None
    result = []
    for item in source:
        method_id = _id(item)
        if isinstance(item, dict):
            method_id = _first(item, "shipping_method_id", "id", "value")
        if method_id is None:
            return None
        result.append({"shipping_method_id": method_id})
    return result


def convert_source_product(source: dict[str, Any]) -> dict[str, Any]:
    """Convert a captured BUYMA source product into {product: ...}.

    This function is intentionally fail-closed. It supports direct API-shaped
    options/variants where present; it does not infer stock combinations from
    display labels or fabricate shipping and area master IDs.
    """
    if not isinstance(source, dict):
        raise TypeError("원본 상품 데이터는 JSON 객체여야 합니다.")

    product_id = _first(source, "id", "product_id")
    name = _first(source, "name", "title")
    comments = _first(source, "comments", "comment", "description")
    brand_id = _id(_first(source, "brand_id", "brand"))
    category_id = _first(source, "category_id", "category")
    price = _first(source, "price")
    available_until = _first(source, "available_until", "period", "purchase_deadline")
    buying_area_id = _id(_first(source, "buying_area_id", "purchase_area", "buying_area"))
    shipping_area_id = _id(_first(source, "shipping_area_id", "shipping_area"))
    images = _images(_first(source, "images", "item_images"))
    shipping_methods = _shipping_methods(_first(source, "shipping_methods"))
    options = _first(source, "options")
    variants = _first(source, "variants")

    missing = []
    required_values = {
        "id": product_id,
        "name": name,
        "comments": comments,
        "brand_id": brand_id,
        "category_id": category_id,
        "price": price,
        "available_until": available_until,
        "buying_area_id": buying_area_id,
        "shipping_area_id": shipping_area_id,
        "images": images,
        "shipping_methods": shipping_methods,
        "options": options if isinstance(options, list) else None,
        "variants": variants if isinstance(variants, list) else None,
    }
    for key, value in required_values.items():
        if value is None or value == []:
            missing.append(key)

    status = str(_first(source, "status", "control") or "").lower()
    control_map = {
        "public": "publish",
        "publish": "publish",
        "draft": "draft",
        "buyer_suspended": "suspend",
        "suspend": "suspend",
    }
    control = control_map.get(status)
    if not control:
        missing.append("control(status 값으로 판별 불가)")

    if missing:
        raise PayloadMappingError(missing)

    try:
        price = int(price)
    except (TypeError, ValueError):
        raise PayloadMappingError(["price(정수 JPY가 아님)"]) from None
    if price <= 0:
        raise PayloadMappingError(["price(1 이상의 JPY 정수가 아님)"])

    product: dict[str, Any] = {
        "id": int(product_id),
        "control": control,
        "name": str(name),
        "comments": str(comments),
        "brand_id": brand_id,
        "category_id": category_id,
        "price": price,
        "available_until": str(available_until).replace("-", "/")[:10],
        "buying_area_id": buying_area_id,
        "shipping_area_id": shipping_area_id,
        "images": images,
        "shipping_methods": shipping_methods,
        "options": deepcopy(options),
        "variants": deepcopy(variants),
    }

    # Optional fields are copied only when present in the captured source.
    optional = {
        "buying_shop_name": ("buying_shop_name",),
        "buyer_notes": ("buyer_notes",),
        "duty": ("duty",),
        "tags": ("tags",),
        "style_numbers": ("style_numbers",),
        "size_unit": ("size_unit",),
        "colorsize_comments": ("colorsize_comments",),
        "order_quantity": ("order_quantity",),
        "shop_urls": ("shop_urls",),
        "regular_price": ("regular_price",),
        "reference_price": ("reference_price",),
    }
    for target, aliases in optional.items():
        value = _first(source, *aliases)
        if value is not None:
            product[target] = deepcopy(value)

    return {"product": product}
