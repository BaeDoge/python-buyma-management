from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"BUYMA API payload 파일이 없습니다: {path}\n"
            "먼저 migration 명령을 실행하세요."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payloads: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(path)
