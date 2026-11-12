from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from scheduler import ScheduleState, parse_schedule_times


def test_parse_schedule_times_normalizes_and_deduplicates_values():
    assert parse_schedule_times("06:00, 12:30,06:00,00:00") == [
        "06:00",
        "12:30",
        "00:00",
    ]


@pytest.mark.parametrize("value", ["", "25:00", "12:60", "6:00", "noon"])
def test_parse_schedule_times_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        parse_schedule_times(value)


def test_schedule_state_persists_attempt_and_completion(tmp_path):
    path = tmp_path / "data" / "scheduler_runs.json"
    state = ScheduleState(path)
    key = "2026-11-13|06:00"

    assert state.status(key) is None
    state.mark(key, "running", scheduled_time="06:00")
    assert ScheduleState(path).status(key) == "running"

    state.mark(key, "completed", accepted_requests=4)
    reloaded = ScheduleState(path)
    assert reloaded.status(key) == "completed"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["runs"][key]["accepted_requests"] == 4
