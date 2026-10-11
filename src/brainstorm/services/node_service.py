from typing import Any

from PySide6.QtCore import QObject, Signal

from brainstorm.db.nodes import NodeRepository
from brainstorm.domain import Node, new_id, title_from_body, utc_now

DEFAULT_W = 200.0
DEFAULT_H = 100.0

# Fields callers may change through update(). Kind changes go through promote() (Phase 5),
# position through move().
_UPDATE_FIELDS = {"title", "body", "status", "w", "h", "z", "props"}


class NodeService(QObject):
    """The only write path for nodes. Every mutation emits a signal that models listen to."""

    nodeCreated = Signal(object)  # Node
    nodeUpdated = Signal(object)  # Node (after the change)
    nodeMoved = Signal(str, object, object)  # id, x, y (floats, or None when off canvas)
    nodeDeleted = Signal(str, str)  # id, space_id

    def __init__(self, repo: NodeRepository, parent: QObject | None = None):
        super().__init__(parent)
        self._repo = repo

    def get(self, node_id: str) -> Node | None:
        return self._repo.get(node_id)

    def list(self, space_id: str) -> list[Node]:
        return self._repo.list_for_space(space_id)

    def create(
        self,
        space_id: str,
        kind: str,
        *,
        title: str = "",
        body: str = "",
        status: str | None = None,
        x: float | None = None,
        y: float | None = None,
        w: float | None = DEFAULT_W,
        h: float | None = DEFAULT_H,
        z: int | None = None,
        props: dict[str, Any] | None = None,
    ) -> Node:
        if (x is None) != (y is None):
            raise ValueError("x and y must both be set or both be None")
        if kind == "note" and not title:
            title = title_from_body(body)
        now = utc_now()
        node = Node(
            id=new_id(),
            space_id=space_id,
            kind=kind,
            title=title,
            body=body,
            status=status,
            x=x,
            y=y,
            w=w,
            h=h,
            z=self._repo.max_z(space_id) + 1 if z is None else z,  # new nodes go on top
            props=props or {},
            created_at=now,
            updated_at=now,
        )
        self._repo.add(node)
        self.nodeCreated.emit(node)
        return node

    def update(self, node_id: str, **fields: Any) -> Node:
        unknown = set(fields) - _UPDATE_FIELDS
        if unknown:
            raise ValueError(f"Cannot update field(s): {', '.join(sorted(unknown))}")
        node = self._require(node_id)
        if "body" in fields and "title" not in fields and node.kind == "note":
            fields["title"] = title_from_body(fields["body"])
        self._repo.update(node_id, {**fields, "updated_at": utc_now()})
        node = self._require(node_id)
        self.nodeUpdated.emit(node)
        return node

    def set_props(self, node_id: str, **changes: Any) -> Node:
        """Merge `changes` into props. A value of None removes that key."""
        node = self._require(node_id)
        props = {**node.props, **changes}
        props = {k: v for k, v in props.items() if v is not None}
        return self.update(node_id, props=props)

    def resize(
        self,
        node_id: str,
        x: float,
        y: float,
        w: float,
        h: float,
        props: dict[str, Any] | None = None,
    ) -> Node:
        """Commit a resize (which can also shift x/y) as one write. Called on release."""
        node = self._require(node_id)
        fields: dict[str, Any] = {"x": x, "y": y, "w": w, "h": h, "updated_at": utc_now()}
        if props:
            fields["props"] = {**node.props, **props}
        self._repo.update(node_id, fields)
        node = self._require(node_id)
        self.nodeUpdated.emit(node)
        return node

    def shift_z(self, node_id: str, delta: int) -> list[Node]:
        """Move a node up (+1) or down (-1) one step among the nodes drawn on the canvas.

        The stacking order is renumbered 0..n-1 so z values never collide. Returns the nodes
        whose z changed.
        """
        node = self._require(node_id)
        if node.x is None:
            return []
        stack = [n for n in self._repo.list_for_space(node.space_id) if n.x is not None]
        index = next(i for i, n in enumerate(stack) if n.id == node_id)
        target = max(0, min(len(stack) - 1, index + delta))
        if target == index:
            return []
        stack.insert(target, stack.pop(index))
        changed = []
        now = utc_now()
        for z, item in enumerate(stack):
            if item.z != z:
                self._repo.update(item.id, {"z": z, "updated_at": now})
                item.z = z
                item.updated_at = now
                changed.append(item)
        for item in changed:
            self.nodeUpdated.emit(item)
        return changed

    def move(self, node_id: str, x: float | None, y: float | None) -> None:
        """Commit a position. Call once on drag release, never per mouse-move."""
        if (x is None) != (y is None):
            raise ValueError("x and y must both be set or both be None")
        self._require(node_id)
        self._repo.update(node_id, {"x": x, "y": y, "updated_at": utc_now()})
        self.nodeMoved.emit(node_id, x, y)

    def delete(self, node_id: str) -> None:
        node = self._require(node_id)
        self._repo.delete(node_id)
        self.nodeDeleted.emit(node_id, node.space_id)

    def _require(self, node_id: str) -> Node:
        node = self._repo.get(node_id)
        if node is None:
            raise KeyError(f"No such node: {node_id}")
        return node
