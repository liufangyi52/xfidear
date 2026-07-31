import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "Xfplus"
DATABASE_URL = "sqlite:////tmp/xfidear-demo.db"

sys.path.insert(0, str(APP_ROOT))
os.environ["DATABASE_URL"] = DATABASE_URL

from backend.main import app
