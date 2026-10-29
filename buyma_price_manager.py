from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "app"))
runpy.run_path(str(ROOT / "app" / "manager.py"), run_name="__main__")
