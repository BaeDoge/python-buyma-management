from __future__ import annotations

from datetime import datetime
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


def _is_true(value) -> bool:
    return value is True or str(value).strip().lower() in {"true", "1"}


def _friendly_reason(value: object, *, applied: bool = False) -> str:
    if applied:
        return "BUYMA에 가격 변경 요청을 접수했습니다."

    reason = str(value or "").strip()
    if not reason:
        return "가격을 변경하지 않았습니다."

    exact = {
        "이미 최저가": "현재 판매 가격이 경쟁 판매자 최저가와 같거나 낮습니다.",
        "가격 차이 초과": "경쟁 최저가에 맞추려면 설정한 1회 최대 인하 금액을 넘어 이번에는 변경하지 않았습니다.",
        "신규 가격이 0 이하": "설정한 가격 차이를 적용하면 새 가격이 1엔 미만이 되어 변경하지 않았습니다.",
        "변경 대상": "설정한 가격 변경 기준에 해당합니다.",
        "상품 없음": "해당 페이지에서 가격을 확인할 수 있는 상품을 찾지 못했습니다.",
        "경쟁 판매자 없음": "비교할 다른 판매자의 상품이 없어 가격을 계산하지 않았습니다.",
        "BestShip 상품이 없습니다.": "해당 페이지에서 BestShip 판매자 상품을 찾지 못했습니다.",
        "공개 페이지 접속 실패": "BUYMA 상품 페이지를 열지 못했습니다. URL이나 페이지 상태를 확인해 주세요.",
        "타임세일 가격 변경 후보: 실제 商品価格 확인은 전체 변경 실행 시 진행": "미리보기에서는 타임세일 상품의 판매자 실제 가격을 확인하지 않아 변경하지 않았습니다.",
    }
    if reason in exact:
        return exact[reason]

    if reason.startswith("DRY RUN / "):
        inner = reason.removeprefix("DRY RUN / ").strip()
        return "미리보기 결과, " + exact.get(inner, inner) + " 실제 가격은 변경하지 않았습니다."

    if reason.startswith("공개 페이지 처리 실패:"):
        return "BUYMA 페이지 정보를 읽지 못해 변경하지 않았습니다. 다시 실행해 확인해 주세요."

    if reason.startswith("변경하지 않았습니다:") or reason.startswith("BUYMA API 가격 변경 오류:") or reason.startswith("할인/타임세일 API 변경 실패:"):
        detail = reason.split(":", 1)[1].strip()
        if "HTTP 401" in detail:
            return "BUYMA 인증 정보가 만료되었거나 유효하지 않아 변경하지 않았습니다. 다시 로그인하거나 API 토큰을 확인해 주세요."
        if "HTTP 403" in detail:
            return "현재 BUYMA 계정에 해당 상품을 변경할 권한이 없어 변경하지 않았습니다."
        if "HTTP 422" in detail:
            return "BUYMA에서 상품 정보를 확인한 결과 변경할 수 없는 항목이 있습니다. 상품 정보와 옵션을 확인해 주세요."
        if "HTTP 429" in detail:
            return "BUYMA 요청 횟수 제한에 도달해 변경하지 않았습니다. 다음 실행 때 다시 확인해 주세요."
        if any(code in detail for code in ("HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")):
            return "BUYMA 서비스가 일시적으로 응답하지 않아 변경하지 않았습니다. 다음 실행 때 다시 확인해 주세요."
        if "상품 ID 불일치" in detail or "상품ID 불일치" in detail:
            return "판매자 화면에서 확인한 상품 번호가 대상 상품과 달라 변경하지 않았습니다."
        if "API 변환 필드가 부족" in detail or "필수 필드 누락" in detail:
            return "가격 변경에 필요한 상품 정보 일부를 판매자 화면에서 확인하지 못했습니다."
        if "판매자 페이지" in detail or "판매자 편집 화면" in detail:
            return "판매자 편집 화면에서 최신 상품 정보를 확인하지 못해 변경하지 않았습니다."
        if "商品価格" in detail and ("비어" in detail or "0 이하" in detail):
            return "판매자 화면에서 실제 상품 가격을 확인하지 못해 변경하지 않았습니다."
        return f"상품 정보를 확인하는 중 변경하지 않았습니다. 상세 내용: {detail}"

    if reason.startswith("공개 표시 가격과 실제 商品価格 불일치:"):
        return reason.replace(
            "공개 표시 가격과 실제 商品価格 불일치:",
            "BUYMA 화면 표시 가격과 판매자 실제 상품 가격이 다릅니다:",
        ).replace(
            "BUYMA 할인/타임세일 가능성으로 제외",
            "할인 또는 타임세일 가격일 수 있어 변경하지 않았습니다.",
        ).replace(
            " (BUYMA_ALLOW_TIMESALE_PRICE_UPDATE=false)",
            "",
        )

    if "미리보기 가격과" in reason and "달라" in reason:
        return "미리보기 이후 가격이 달라졌습니다. 최신 가격으로 다시 미리보기를 진행해 주세요."

    if "로그인 세션" in reason or "로그인 검증" in reason:
        return "BUYMA 판매자 로그인이 확인되지 않아 변경하지 않았습니다. 다시 로그인한 뒤 실행해 주세요."

    if "타임세일 표시 상품" in reason:
        return "타임세일 표시 중인 상품은 설정에서 타임세일 변경을 허용하지 않아 제외했습니다."

    if "BestShip 상품" in reason and ("없습니다" in reason or "확인되지 않아" in reason):
        return "해당 URL에서 BestShip 판매자 상품을 확인하지 못했습니다."

    if reason.startswith("할인/타임세일 상품 실시간 가격 확인 실패:") or reason.startswith("타임세일 상품의 판매자 실제 가격과 상품 정보를 확인하지 못해 변경하지 않았습니다:"):
        return "타임세일 상품의 판매자 실제 가격이나 상품 정보를 확인하지 못해 변경하지 않았습니다."
    if "타임세일 가격 변경 취소" in reason or "최종 승인 문구 불일치" in reason:
        return "타임세일 상품은 이번 실행에서 변경하지 않도록 선택했습니다."

    if reason.startswith("판매자 페이지에서"):
        return "판매자 상품 정보를 확인하지 못해 변경하지 않았습니다."

    if reason.startswith("최신 원본 데이터의 API 변환 필드가 부족합니다:"):
        return "가격 변경에 필요한 상품 정보를 판매자 편집 화면에서 모두 확인하지 못했습니다."

    if reason.startswith("실제 商品價格 기준 변경 제외:"):
        return "판매자 실제 가격을 기준으로 계산한 결과, 설정한 가격 변경 조건에 해당하지 않습니다."

    if reason.startswith("미리보기 결과"):
        return reason

    return reason


def _detail_report(results) -> pd.DataFrame:
    report = pd.DataFrame(results)
    if report.empty:
        return report

    if "비고" in report.columns:
        report = report.rename(columns={"비고": "처리 내용"})

    if "처리 내용" in report.columns:
        applied_values = report.get("적용 여부", pd.Series(False, index=report.index))
        report["처리 내용"] = [
            _friendly_reason(reason, applied=_is_true(applied))
            for reason, applied in zip(report["처리 내용"], applied_values)
        ]

    if "원본 데이터 조회" in report.columns:
        report = report.rename(columns={"원본 데이터 조회": "상품 정보 확인"})
        report["상품 정보 확인"] = report["상품 정보 확인"].replace({
            "실시간 조회 및 필수 필드 검증 완료": "판매자 화면에서 최신 상품 정보를 확인했습니다.",
            "실시간 商品価格 확인 및 API 필수 필드 검증 완료": "판매자 화면에서 실제 상품 가격과 정보를 확인했습니다.",
        })

    report = report.rename(columns={
        "적용 여부": "변경 요청 접수 여부",
        "적용일시": "요청 기록 시각",
        "request_uid": "BUYMA 요청 ID",
        "request_received_at": "BUYMA 응답 접수 시각",
    })
    return report


async def write_results(
    settings,
    sheets,
    results,
    changed,
    already_lowest,
    no_own,
    *,
    report_path: Path,
    run_summary: dict | None = None,
    logger=None,
):
    """Append one run summary and its product rows to two linked history tabs."""
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = _detail_report(results)
    if report.empty:
        report = pd.DataFrame(columns=[
            "URL", "상품ID", "상품명", "현재가", "최저가", "신규가",
            "변경 요청 접수 여부", "처리 내용", "BUYMA 요청 ID",
        ])

    summary_values = dict(run_summary or {})
    run_id = str(summary_values.get("변경 ID", "")).strip()
    if not run_id:
        raise ValueError("실행 이력에 사용할 변경 ID가 없습니다.")

    report.insert(0, "변경 ID", run_id)
    report.to_csv(report_path, index=False, encoding="utf-8-sig")

    # 실행 이력에는 실행당 정확히 한 행만 추가합니다.
    summary = pd.DataFrame([summary_values])
    try:
        sheets.append_df(settings.google_run_history_sheet, summary)
        if logger:
            logger.info(
                "실행 이력을 '%s' 탭에 기록했습니다. 변경 ID=%s",
                settings.google_run_history_sheet,
                run_id,
            )
    except Exception:
        if logger:
            logger.exception("실행 이력을 Google Sheets에 저장하지 못했습니다.")
        raise

    # 실행 상세이력에는 상품별 한 행을 추가하고, 같은 변경 ID로 실행 이력과 연결합니다.
    if not report.empty and len(results) > 0:
        try:
            sheets.append_df(settings.google_detail_history_sheet, report)
            if logger:
                logger.info(
                    "상품별 상세이력을 '%s' 탭에 기록했습니다. 변경 ID=%s / %s건",
                    settings.google_detail_history_sheet,
                    run_id,
                    len(report),
                )
        except Exception:
            if logger:
                logger.exception("상품별 상세이력을 Google Sheets에 저장하지 못했습니다.")
            raise

    if logger:
        logger.info("상품별 CSV 보고서 저장: %s", report_path)
    return report_path
