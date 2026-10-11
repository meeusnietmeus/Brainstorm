import json
import sqlite3
from typing import Any

from brainstorm.domain import Space, new_id, utc_now
from brainstorm.domain.space import GLOBAL


def _from_row(row: sqlite3.Row) -> Space:
    data = dict(row)
    if data["view_state"] is not None:
        data["view_state"] = json.loads(data["view_state"])
    return Space(**data)


class SpaceRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def add(self, space: Space) -> Space:
        view_state = None if space.view_state is None else json.dumps(space.view_state)
        self._conn.execute(
            "INSERT INTO spaces (id, kind, name, created_at, updated_at, archived_at, view_state)"
            " VALUES (:id, :kind, :name, :created_at, :updated_at, :archived_at, :view_state)",
            {**{s: getattr(space, s) for s in space.__slots__}, "view_state": view_state},
        )
        self._conn.commit()
        return space

    def get(self, space_id: str) -> Space | None:
        row = self._conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()
        return _from_row(row) if row else None

    def list(self, include_archived: bool = False) -> list[Space]:
        sql = "SELECT * FROM spaces"
        if not include_archived:
            sql += " WHERE archived_at IS NULL"
        return [_from_row(r) for r in self._conn.execute(sql + " ORDER BY created_at")]

    def get_global(self) -> Space | None:
        row = self._conn.execute("SELECT * FROM spaces WHERE kind = 'global'").fetchone()
        return _from_row(row) if row else None

    def ensure_global(self) -> Space:
        existing = self.get_global()
        if existing:
            return existing
        now = utc_now()
        return self.add(Space(new_id(), GLOBAL, "Board", now, now))

    def set_view_state(self, space_id: str, state: dict[str, Any] | None) -> bool:
        """Deliberately leaves updated_at alone: panning is not an edit of the space."""
        value = None if state is None else json.dumps(state)
        cur = self._conn.execute("UPDATE spaces SET view_state = ? WHERE id = ?", (value, space_id))
        self._conn.commit()
        return cur.rowcount > 0

    def delete(self, space_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM spaces WHERE id = ?", (space_id,))
        self._conn.commit()
        return cur.rowcount > 0
