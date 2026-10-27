from buyma_price_competitor.public_products import normalize_seller
from buyma_price_competitor.public_products import extract_seller_id

def test_seller_id():
    assert extract_seller_id("/buyer/12217668.html") == "12217668"

def test_seller_name_normalization():
    assert normalize_seller(" BestShip ") == normalize_seller("BestShip")
