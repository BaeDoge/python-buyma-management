from pathlib import Path
import runpy, sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/"app"/"src"))
runpy.run_path(str(ROOT/"app"/"refresh_prices.py"), run_name="__main__")
