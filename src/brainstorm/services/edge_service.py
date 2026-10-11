import sqlite3
from typing import Any

from PySide6.QtCore import QObject, Signal

from brainstorm.db.edges import EdgeRepository
from brainstorm.db.nodes import NodeRepository
from brainstorm.domain import Edge, new_id, utc_now
from brainstorm.domain.edge import ARROWS

_STYLE_KEYS = {"dashed", "arrow", "color"}


class EdgeService(QObject):
    """Write path for edges. Edges removed because a node was deleted are not announced here:
    the database cascades, and models drop those rows when they see the node signal."""

    edgeCreated = Signal(object)  # Edge
    edgeUpdated = Signal(object)  # Edge (after the change)
    edgeDeleted = Signal(str, str)  # id, space_id

    def __init__(self, edges: EdgeRepository, nodes: NodeRepository, parent: QObject | None = None):
        super().__init__(parent)
        self._edges = edges
        self._nodes = nodes

    def get(self, edge_id: str) -> Edge | None:
        return self._edges.get(edge_id)

    def list(self, space_id: str) -> list[Edge]:
        return self._edges.list_for_space(space_id)

    def create(
        self,
        source_id: str,
        target_id: str,
        label: str = "",
        style: dict[str, Any] | None = None,
    ) -> Edge:
        if source_id == target_id:
            raise ValueError("An edge cannot connect a node to itself")
        source = self._nodes.get(source_id)
        target = self._nodes.get(target_id)
        if source is None or target is None:
            raise KeyError("Both ends of an edge must be existing nodes")
        if source.space_id != target.space_id:
            raise ValueError("Both ends of an edge must be in the same space")
        if self._edges.find(source_id, target_id):
            raise ValueError("These nodes are already connected in that direction")
        style = self._checked_style(style or {})
        edge = Edge(new_id(), source.space_id, source_id, target_id, utc_now(), label, style)
        self._edges.add(edge)
        self.edgeCreated.emit(edge)
        return edge

    def set_label(self, edge_id: str, label: str) -> Edge:
        return self._update(edge_id, {"label": label})

    def set_style(self, edge_id: str, **changes: Any) -> Edge:
        """Merge style keys (dashed, arrow, color). A value of None removes that key."""
        edge = self._require(edge_id)
        style = {**edge.style, **self._checked_style(changes)}
        style = {k: v for k, v in style.items() if v is not None}
        return self._update(edge_id, {"style": style})

    def reconnect(
        self, edge_id: str, source_id: str | None = None, target_id: str | None = None
    ) -> Edge:
        edge = self._require(edge_id)
        source_id = source_id or edge.source_id
        target_id = target_id or edge.target_id
        if source_id == target_id:
            raise ValueError("An edge cannot connect a node to itself")
        for node_id in (source_id, target_id):
            node = self._nodes.get(node_id)
            if node is None:
                raise KeyError(f"No such node: {node_id}")
            if node.space_id != edge.space_id:
                raise ValueError("Both ends of an edge must be in the same space")
        existing = self._edges.find(source_id, target_id)
        if existing and existing.id != edge_id:
            raise ValueError("These nodes are already connected in that direction")
        return self._update(edge_id, {"source_id": source_id, "target_id": target_id})

    def delete(self, edge_id: str) -> None:
        edge = self._require(edge_id)
        self._edges.delete(edge_id)
        self.edgeDeleted.emit(edge_id, edge.space_id)

    def _update(self, edge_id: str, fields: dict[str, Any]) -> Edge:
        self._require(edge_id)
        try:
            self._edges.update(edge_id, fields)
        except sqlite3.IntegrityError as exc:
            raise ValueError(str(exc)) from exc
        edge = self._require(edge_id)
        self.edgeUpdated.emit(edge)
        return edge

    def _require(self, edge_id: str) -> Edge:
        edge = self._edges.get(edge_id)
        if edge is None:
            raise KeyError(f"No such edge: {edge_id}")
        return edge

    @staticmethod
    def _checked_style(style: dict[str, Any]) -> dict[str, Any]:
        unknown = set(style) - _STYLE_KEYS
        if unknown:
            raise ValueError(f"Unknown style key(s): {', '.join(sorted(unknown))}")
        if style.get("arrow") is not None and style["arrow"] not in ARROWS:
            raise ValueError(f"arrow must be one of {ARROWS}")
        return style
