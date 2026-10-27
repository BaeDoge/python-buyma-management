from __future__ import annotations

from pathlib import Path
from typing import Any

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials


class GoogleSheetClient:
    def __init__(self, service_account: Path, scopes: list[str], sheet_url: str):
        if not service_account.exists():
            raise FileNotFoundError(
                f"Google 서비스 계정 파일이 없습니다: {service_account}"
            )
        self.creds = Credentials.from_service_account_file(
            str(service_account), scopes=scopes
        )
        self.client = gspread.authorize(self.creds)
        self.spreadsheet = self.client.open_by_url(sheet_url)

    def read_df(self, sheet_name: str) -> pd.DataFrame:
        worksheet = self.spreadsheet.worksheet(sheet_name)
        return pd.DataFrame(worksheet.get_all_records())

    def replace_df(self, sheet_name: str, df: pd.DataFrame) -> None:
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name, rows=max(1000, len(df) + 10), cols=max(10, len(df.columns) + 2)
            )

        values: list[list[Any]] = [df.columns.tolist()] + df.fillna("").values.tolist()
        worksheet.clear()
        worksheet.update("A1", values)
