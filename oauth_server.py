from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/"app"/"src"))
from app.oauth_server import app
