"""Filesystem locations. Data lives outside the install folder so upgrades never touch it."""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths

DATA_DIR_ENV = "BRAINSTORM_DATA_DIR"


def data_dir() -> Path:
    """OS app-data folder (override with BRAINSTORM_DATA_DIR for dev and tests)."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        path = Path(override)
    else:
        location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        path = Path(location)
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "brainstorm.db"


def assets_dir() -> Path:
    path = data_dir() / "assets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def qml_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)  # PyInstaller (Phase 12)
    root = Path(base) / "brainstorm" if base else Path(__file__).parent
    return root / "qml"
