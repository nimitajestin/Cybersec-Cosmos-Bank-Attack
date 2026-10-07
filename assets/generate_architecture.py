"""CLI helper: python assets/generate_architecture.py  (offline matplotlib PNG)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.diagram import generate_architecture_png  # noqa: E402

if __name__ == "__main__":
    path = generate_architecture_png()
    print(f"Wrote {path}")
