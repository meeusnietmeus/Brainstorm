import json
import sqlite3
from typing import Any

from brainstorm.domain import Node

# Columns that update() may change. id, space_id and created_at are fixed after creation.
UPDATABLE = ("kind", "title", "body", "status", "x", "y", "w", "h", "z", "props", "updated_at")


def _from_row(row: sqlite3.Row) -> Node:
    data = dict(row)
    data["props"] = json.loads(data["props"])
    return Node(**data)


class NodeRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def add(self, node: Node) -> Node:
        self._conn.execute(
            "INSERT INTO nodes (id, space_id, kind, title, body, status, x, y, w, h, z, props,"
            " created_at, updated_at) VALUES (:id, :space_id, :kind, :title, :body, :status,"
            " :x, :y, :w, :h, :z, :props, :created_at, :updated_at)",
            {**{s: getattr(node, s) for s in node.__slots__}, "props": json.dumps(node.props)},
        )
        self._conn.commit()
        return node

    def get(self, node_id: str) -> Node | None:
        row = self._conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        return _from_row(row) if row else None

    def list_for_space(self, space_id: str) -> list[Node]:
        rows = self._conn.execute(
            "SELECT * FROM nodes WHERE space_id = ? ORDER BY z, created_at", (space_id,)
        )
        return [_from_row(r) for r in rows]

    def update(self, node_id: str, fields: dict[str, Any]) -> bool:
        unknown = set(fields) - set(UPDATABLE)
        if unknown:
            raise ValueError(f"Cannot update column(s): {', '.join(sorted(unknown))}")
        if not fields:
            return False
        values = dict(fields)
        if "props" in values:
            values["props"] = json.dumps(values["props"])
        assignments = ", ".join(f"{col} = :{col}" for col in values)
        cur = self._conn.execute(
            f"UPDATE nodes SET {assignments} WHERE id = :_id", {**values, "_id": node_id}
        )
        self._conn.commit()
        return cur.rowcount > 0

    def move_many(self, moves: list[tuple[str, float, float]], updated_at: str) -> None:
        """Set x/y for several nodes in a single transaction."""
        self._conn.executemany(
            "UPDATE nodes SET x = ?, y = ?, updated_at = ? WHERE id = ?",
            [(x, y, updated_at, node_id) for node_id, x, y in moves],
        )
        self._conn.commit()

    def delete(self, node_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def max_z(self, space_id: str) -> int:
        row = self._conn.execute(
            "SELECT MAX(z) FROM nodes WHERE space_id = ?", (space_id,)
        ).fetchone()
        return row[0] if row[0] is not None else 0
