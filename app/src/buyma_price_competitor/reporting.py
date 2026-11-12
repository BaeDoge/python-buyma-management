from __future__ import annotations

from pathlib import Path

import pandas as pd


class CheckpointResults(list):
    """Persist completed product rows so an interrupted run keeps its report."""

    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def checkpoint(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(self).to_csv(self.path, index=False, encoding="utf-8-sig")

    def append(self, item) -> None:
        super().append(item)
        self.checkpoint()


async def write_results(
    settings, sheets, results, changed, already_lowest, no_own,
    *, report_path: Path, logger=None,
):
    """Save the CSV report and publish the same columns/rows to Google Sheets."""
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = pd.DataFrame(results)
    report.to_csv(report_path, index=False, encoding="utf-8-sig")

    if not report.empty:
        try:
            sheets.replace_df(settings.google_result_sheet, report)
            if logger:
                logger.info(
                    "최신 결과를 Google Sheet '%s' 탭에 업로드했습니다.",
                    settings.google_result_sheet,
                )
        except Exception:
            if logger:
                logger.exception("Google Sheet 최신 결과 탭 업로드 실패")

        try:
            sheets.append_df(settings.google_api_history_sheet, report)
            if logger:
                logger.info(
                    "공식 API 실행 보고서를 Google Sheet '%s' 탭에 누적했습니다.",
                    settings.google_api_history_sheet,
                )
        except Exception:
            if logger:
                logger.exception("공식 API 이력 시트 업로드 실패")

    if logger:
        logger.info("CSV 결과 저장: %s", report_path)
    return report_path
