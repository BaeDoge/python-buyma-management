from datetime import datetime
from zoneinfo import ZoneInfo

import gspread

from buyma_price_competitor.google_sheets import GoogleSheetClient


class FakeWorksheet:
    def __init__(self, records):
        self.records = records

    def get_all_records(self):
        return self.records


class FakeSpreadsheet:
    def __init__(self, worksheets=None):
        self.worksheets_by_name = worksheets or {}

    def worksheet(self, name):
        if name not in self.worksheets_by_name:
            raise gspread.WorksheetNotFound(name)
        return self.worksheets_by_name[name]


def test_next_run_id_increments_the_highest_sequence_for_today():
    client = GoogleSheetClient.__new__(GoogleSheetClient)
    client.spreadsheet = FakeSpreadsheet({
        "실행 이력": FakeWorksheet([
            {"변경 ID": "20261116-001"},
            {"변경 ID": "20261116-003"},
            {"변경 ID": "20261115-009"},
            {"변경 ID": "old-format"},
        ])
    })

    run_id = client.next_run_id(
        "실행 이력",
        datetime(2026, 11, 16, 18, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert run_id == "20261116-004"


def test_next_run_id_starts_at_001_when_history_tab_is_missing():
    client = GoogleSheetClient.__new__(GoogleSheetClient)
    client.spreadsheet = FakeSpreadsheet()

    run_id = client.next_run_id(
        "실행 이력",
        datetime(2026, 11, 16, 18, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert run_id == "20261116-001"
