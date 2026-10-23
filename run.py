#!/usr/bin/env python3
"""Run the suite from the repository root without installing it: ``python run.py <command>``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from branchcut.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
