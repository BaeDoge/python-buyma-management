from pathlib import Path

import pandas as pd
import pytest

from buyma_price_competitor.reporting import CheckpointResults, write_results


class FakeSheets:
    def __init__(self):
        self.replaced = []
        self.appended = []

    def replace_df(self, name, frame):
        self.replaced.append((name, frame.copy()))

    def append_df(self, name, frame):
        self.appended.append((name, frame.copy()))


class FakeSettings:
    def __init__(self, root: Path):
        self.reports_dir = root / "reports"
        self.google_result_sheet = "api 가격변경 시트"
        self.google_history_sheet = "[5] 최저가 적용이력"
        self.google_api_history_sheet = "[6] 최저가 적용이력-공식API"


@pytest.mark.asyncio
async def test_report_is_appended_to_official_api_history_without_changing_legacy_history(tmp_path):
    settings = FakeSettings(tmp_path)
    sheets = FakeSheets()
    results = [
        {
            "상품ID": "123456789",
            "현재가": 12000,
            "신규가": 11990,
            "적용 여부": True,
            "비고": "BUYMA API 요청 접수",
            "request_uid": "request-1",
        }
    ]
    report_path = tmp_path / "reports" / "report.csv"

    await write_results(
        settings, sheets, results, 1, 0, 0,
        report_path=report_path,
    )

    assert report_path.exists()
    saved = pd.read_csv(report_path, encoding="utf-8-sig")
    assert list(saved.columns) == list(results[0].keys())
    assert saved.iloc[0]["상품ID"] == 123456789

    assert [name for name, _ in sheets.replaced] == ["api 가격변경 시트"]
    assert [name for name, _ in sheets.appended] == ["[6] 최저가 적용이력-공식API"]
    uploaded = sheets.appended[0][1]
    assert list(uploaded.columns) == list(saved.columns)
    assert uploaded.iloc[0]["신규가"] == 11990
    assert uploaded.iloc[0]["request_uid"] == "request-1"


def test_checkpoint_results_persists_each_appended_row(tmp_path):
    path = tmp_path / "reports" / "checkpoint.csv"
    results = CheckpointResults(path)

    results.append({"상품ID": "123", "적용 여부": True})
    results.append({"상품ID": "456", "적용 여부": False})

    saved = pd.read_csv(path, encoding="utf-8-sig")
    assert saved["상품ID"].astype(str).tolist() == ["123", "456"]
