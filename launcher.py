"""
Desktop launcher for the packaged Streamlit app (used by PyInstaller).

Security concept: the SOC console must run fully offline after install —
this wrapper never passes a telemetry URL or remote endpoint.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _root() -> Path:
    """Folder that contains app.py (PyInstaller _MEIPASS when frozen)."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main() -> int:
    """Start Streamlit against the bundled Home.py on localhost only."""
    root = _root()
    os.chdir(root)
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    app = root / "Home.py"
    if not app.exists():
        alt = Path(sys.executable).resolve().parent / "Home.py"
        if alt.exists():
            os.chdir(alt.parent)
            app = alt
        else:
            raise SystemExit(f"Cannot find Home.py (looked in {root})")

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        str(app),
        "--global.developmentMode=false",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.port=8501",
        "--server.address=127.0.0.1",
    ]
    return stcli.main()


if __name__ == "__main__":
    raise SystemExit(main())
