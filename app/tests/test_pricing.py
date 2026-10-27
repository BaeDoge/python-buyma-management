from buyma_price_competitor.pricing import decide

def test_already_lowest():
    r = decide(10000, 10000, 1000, 5000)
    assert r.new_price is None
    assert r.reason == "이미 최저가"

def test_change():
    r = decide(12000, 10000, 1000, 5000)
    assert r.new_price == 9000
    assert r.change == 3000

def test_max_change():
    r = decide(20000, 10000, 1000, 5000)
    assert r.new_price is None
    assert r.reason == "가격 차이 초과"
