from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.database import create_all
from backend.services.seed_service import seed_incidents


def main() -> None:
    create_all()
    seed_incidents(replace_existing=True)


if __name__ == "__main__":
    main()
