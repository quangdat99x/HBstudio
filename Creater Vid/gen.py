"""Asset generator for headless turns: "$CREATER_PYTHON" "$GEN_PY" <command> --help (see creater/gen.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from creater.gen import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
