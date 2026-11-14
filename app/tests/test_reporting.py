import asyncio
from pathlib import Path

import pandas as pd

from buyma_price_competitor.reporting import (
    CheckpointResults,
    _detail_report,
    write_results,
)


class FakeSheets:
    def __init__(self):
        self.replaced = []
        self.appended = []
        self.placed = []

    def index_after(self, sheet_name):
        assert sheet_name == "api 가격변경 시트"
        return 3

    def place_after(self, sheet_name, anchor_name):
        self.placed.append((sheet_name, anchor_name))

    def replace_df(self, name, frame):
        self.replaced.append((name, frame.copy()))

    def append_df(self, name, frame, *, index=None, reset_schema=False):
        self.appended.append((name, frame.copy(), index, reset_schema))


class FakeSettings:
    def __init__(self, root: Path):
        self.reports_dir = root / "reports"
        self.google_result_sheet = "api 가격변경 시트"
        self.google_api_history_sheet = "[6] 최저가 적용이력-공식API"
        self.google_application_history_sheet = "api 가격변경 시트 이력"


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
        },
        {
            "상품ID": "789",
            "현재가": 342449,
            "화면가": 342449,
            "적용 여부": False,
            "비고": (
                "공개 표시 가격과 실제 商品価格 불일치: "
                "화면가=342,449, 商品価格=622,826. "
                "BUYMA 할인/타임세일 가능성으로 제외 "
                "(BUYMA_ALLOW_TIMESALE_PRICE_UPDATE=false)"
            ),
        },
    ])

    assert "비고" not in report.columns
    assert "처리 내용" in report.columns
    assert "1회 최대 인하 금액" in report.iloc[0]["처리 내용"]
    assert report.iloc[1]["처리 내용"] == "BUYMA에 가격 변경 요청을 접수했습니다."
    assert "화면 표시 가격과 판매자 실제 상품 가격이 다릅니다" in report.iloc[2]["처리 내용"]


def test_run_history_appends_one_summary_row_and_resets_old_layout(tmp_path):
    settings = FakeSettings(tmp_path)
    sheets = FakeSheets()
    results = [
        {
            "URL": "https://www.buyma.com/item/123/",
            "상품ID": "123",
            "현재가": 12000,
            "신규가": 11990,
            "적용 여부": True,
            "비고": "BUYMA API 요청 접수",
            "request_uid": "request-1",
        },
        {
            "URL": "https://www.buyma.com/item/456/",
            "상품ID": "456",
            "현재가": 15000,
            "新規": None,
            "적용 여부": False,
            "비고": "이미 최저가",
        },
    ]
    summary = {
        "실행 ID": "20261114_120000",
        "실행 구분": "예약 실행",
        "실행 시작 시각": "2026-11-14 12:00:00",
        "실행 종료 시각": "2026-11-14 12:02:00",
        "등록 URL 수": 10,
        "확인한 URL 수": 10,
        "가격 확인된 상품 수": 76,
        "BestShip 상품 수": 2,
        "변경 요청 접수 수": 1,
        "변경하지 않은 BestShip 상품 수": 1,
        "변경된 상품 ID 목록": "123",
        "변경된 상품 URL 목록": "https://www.buyma.com/item/123/",
        "가격 비교 기준": "경쟁 최저가보다 10엔 낮게",
        "1회 최대 인하 폭": "50엔",
        "타임세일 상품 처리": "제외",
        "실행 결과": "가격 변경 요청 1개 접수",
    }

    report_path = tmp_path / "reports" / "report.csv"
    asyncio.run(write_results(
        settings, sheets, results, 1, 0, 0,
        report_path=report_path,
        run_summary=summary,
    ))

    assert report_path.exists()
    saved = pd.read_csv(report_path, encoding="utf-8-sig")
    assert "처리 내용" in saved.columns
    assert "비고" not in saved.columns
    assert saved.iloc[0]["처리 내용"] == "BUYMA에 가격 변경 요청을 접수했습니다."

    assert [name for name, _ in sheets.replaced] == ["api 가격변경 시트"]
    assert len(sheets.appended) == 2
    assert sheets.appended[0][0] == "[6] 최저가 적용이력-공식API"
    assert sheets.appended[1][0] == "api 가격변경 시트 이력"

    history = sheets.appended[1][1]
    assert len(history) == 1
    assert history.iloc[0]["실행 구분"] == "예약 실행"
    assert history.iloc[0]["가격 확인된 상품 수"] == 76
    assert history.iloc[0]["변경 요청 접수 수"] == 1
    assert "item/123/" in history.iloc[0]["변경된 상품 URL 목록"]
    assert sheets.appended[1][2] == 3
    assert sheets.appended[1][3] is True
    assert sheets.placed == [
        ("api 가격변경 시트 이력", "api 가격변경 시트")
    ]


def test_empty_run_still_records_execution_summary(tmp_path):
    settings = FakeSettings(tmp_path)
    sheets = FakeSheets()
    summary = {
        "실행 ID": "20261114_000000",
        "실행 구분": "전체 가격 비교",
        "등록 URL 수": 0,
        "변경 요청 접수 수": 0,
    }

    asyncio.run(write_results(
        settings, sheets, [], 0, 0, 0,
        report_path=tmp_path / "reports" / "empty.csv",
        run_summary=summary,
    ))

    assert sheets.replaced[0][0] == "api 가격변경 시트"
    assert list(sheets.replaced[0][1].columns) == [
        "URL", "상품ID", "변경 여부", "처리 내용"
    ]
    assert len(sheets.appended) == 1
    assert sheets.appended[0][0] == "api 가격변경 시트 이력"
    assert len(sheets.appended[0][1]) == 1


def test_checkpoint_results_persists_each_appended_row(tmp_path):
    path = tmp_path / "reports" / "checkpoint.csv"
    results = CheckpointResults(path)

    results.append({"상품ID": "123", "적용 여부": True})
    results.append({"상품ID": "456", "적용 여부": False})

    saved = pd.read_csv(path, encoding="utf-8-sig")
    assert saved["상품ID"].astype(str).tolist() == ["123", "456"]
