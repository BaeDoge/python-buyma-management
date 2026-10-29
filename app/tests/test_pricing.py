from buyma_price_competitor.pricing import decide


def test_already_lowest():
    result = decide(10_000, 10_000, 10, 100)
    assert result.new_price is None
    assert result.reason == "이미 최저가"


def test_calculates_price_delta_below_competitor_minimum():
    result = decide(10_080, 10_000, 10, 100)
    assert result.new_price == 9_990
    assert result.change == 90
    assert result.reason == "변경 대상"


def test_change_at_maximum_is_allowed():
    result = decide(10_100, 10_000, 10, 100)
    assert result.new_price == 9_990
    assert result.change == 110
    assert result.reason == "가격 차이 초과"


def test_change_over_maximum_is_skipped():
    result = decide(20_000, 10_000, 10, 100)
    assert result.new_price is None
    assert result.reason == "가격 차이 초과"


def test_non_positive_new_price_is_skipped():
    result = decide(500, 5, 10, 1000)
    assert result.new_price is None
    assert result.reason == "신규 가격이 0 이하"
