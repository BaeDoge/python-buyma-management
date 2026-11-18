import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import gspread

import pandas as pd

from buyma_price_competitor.google_sheets import GoogleSheetClient
from buyma_price_competitor.reporting import (
    CheckpointResults,
    _detail_report,
    write_results,
)


class FakeSheets:
    def __init__(self):
        self.appended = []
        self.cleaned = []

    def append_df(self, name, frame, *, index=None, reset_schema=False):
        self.appended.append((name, frame.copy(), reset_schema))

    def remove_legacy_output_sheets(self, keep):
        self.cleaned.append(set(keep))
        return ["api 가격변경 시트", "[6] 최저가 적용이력-공식API"]


class FakeSettings:
    def __init__(self, root: Path):
        self.reports_dir = root / "reports"
        self.google_run_history_sheet = "실행 이력"
        self.google_detail_history_sheet = "실행 상세이력"


def test_detail_report_uses_plain_korean_processing_reasons():
    report = _detail_report([
        {
            "상품ID": "123",
            "현재가": 12000,
            "최저가": 11900,
            "신규가": None,
            "적용 여부": False,
            "비고": "가격 차이 초과",
        },
        {
            "상품ID": "456",
            "현재가": 15000,
            "최저가": 14900,
            "신규가": 14890,
            "적용 여부": True,
            "비고": "BUYMA API 요청 접수: 15,000 -> 14,890",
            "request_uid": "request-1",
        },
    ])

    assert "비고" not in report.columns
    assert "처리 내용" in report.columns
    assert "1회 최대 인하 금액" in report.iloc[0]["처리 내용"]
    assert report.iloc[1]["처리 내용"] == "BUYMA에 가격 변경 요청을 접수했습니다."
    assert "변경 요청 접수 여부" in report.columns
    assert "BUYMA 요청 ID" in report.columns


def test_write_results_appends_one_summary_and_product_rows_linked_by_change_id(tmp_path):
    settings = FakeSettings(tmp_path)
    sheets = FakeSheets()
    results = [
        {
            "URL": "https://www.buyma.com/item/123/",
            "상품ID": "123",
            "상품명": "상품 A",
            "현재가": 12000,
            "최저가": 11990,
            "신규가": 11980,
            "적용 여부": True,
            "비고": "BUYMA API 요청 접수",
            "request_uid": "request-1",
        },
        {
            "URL": "https://www.buyma.com/item/456/",
            "상품ID": "456",
            "상품명": "상품 B",
            "현재가": 15000,
            "최저가": 15000,
            "신규가": None,
            "적용 여부": None,
            "비고": "이미 최저가",
        },
    ]
    summary = {
        "변경 ID": "20261116-001",
        "실행 구분": "예약 실행",
        "실행 시작 시각": "2026-11-16 12:00:00",
        "실행 종료 시각": "2026-11-16 12:02:00",
        "최저가 시트 등록 URL 수": 10,
        "확인한 URL 수": 10,
        "전체 조회 상품 수": 76,
        "BestShip 상품 수": 2,
        "이미 최저가 상품 수": 1,
        "가격 변경 요청 수": 1,
        "변경하지 않은 BestShip 상품 수": 0,
        "가격 비교 기준": "경쟁 최저가보다 10엔 낮게",
        "1회 최대 인하 폭": "50엔",
        "타임세일 상품 처리": "제외",
    }

    report_path = tmp_path / "reports" / "report.csv"
    asyncio.run(write_results(
        settings, sheets, results, 1, 1, 0,
        report_path=report_path,
        run_summary=summary,
    ))

    assert report_path.exists()
    saved = pd.read_csv(report_path, encoding="utf-8-sig")
    assert saved["변경 ID"].tolist() == ["20261116-001", "20261116-001"]
    assert "처리 내용" in saved.columns
    assert "비고" not in saved.columns

    # 출력 시트는 두 개뿐이며, 실행 이력은 한 행, 상세이력은 상품별 한 행이다.
    assert [item[0] for item in sheets.appended] == ["실행 이력", "실행 상세이력"]
    run_history = sheets.appended[0][1]
    detail_history = sheets.appended[1][1]
    assert sheets.appended[0][2] is True
    assert sheets.appended[1][2] is True
    assert sheets.cleaned == [{"실행 이력", "실행 상세이력"}]

    assert len(run_history) == 1
    assert run_history.iloc[0]["변경 ID"] == "20261116-001"
    assert run_history.iloc[0]["최저가 시트 등록 URL 수"] == 10
    assert run_history.iloc[0]["이미 최저가 상품 수"] == 1
    assert run_history.iloc[0]["가격 변경 요청 수"] == 1

    assert len(detail_history) == 2
    assert detail_history["변경 ID"].tolist() == ["20261116-001", "20261116-001"]
    assert detail_history["상품ID"].tolist() == ["123", "456"]
    assert detail_history.iloc[0]["현재가"] == 12000
    assert detail_history.iloc[0]["신규가"] == 11980


def test_empty_run_still_appends_one_run_row_without_empty_detail_row(tmp_path):
    settings = FakeSettings(tmp_path)
    sheets = FakeSheets()
    summary = {
        "변경 ID": "20261116-002",
        "실행 구분": "전체 가격 비교",
        "최저가 시트 등록 URL 수": 0,
        "이미 최저가 상품 수": 0,
        "가격 변경 요청 수": 0,
    }

    asyncio.run(write_results(
        settings, sheets, [], 0, 0, 0,
        report_path=tmp_path / "reports" / "empty.csv",
        run_summary=summary,
    ))

    assert [item[0] for item in sheets.appended] == ["실행 이력", "실행 상세이력"]
    assert len(sheets.appended[0][1]) == 1
    assert sheets.appended[0][1].iloc[0]["변경 ID"] == "20261116-002"
    assert len(sheets.appended[1][1]) == 0
    assert sheets.cleaned == [{"실행 이력", "실행 상세이력"}]


def test_checkpoint_results_persists_each_appended_row(tmp_path):
    path = tmp_path / "reports" / "checkpoint.csv"
    results = CheckpointResults(path)

    results.append({"상품ID": "123", "적용 여부": True})
    results.append({"상품ID": "456", "적용 여부": False})

    saved = pd.read_csv(path, encoding="utf-8-sig")
    assert saved["상품ID"].astype(str).tolist() == ["123", "456"]


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



def test_detail_history_keeps_a_fixed_column_layout_for_optional_fields(tmp_path):
    settings = FakeSettings(tmp_path)
    first_sheets = FakeSheets()
    first_results = [{
        "URL": "https://www.buyma.com/item/123/",
        "상품ID": "123",
        "현재가": 12000,
        "신규가": 11990,
        "적용 여부": True,
        "비고": "BUYMA API 요청 접수",
    }]
    summary = {
        "변경 ID": "20261116-003",
        "실행 구분": "전체 가격 변경",
    }

    asyncio.run(write_results(
        settings, first_sheets, first_results, 1, 0, 0,
        report_path=tmp_path / "reports" / "first.csv",
        run_summary=summary,
    ))

    second_sheets = FakeSheets()
    second_results = [{
        "URL": "https://www.buyma.com/item/456/",
        "상품ID": "456",
        "현재가": 15000,
        "화면가": 14000,
        "신규가": 14990,
        "적용 여부": False,
        "적용일시": "2026-11-16 12:00:00",
        "request_uid": None,
        "비고": "표시 가격과 실제 가격이 달라 제외",
    }]

    asyncio.run(write_results(
        settings, second_sheets, second_results, 0, 0, 0,
        report_path=tmp_path / "reports" / "second.csv",
        run_summary={"변경 ID": "20261116-004", "실행 구분": "전체 가격 비교"},
    ))

    first_detail = first_sheets.appended[1][1]
    second_detail = second_sheets.appended[1][1]
    assert list(first_detail.columns) == list(second_detail.columns)
    assert first_detail["변경 ID"].tolist() == ["20261116-003"]
    assert second_detail["변경 ID"].tolist() == ["20261116-004"]
    assert second_detail.iloc[0]["화면가"] == 14000
