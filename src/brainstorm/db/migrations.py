"""Numbered SQL migrations (db/migrations/NNN_name.sql) tracked with PRAGMA user_version."""

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_NAME = re.compile(r"^(\d+)_.+\.sql$")


class MigrationError(Exception):
    pass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    found = []
    for path in directory.glob("*.sql"):
        match = _NAME.match(path.name)
        if not match:
            raise MigrationError(f"Bad migration file name: {path.name}")
        found.append(Migration(int(match.group(1)), path.name, path.read_text(encoding="utf-8")))
    found.sort(key=lambda m: m.version)
    if [m.version for m in found] != list(range(1, len(found) + 1)):
        raise MigrationError("Migrations must be numbered 1..N without gaps or duplicates")
    return found


def current_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection, directory: Path = MIGRATIONS_DIR) -> int:
    """Apply every pending migration, each in its own transaction. Returns the new version."""
    migrations = discover(directory)
    latest = migrations[-1].version if migrations else 0
    current = current_version(conn)
    if current > latest:
        raise MigrationError(
            f"Database is version {current} but this app only knows up to {latest}. "
            "It was probably created by a newer version of Brainstorm."
        )
    for migration in migrations:
        if migration.version <= current:
            continue
        try:
            # user_version is set inside the transaction so schema and version change together.
            conn.executescript(
                f"BEGIN;\n{migration.sql}\nPRAGMA user_version = {migration.version};\nCOMMIT;"
            )
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise MigrationError(f"Migration {migration.name} failed: {exc}") from exc
    return latest
