from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PriceDecision:
    current_price: int
    competitor_min: int
    new_price: int | None
    change: int | None
    reason: str


def decide(current_price: int, competitor_min: int, delta: int, max_change: int) -> PriceDecision:
    if current_price <= competitor_min:
        return PriceDecision(current_price, competitor_min, None, None, "이미 최저가")

    new_price = competitor_min - delta
    change = current_price - new_price

    if new_price <= 0:
        return PriceDecision(current_price, competitor_min, None, change, "신규 가격이 0 이하")

    if change > max_change:
        return PriceDecision(current_price, competitor_min, None, change, "가격 차이 초과")

    return PriceDecision(current_price, competitor_min, new_price, change, "변경 대상")
