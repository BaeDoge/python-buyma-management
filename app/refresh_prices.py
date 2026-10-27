"""Recurring BUYMA price comparison/update entry point.

Default mode is DRY RUN. Use --apply only after the payload and one-product
API update have been verified. This entry point never calls payload_migration
or performs BUYMA web login.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
SRC = APP_DIR / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if APP_DIR.is_dir() and str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from main import main  # noqa: E402

if __name__ == "__main__":
    main()
