import sqlite3
from pathlib import Path


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the database. Use ":memory:" for tests."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
