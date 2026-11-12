from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else APP_DIR.parent
SRC_DIR = APP_DIR / "src"
for item in (APP_DIR, SRC_DIR):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from buyma_price_competitor.config import Settings
from buyma_price_competitor.logging_utils import setup_logging
from buyma_price_competitor.runner import run_price_competition


def parse_schedule_times(raw: str) -> list[str]:
    """Parse local PC times in HH:MM format, preserving the configured order."""
    values: list[str] = []
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            parsed = datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError(
                f"BUYMA_SCHEDULE_TIMES 값이 잘못되었습니다: {value!r}. HH:MM 형식으로 입력하세요."
            ) from exc
        normalized = parsed.strftime("%H:%M")
        if normalized not in values:
            values.append(normalized)
    if not values:
        raise ValueError("BUYMA_SCHEDULE_TIMES에 실행 시간을 하나 이상 입력하세요.")
    return values


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} 값은 true 또는 false여야 합니다.")


class ScheduleState:
    """Store each scheduled attempt so restarting the EXE will not repeat it."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {"runs": {}}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and isinstance(loaded.get("runs"), dict):
                    self.data = loaded
            except (OSError, json.JSONDecodeError):
                raise RuntimeError(f"예약 실행 기록을 읽을 수 없습니다: {path}")

    def status(self, key: str) -> str | None:
        record = self.data["runs"].get(key)
        return record.get("status") if isinstance(record, dict) else None

    def mark(self, key: str, status: str, **details: Any) -> None:
        self.data["runs"][key] = {
            "status": status,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            **details,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)


class SingleInstance:
    """Keep the lock handle open for the process lifetime."""

    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0)
        if self.handle.read(1) == b"":
            self.handle.seek(0)
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            self.handle.close()
            self.handle = None
            return False

    def release(self) -> None:
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


def run_scheduler() -> int:
    settings = Settings.load()
    logger = setup_logging(settings.logs_dir)

    schedule_times = parse_schedule_times(os.getenv("BUYMA_SCHEDULE_TIMES", "06:00,12:00,18:00,00:00"))
    delta = int(os.getenv("BUYMA_SCHEDULE_PRICE_DELTA", str(settings.price_delta)))
    maximum = int(os.getenv("BUYMA_SCHEDULE_MAX_CHANGE", str(settings.max_change)))
    if delta <= 0 or maximum <= 0:
        raise ValueError("예약 실행 가격 단위와 최대 인하 폭은 1 이상이어야 합니다.")

    scheduled_settings = replace(
        settings,
        headless=env_bool("BUYMA_SCHEDULE_HEADLESS", True),
    )
    state = ScheduleState(settings.root / "data" / "scheduler_runs.json")
    lock = SingleInstance(settings.root / "data" / "scheduler.lock")

    if not lock.acquire():
        logger.error("이미 BUYMA 예약 실행 프로그램이 실행 중입니다.")
        return 2

    logger.info("BUYMA 가격 자동 실행기를 시작했습니다.")
    logger.info("실행 시간(PC 현지 시간): %s", ", ".join(schedule_times))
    logger.info("가격 단위: 경쟁 최저가보다 %s엔 낮게 / 최대 인하 폭 %s엔", delta, maximum)
    logger.info("타임세일 변경: %s", "허용" if settings.allow_timesale_price_update else "제외")
    logger.info("예약 실행 중에는 별도의 키보드 입력을 기다리지 않습니다. 종료는 Ctrl+C입니다.")

    try:
        while True:
            now = datetime.now().astimezone()
            slot = now.strftime("%H:%M")
            key = f"{now.strftime('%Y-%m-%d')}|{slot}"

            if slot in schedule_times and state.status(key) is None:
                # Mark the attempt before starting. A process crash must not cause
                # the same scheduled batch to be sent again after a restart.
                state.mark(key, "running", scheduled_time=slot)
                logger.info("예약 실행 시작: %s", key)
                try:
                    results = asyncio.run(
                        run_price_competition(
                            scheduled_settings,
                            logger,
                            apply=True,
                            price_delta=delta,
                            max_change=maximum,
                            approve_timesale=True,
                            interactive_login=False,
                        )
                    )
                    accepted = sum(
                        1 for row in (results or [])
                        if row.get("적용 여부") is True
                    )
                    state.mark(key, "completed", accepted_requests=accepted)
                    logger.info(
                        "예약 실행 완료: %s / API 요청 접수 %d건",
                        key,
                        accepted,
                    )
                except Exception as exc:
                    state.mark(key, "failed", error=f"{type(exc).__name__}: {exc}")
                    logger.exception("예약 실행 실패: %s", key)

            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("BUYMA 가격 자동 실행기를 종료합니다.")
        return 0
    finally:
        lock.release()


def main() -> int:
    try:
        return run_scheduler()
    except Exception:
        logging.exception("예약 실행기를 시작하지 못했습니다.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
