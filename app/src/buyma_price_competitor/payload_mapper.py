"""Conservative adapter from BUYMA seller-page data to Product API payload.

Only values explicitly present in the captured seller data are mapped. Complex
arrays are copied only when they already match the documented API representation;
the adapter never invents shipping methods, options, stock, or area IDs.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Any

API_REQUIRED = (
    "control", "name", "comments", "brand_id", "category_id", "price",
    "available_until", "buying_area_id", "shipping_area_id", "images",
    "shipping_methods", "options", "variants",
)


def _first(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


def _nested_id(value: Any) -> Any:
    if isinstance(value, dict):
        return _first(value, "id", "brand_id", "area_id", "value")
    return value


def _api_images(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    result = []
    for index, item in enumerate(value, 1):
        if not isinstance(item, dict):
            return None
        path = _first(item, "path", "url", "image_url", "original_url")
        if not path:
            return None
        result.append({"path": path, "position": item.get("position", index)})
    return result


def _api_shipping_methods(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    result = []
    for item in value:
        method_id = _nested_id(item)
        if isinstance(method_id, bool) or not isinstance(method_id, (int, str)):
            return None
        result.append({"shipping_method_id": int(method_id)})
    return result


def _already_api_options(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    required = {"type", "value", "master_id", "position"}
    if all(isinstance(x, dict) and required.issubset(x) for x in value):
        return deepcopy(value)
    return None


def _already_api_variants(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    for item in value:
        if not isinstance(item, dict) or not {"options", "stock_type", "stocks"}.issubset(item):
            return None
    return deepcopy(value)


def convert_source_product(source: dict[str, Any], product_id: str) -> tuple[dict[str, Any], list[str]]:
    """Return (candidate API product, unresolved required fields)."""
    if not isinstance(source, dict):
        raise TypeError("source_product_data must be an object")

    status = str(_first(source, "status", "product_status") or "").lower()
    control = {"public": "publish", "published": "publish", "draft": "draft",
               "buyer_suspended": "suspend", "suspended": "suspend"}.get(status)

    brand = _first(source, "brand", "brand_id")
    purchase_area = _first(source, "purchase_area", "buying_area_id")
    ship_area = _first(source, "shipping_area", "shipping_area_id")

    raw_period = _first(source, "available_until", "period", "purchase_deadline")
    available_until = None
    if isinstance(raw_period, str):
        # Keep the source date, normalizing only an unambiguous ISO date.
        try:
            available_until = date.fromisoformat(raw_period[:10]).strftime("%Y/%m/%d")
        except ValueError:
            available_until = raw_period if len(raw_period) >= 8 else None

    product: dict[str, Any] = {
        "id": int(_first(source, "id") or product_id),
        "control": control,
        "name": _first(source, "name", "title"),
        "comments": _first(source, "comments", "comment"),
        "brand_id": _nested_id(brand),
        "category_id": _first(source, "category_id"),
        "price": _first(source, "price"),
        "available_until": available_until,
        "buying_area_id": _nested_id(purchase_area),
        "shipping_area_id": _nested_id(ship_area),
        "images": _api_images(_first(source, "images", "item_images")),
        "shipping_methods": _api_shipping_methods(source.get("shipping_methods")),
        "options": _already_api_options(_first(source, "options")),
        "variants": _already_api_variants(_first(source, "variants")),
    }

    # Numeric IDs and price must be real integers; do not accept display strings.
    for key in ("id", "brand_id", "category_id", "price", "buying_area_id", "shipping_area_id"):
        value = product.get(key)
        if isinstance(value, str) and value.isdigit():
            product[key] = int(value)
    missing = []
    for key in API_REQUIRED:
        value = product.get(key)
        if value is None or value == "" or (key in {"images", "shipping_methods", "options", "variants"} and not isinstance(value, list)):
            missing.append(key)
    if product.get("control") not in {"publish", "draft", "suspend"}:
        missing.append("control(status mapping)")
    if product.get("id") != int(product_id):
        missing.append("id(product ID mismatch)")
    return product, sorted(set(missing))
