"""Launch ``hackingtool.py`` in the parent directory (repo root)."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    script = root / "hackingtool.py"
    if not script.is_file():
        print(f"[ERROR] Expected {script}", file=sys.stderr)
        sys.exit(1)
    sys.path.insert(0, str(root))
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
