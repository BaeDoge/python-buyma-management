"""BESTSHIP-only entry point. Runtime config lives beside the executable."""
from pathlib import Path
import sys

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
SOURCE = ROOT / "app" / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from buyma_price_competitor.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
