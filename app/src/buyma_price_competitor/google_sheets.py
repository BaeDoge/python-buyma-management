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

    def append_df(self, sheet_name: str, df: pd.DataFrame) -> None:
        """Append execution history without clearing earlier runs."""
        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name,
                rows=max(1000, len(df) + 10),
                cols=max(10, len(df.columns) + 2),
            )

        incoming_headers = [str(column) for column in df.columns]
        existing_values = worksheet.get_all_values()

        if existing_values:
            headers = [str(column) for column in existing_values[0]]
            for column in incoming_headers:
                if column not in headers:
                    headers.append(column)
        else:
            headers = incoming_headers

        if worksheet.col_count < len(headers):
            worksheet.add_cols(len(headers) - worksheet.col_count)

        required_rows = len(existing_values) + len(df) + 1
        if worksheet.row_count < required_rows:
            worksheet.add_rows(required_rows - worksheet.row_count)

        if not existing_values or headers != existing_values[0]:
            worksheet.update("A1", [headers])

        rows = []
        for record in df.to_dict(orient="records"):
            row = []
            for header in headers:
                value = record.get(header, "")
                if value is None or (
                    not isinstance(value, (dict, list)) and pd.isna(value)
                ):
                    row.append("")
                else:
                    row.append(str(value))
            rows.append(row)

        if rows:
            worksheet.append_rows(rows, value_input_option="USER_ENTERED")
