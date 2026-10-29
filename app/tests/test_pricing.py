from buyma_price_competitor.pricing import decide


def test_already_at_competitor_minimum():
    result = decide(10_000, 10_000, 10, 100)
    assert result.new_price is None
    assert result.reason == "이미 최저가"


def test_already_below_competitor_minimum():
    result = decide(9_900, 10_000, 10, 100)
    assert result.new_price is None
    assert result.reason == "이미 최저가"


def test_calculates_delta_below_competitor_minimum():
    result = decide(10_080, 10_000, 10, 100)
    assert result.new_price == 9_990
    assert result.change == 90
    assert result.reason == "변경 대상"


def test_change_equal_to_maximum_is_allowed():
    result = decide(10_090, 10_000, 10, 100)
    assert result.new_price == 9_990
    assert result.change == 100
    assert result.reason == "변경 대상"


def test_change_over_maximum_is_skipped():
    result = decide(10_091, 10_000, 10, 100)
    assert result.new_price is None
    assert result.change == 101
    assert result.reason == "가격 차이 초과"


def test_non_positive_new_price_is_skipped():
    result = decide(500, 5, 10, 1_000)
    assert result.new_price is None
    assert result.reason == "신규 가격이 0 이하"
