"""Resolve project paths for both `streamlit run` and the packaged .exe."""

from __future__ import annotations

import sys
from pathlib import Path


def bundled_root() -> Path:
    """Read-only bundle root (Home.py, pages/, shipped assets) including PyInstaller _MEIPASS."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def project_root() -> Path:
    """Writable root for SQLite and generated files (next to the .exe when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def db_path() -> Path:
    """SQLite file lives in a writable folder so the demo survives tab switches."""
    return project_root() / "cosmos_soc.db"


def assets_dir() -> Path:
    """Prefer bundled assets; fall back to a writable folder beside the executable."""
    bundled = bundled_root() / "assets"
    if bundled.exists():
        return bundled
    path = project_root() / "assets"
    path.mkdir(parents=True, exist_ok=True)
    return path
