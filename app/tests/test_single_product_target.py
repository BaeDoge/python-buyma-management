from __future__ import annotations

import pandas as pd
import pytest

from buyma_price_competitor.runner import collect_sheet_urls


class FakeSheets:
    def __init__(self, frame):
        self.frame = frame
        self.requested_sheet = None

    def read_df(self, sheet_name):
        self.requested_sheet = sheet_name
        return self.frame


class FakeSettings:
    google_price_sheet = "prices"
    google_url_column = "URL"


def test_urls_are_read_directly_from_sheet_without_id_store():
    sheets = FakeSheets(pd.DataFrame({
        "URL": [
            "https://www.buyma.com/r/item-one/",
            "https://www.buyma.com/r/item-one/",
            None,
            "  https://www.buyma.com/r/item-two/  ",
            "",
        ]
    }))

    assert collect_sheet_urls(sheets, FakeSettings()) == [
        "https://www.buyma.com/r/item-one/",
        "https://www.buyma.com/r/item-two/",
    ]
    assert sheets.requested_sheet == "prices"


def test_sheet_url_collection_supports_limit():
    sheets = FakeSheets(pd.DataFrame({
        "URL": ["https://example.com/1", "https://example.com/2"]
    }))

    assert collect_sheet_urls(sheets, FakeSettings(), limit=1) == [
        "https://example.com/1"
    ]


def test_missing_url_column_fails_clearly():
    sheets = FakeSheets(pd.DataFrame({"other": ["https://example.com"]}))

    with pytest.raises(ValueError, match="URL"):
        collect_sheet_urls(sheets, FakeSettings())


def test_empty_sheet_returns_no_urls():
    sheets = FakeSheets(pd.DataFrame())

    assert collect_sheet_urls(sheets, FakeSettings()) == []
