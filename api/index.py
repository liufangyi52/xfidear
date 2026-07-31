import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "Xfplus"
DATABASE_URL = "sqlite:////tmp/xfidear-demo.db"
if os.name == "nt":
    DATABASE_URL = f"sqlite:///{Path(tempfile.gettempdir()) / 'xfidear-demo.db'}"

sys.path.insert(0, str(APP_ROOT))
os.environ["DATABASE_URL"] = DATABASE_URL

from backend.main import app
from backend.services.seed_service import initialize_database


# Vercel invokes the exported ASGI app directly, so lifespan startup is not
# guaranteed to run before an API request. Seed the temporary demo database now.
initialize_database()
