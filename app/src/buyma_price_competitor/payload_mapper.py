"""Convert the captured BUYMA seller edit data to Product API format.

Mappings are based on BUYMA's Product API specification and the observed
/rorapi/sell/products/{id} source schema. Unknown/ambiguous inventory data fails
closed because this is a price-only update and inventory must remain unchanged.
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
    # BUYMA areas.csv IDs consist of area_cd followed by city_cd.
    if not isinstance(value, dict):
        return None
    area, city = value.get("area_cd"), value.get("city_cd")
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
        path = item.get("zoom_url") or item.get("preview_url")
        if not isinstance(path, str) or not path.startswith("https://"):
            return None
        result.append({"path": path, "position": int(item.get("position") or index)})
    return result


def _options(source: dict[str, Any]) -> list[dict[str, Any]] | None:
    colors, sizes = source.get("colors"), source.get("sizes")
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
                if not isinstance(details, list):
                    return None
                if details:
                    mapped = []
                    for detail in details:
                        if not isinstance(detail, dict) or not detail.get("name") or detail.get("value") in (None, ""):
                            return None
                        mapped.append({"key": str(detail["name"]), "value": str(detail["value"])})
                    option["details"] = mapped
            result.append(option)
    # BUYMA requires the options array. The source always contains at least one
    # color/size entry for the captured records; do not invent missing options.
    return result or None


def _variants(source: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, int | None, list[str]]:
    colors, sizes, matrix = source.get("colors"), source.get("sizes"), source.get("colorsizes")
    if not isinstance(colors, list) or not isinstance(sizes, list) or not isinstance(matrix, list) or not matrix:
        return None, None, ["variants(colorsizes 누락)"]

    color_count, size_count = max(1, len(colors)), max(1, len(sizes))
    if len(matrix) != color_count or any(not isinstance(row, list) or len(row) != size_count for row in matrix):
        return None, None, ["variants(colorsizes 조합 수 불일치)"]

    color_names = [str(x.get("name")) for x in colors] if colors else ["色指定なし"]
    size_names = [str(x.get("name")) for x in sizes] if sizes else ["FREE"]
    variants: list[dict[str, Any]] = []
    has_purchase_for_order = False

    for ci, row in enumerate(matrix):
        for si, cell in enumerate(row):
            if not isinstance(cell, dict) or cell.get("selectable") not in (0, 1, False, True):
                return None, None, ["variants(selectable 상태 불명확)"]
            # The seller-page selectable flag indicates whether the combination
            # can be selected. Available combinations use purchase_for_order;
            # unavailable combinations use out_of_stock. Never invent stock-in-hand.
            available = int(cell["selectable"]) == 1
            has_purchase_for_order |= available
            variant_options = []
            if sizes:
                variant_options.append({"type": "size", "value": size_names[si]})
            if colors:
                variant_options.append({"type": "color", "value": color_names[ci]})
            if not variant_options:
                return None, None, ["variants 옵션 연결 실패"]
            variants.append({
                "options": variant_options,
                "stock_type": "purchase_for_order" if available else "out_of_stock",
                "stocks": None,
            })

    if not has_purchase_for_order:
        return variants, None, []
    try:
        quantity = int(source.get("capacity_amount"))
    except (TypeError, ValueError):
        return None, None, ["order_quantity(capacity_amount 확인 불가)"]
    if quantity < 1:
        return None, None, ["order_quantity(capacity_amount가 1 미만)"]
    return variants, quantity, []


def convert_source_product(source: dict[str, Any], product_id: str) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(source, dict):
        raise TypeError("source_product_data must be an object")

    status = str(source.get("status") or "").lower()
    control = {"publish": "publish", "draft": "draft", "buyer_suspended": "suspend"}.get(status)
    brand = source.get("brand")
    brand_id = brand.get("id") if isinstance(brand, dict) else source.get("brand_id")

    images = _images(source.get("item_images"))
    raw_shipping = source.get("shipping_methods")
    shipping_methods = None
    if isinstance(raw_shipping, list):
        shipping_methods = []
        for item in raw_shipping:
            if not isinstance(item, dict) or item.get("id") is None:
                shipping_methods = None
                break
            shipping_methods.append({"shipping_method_id": int(item["id"])})

    options = _options(source)
    variants, order_quantity, variant_errors = _variants(source)

    raw_price = source.get("price")
    product: dict[str, Any] = {
        "id": int(product_id),
        "control": control,
        "name": source.get("name"),
        "comments": source.get("comment"),
        "brand_id": int(brand_id) if str(brand_id or "").isdigit() else None,
        "category_id": int(source["category_id"]) if str(source.get("category_id") or "").isdigit() else None,
        "price": int(raw_price) if str(raw_price or "").isdigit() else None,
        "available_until": _date(source.get("period")),
        "buying_area_id": _area_id(source.get("purchase_area")),
        "shipping_area_id": _area_id(source.get("shipping_area")),
        "images": images,
        "shipping_methods": shipping_methods,
        "options": options,
        "variants": variants,
    }

    duty_map = {"prepaid": "included", "buyer": "refundable", "none": "none"}
    duty = "none" if source.get("include_duty") is False else duty_map.get(str(source.get("duty_type") or "").lower())
    optional = {
        "buying_shop_name": source.get("shop_name"),
        "duty": duty,
        "tags": [{"tag_id": int(x["id"])} for x in (source.get("tags") or [])
                 if isinstance(x, dict) and x.get("selected") is True and str(x.get("id", "")).isdigit()],
        "style_numbers": [{"number": x["number"], "memo": x.get("memo", "")}
                          for x in (source.get("style_numbers") or [])
                          if isinstance(x, dict) and x.get("number")],
        "colorsize_comments": source.get("variations_note"),
        "order_quantity": order_quantity,
        "shop_urls": deepcopy(source.get("shop_urls") or []),
    }
    # size_unit_id is a source master ID, not the API's textual size_unit.
    for key, value in optional.items():
        if value not in (None, [], ""):
            product[key] = deepcopy(value)

    missing = []
    source_id = source.get("id")
    if source_id is None or str(source_id) != str(product_id):
        missing.append("id(product ID mismatch)")
    for key in API_REQUIRED:
        value = product.get(key)
        if value is None or value == "" or (key in {"images", "shipping_methods", "options", "variants"} and not isinstance(value, list)):
            missing.append(key)
    if control is None:
        missing.append("control(status mapping)")
    if product["id"] != int(product_id):
        missing.append("id(product ID mismatch)")
    missing.extend(variant_errors)

    # Do not turn a time-sale price into an ordinary price update. The public
    # listing price can be different from product.price while a campaign is live.
    sale = source.get("timesale")
    if isinstance(sale, dict) and sale.get("status") == "on":
        missing.append("active_timesale(타임세일 종료 후 가격 변경 필요)")

    return product, sorted(set(missing))
