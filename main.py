from pathlib import Path
import runpy, sys
ROOT=Path(__file__).resolve().parent
SRC=ROOT/"app"/"src"
sys.path.insert(0, str(SRC))
runpy.run_path(str(ROOT/"app"/"main.py"), run_name="__main__")
