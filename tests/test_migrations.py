import sqlite3

import pytest

from brainstorm.db.connection import connect
from brainstorm.db.migrations import MigrationError, current_version, discover, migrate


def tables(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {r["name"] for r in rows}


def test_fresh_database_is_migrated_to_latest():
    conn = connect(":memory:")
    assert current_version(conn) == 0
    latest = migrate(conn)
    assert latest == discover()[-1].version
    assert current_version(conn) == latest
    assert {"spaces", "nodes"} <= tables(conn)


def test_migrate_is_idempotent():
    conn = connect(":memory:")
    migrate(conn)
    migrate(conn)
    assert current_version(conn) == discover()[-1].version


def test_foreign_keys_are_enforced():
    conn = connect(":memory:")
    migrate(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO nodes (id, space_id, kind, created_at, updated_at)"
            " VALUES ('n', 'missing', 'note', 't', 't')"
        )


def test_only_one_global_space_allowed():
    conn = connect(":memory:")
    migrate(conn)
    insert = "INSERT INTO spaces VALUES (?, 'global', 'Board', 't', 't', NULL)"
    conn.execute(insert, ("a",))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(insert, ("b",))


def test_failed_migration_rolls_back_and_keeps_version(tmp_path):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE a (id INTEGER);")
    (tmp_path / "002_bad.sql").write_text("CREATE TABLE b (id INTEGER); NOT VALID SQL;")
    conn = connect(":memory:")
    with pytest.raises(MigrationError):
        migrate(conn, tmp_path)
    assert current_version(conn) == 1
    assert "a" in tables(conn)
    assert "b" not in tables(conn)


def test_newer_database_is_rejected(tmp_path):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE a (id INTEGER);")
    conn = connect(":memory:")
    conn.execute("PRAGMA user_version = 5")
    with pytest.raises(MigrationError, match="newer"):
        migrate(conn, tmp_path)


def test_gaps_in_numbering_are_rejected(tmp_path):
    (tmp_path / "001_a.sql").write_text("SELECT 1;")
    (tmp_path / "003_c.sql").write_text("SELECT 1;")
    with pytest.raises(MigrationError):
        discover(tmp_path)
