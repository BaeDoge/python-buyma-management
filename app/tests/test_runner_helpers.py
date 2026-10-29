import pandas as pd

from buyma_price_competitor.runner import _sheet_urls


def test_sheet_urls_ignores_blank_and_duplicate_values():
    frame = pd.DataFrame({"URL": [
        "https://www.buyma.com/item/1",
        " ",
        "https://www.buyma.com/item/1",
        None,
        "https://www.buyma.com/item/2",
    ]})

    assert _sheet_urls(frame, "URL", None) == [
        "https://www.buyma.com/item/1",
        "https://www.buyma.com/item/2",
    ]


def test_sheet_urls_applies_limit_after_deduplication():
    frame = pd.DataFrame({"URL": ["first", "first", "second", "third"]})
    assert _sheet_urls(frame, "URL", 2) == ["first", "second"]
