"""Map the captured BUYMA seller-page product schema to Product API.

The mapping below is based on the actual /rorapi/sell/products/{id} fields.
Unknown stock states are rejected; price updates must not silently rewrite inventory.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any


API_REQUIRED = (
    "control", "name", "comments", "brand_id", "category_id", "price",
    "available_until", "buying_area_id", "shipping_area_id", "images",
    "shipping_methods", "options", "variants",
)


def _date(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10]).strftime("%Y/%m/%d")
    except ValueError:
        return None


def _area_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    area = value.get("area_cd")
    city = value.get("city_cd")
    if area in (None, "") or city in (None, ""):
        return None
    return f"{area}{city}"


def _images(source: Any) -> list[dict[str, Any]] | None:
    if not isinstance(source, list) or not source:
        return None
    result = []
    for index, item in enumerate(source, 1):
        if not isinstance(item, dict):
            return None
        # zoom_url is the original full-size BUYMA image; preview_url is fallback.
        path = item.get("zoom_url") or item.get("preview_url")
        if not isinstance(path, str) or not path.startswith("https://"):
            return None
        result.append({"path": path, "position": int(item.get("position") or index)})
    return result


def _options(source: dict[str, Any]) -> list[dict[str, Any]] | None:
    colors = source.get("colors") or []
    sizes = source.get("sizes") or []
    if not isinstance(colors, list) or not isinstance(sizes, list):
        return None
    result: list[dict[str, Any]] = []
    for kind, entries in (("size", sizes), ("color", colors)):
        for position, item in enumerate(entries, 1):
            if not isinstance(item, dict) or item.get("name") in (None, ""):
                return None
            option = {
                "type": kind,
                "value": str(item["name"]),
                "master_id": int(item.get("master_id") or 0),
                "position": position,
            }
            if kind == "size":
                details = item.get("details") or []
                if details:
                    if not isinstance(details, list):
                        return None
                    option["details"] = [
                        {"key": str(d["name"]), "value": str(d["value"])}
                        for d in details
                        if isinstance(d, dict) and d.get("name") and d.get("value") not in (None, "")
                    ]
                    if len(option["details"]) != len(details):
                        return None
            result.append(option)
    # BUYMA API requires options as an array, even for a one-value product.
    return result or None


def _variants(source: dict[str, Any], options: list[dict[str, Any]]) -> tuple[list[dict[str, Any]] | None, int | None, list[str]]:
    colors = source.get("colors") or []
    sizes = source.get("sizes") or []
    matrix = source.get("colorsizes")
    if not isinstance(matrix, list) or not matrix:
        return None, None, ["variants(colorsizes 누락)"]

    color_count = max(1, len(colors))
    size_count = max(1, len(sizes))
    if len(matrix) != color_count or any(not isinstance(row, list) or len(row) != size_count for row in matrix):
        return None, None, ["variants(colorsizes 조합 수 불일치)"]

    size_values = [str(x["name"]) for x in sizes] if sizes else ["FREE"]
    color_values = [str(x["name"]) for x in colors] if colors else ["色指定なし"]
    result: list[dict[str, Any]] = []
    available_count = 0
    for color_index, row in enumerate(matrix):
        for size_index, cell in enumerate(row):
            if not isinstance(cell, dict) or cell.get("selectable") not in (0, 1, False, True):
                return None, None, ["variants(selectable 상태 불명확)"]
            available = int(cell["selectable"]) == 1
            variant_options = []
            if sizes:
                variant_options.append({"type": "size", "value": size_values[size_index]})
            if colors:
                variant_options.append({"type": "color", "value": color_values[color_index]})
            if not variant_options:
                return None, None, ["variants 옵션 연결 실패"]
            result.append({
                "options": variant_options,
                "stock_type": "purchase_for_order" if available else "out_of_stock",
                "stocks": None,
            })
            available_count += int(available)

    if available_count:
        raw_quantity = source.get("capacity_amount")
        try:
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            return None, None, ["order_quantity(capacity_amount 확인 불가)"]
        if quantity < 1:
            return None, None, ["order_quantity(capacity_amount가 1 미만)"]
        return result, quantity, []
    return result, None, []


def convert_source_product(source: dict[str, Any], product_id: str) -> tuple[dict[str, Any], list[str]]:
    """Return (candidate API product, unresolved required fields)."""
    if not isinstance(source, dict):
        raise TypeError("source_product_data must be an object")

    status = str(source.get("status") or "").lower()
    control = {"publish": "publish", "public": "publish",
               "draft": "draft", "buyer_suspended": "suspend"}.get(status)

    brand = source.get("brand")
    brand_id = brand.get("id") if isinstance(brand, dict) else source.get("brand_id")

    raw_images = _images(source.get("item_images"))
    shipping_raw = source.get("shipping_methods")
    shipping_methods = None
    if isinstance(shipping_raw, list):
        shipping_methods = []
        for item in shipping_raw:
            if not isinstance(item, dict) or item.get("id") is None:
                shipping_methods = None
                break
            shipping_methods.append({"shipping_method_id": int(item["id"])})

    options = _options(source)
    variants, order_quantity, variant_errors = _variants(source, options or []) if options else (None, None, ["options(colors/sizes 확인 실패)"])

    purchase_area = _area_id(source.get("purchase_area"))
    shipping_area = _area_id(source.get("shipping_area"))
    duty_map = {"prepaid": "included", "buyer": "refundable", "none": "none"}
    duty = duty_map.get(str(source.get("duty_type") or "").lower())
    if source.get("include_duty") is False:
        duty = "none"

    product: dict[str, Any] = {
        "id": int(product_id),
        "control": control,
        "name": source.get("name"),
        "comments": source.get("comment"),
        "brand_id": int(brand_id) if str(brand_id or "").isdigit() else None,
        "category_id": int(source["category_id"]) if str(source.get("category_id") or "").isdigit() else None,
        "price": int(source["price"]) if str(source.get("price") or "").isdigit() else None,
        "available_until": _date(source.get("period")),
        "buying_area_id": purchase_area,
        "shipping_area_id": shipping_area,
        "images": raw_images,
        "shipping_methods": shipping_methods,
        "options": options,
        "variants": variants,
    }

    optional = {
        "buying_shop_name": source.get("shop_name"),
        "duty": duty,
        "tags": [{"tag_id": int(x["id"])} for x in (source.get("tags") or [])
                 if isinstance(x, dict) and x.get("selected") is True and str(x.get("id", "")).isdigit()],
        "style_numbers": [{"number": x["number"], "memo": x.get("memo", "")}
                          for x in (source.get("style_numbers") or [])
                          if isinstance(x, dict) and x.get("number")],
        "size_unit": source.get("size_unit"),
        "colorsize_comments": source.get("variations_note"),
        "order_quantity": order_quantity,
        "shop_urls": deepcopy(source.get("shop_urls") or []),
    }
    if source.get("size_unit") not in (None, ""):
        product["size_unit"] = source["size_unit"]
    elif source.get("size_unit_id") not in (None, 0, "0"):
        # size_unit_id is an internal numeric master key, not the API string.
        pass
    for key, value in optional.items():
        if value not in (None, [], ""):
            product[key] = deepcopy(value)

    missing = []
    for key in API_REQUIRED:
        value = product.get(key)
        if value is None or value == "" or (key in {"images", "shipping_methods", "options", "variants"} and not isinstance(value, list)):
            missing.append(key)
    if control is None:
        missing.append("control(status mapping)")
    if product["id"] != int(product_id):
        missing.append("id(product ID mismatch)")
    missing.extend(variant_errors)
    return product, sorted(set(missing))
