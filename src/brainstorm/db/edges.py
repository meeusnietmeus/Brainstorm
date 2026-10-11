import json
import sqlite3
from typing import Any

from brainstorm.domain import Edge

UPDATABLE = ("source_id", "target_id", "label", "style")


def _from_row(row: sqlite3.Row) -> Edge:
    data = dict(row)
    data["style"] = json.loads(data["style"])
    return Edge(**data)


class EdgeRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def add(self, edge: Edge) -> Edge:
        self._conn.execute(
            "INSERT INTO edges (id, space_id, source_id, target_id, label, style, created_at)"
            " VALUES (:id, :space_id, :source_id, :target_id, :label, :style, :created_at)",
            {**{s: getattr(edge, s) for s in edge.__slots__}, "style": json.dumps(edge.style)},
        )
        self._conn.commit()
        return edge

    def get(self, edge_id: str) -> Edge | None:
        row = self._conn.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone()
        return _from_row(row) if row else None

    def find(self, source_id: str, target_id: str) -> Edge | None:
        row = self._conn.execute(
            "SELECT * FROM edges WHERE source_id = ? AND target_id = ?", (source_id, target_id)
        ).fetchone()
        return _from_row(row) if row else None

    def list_for_space(self, space_id: str) -> list[Edge]:
        rows = self._conn.execute(
            "SELECT * FROM edges WHERE space_id = ? ORDER BY created_at, id", (space_id,)
        )
        return [_from_row(r) for r in rows]

    def list_for_node(self, node_id: str) -> list[Edge]:
        rows = self._conn.execute(
            "SELECT * FROM edges WHERE source_id = ? OR target_id = ? ORDER BY created_at, id",
            (node_id, node_id),
        )
        return [_from_row(r) for r in rows]

    def update(self, edge_id: str, fields: dict[str, Any]) -> bool:
        unknown = set(fields) - set(UPDATABLE)
        if unknown:
            raise ValueError(f"Cannot update column(s): {', '.join(sorted(unknown))}")
        if not fields:
            return False
        values = dict(fields)
        if "style" in values:
            values["style"] = json.dumps(values["style"])
        assignments = ", ".join(f"{col} = :{col}" for col in values)
        cur = self._conn.execute(
            f"UPDATE edges SET {assignments} WHERE id = :_id", {**values, "_id": edge_id}
        )
        self._conn.commit()
        return cur.rowcount > 0

    def delete(self, edge_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
        self._conn.commit()
        return cur.rowcount > 0
