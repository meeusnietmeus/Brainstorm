from dataclasses import replace
from typing import Any

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    Qt,
    Signal,
)

from brainstorm.domain import Node
from brainstorm.services import NodeService

# Role name -> Node attribute. "onCanvas" is derived: nodes without a position exist in the
# model (list and board views use them) but are not drawn.
_FIELD_ROLES = ["nodeId", "kind", "title", "body", "status", "x", "y", "w", "h", "z", "props"]
_ATTR = {"nodeId": "id"}
_FIRST_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_ROLES = {_FIRST_ROLE + i: name for i, name in enumerate([*_FIELD_ROLES, "onCanvas"])}
_ROLE_BY_NAME = {name: role for role, name in _ROLES.items()}
_POSITION_ROLES = [_ROLE_BY_NAME[n] for n in ("x", "y", "onCanvas")]


class NodeModel(QAbstractListModel):
    """Nodes of one space, kept in sync with NodeService signals. Never reloads after an edit."""

    countChanged = Signal()

    def __init__(self, service: NodeService, space_id: str, parent: QObject | None = None):
        super().__init__(parent)
        self._service = service
        self._space_id = space_id
        self._nodes: list[Node] = service.list(space_id)
        self._rows: dict[str, int] = {n.id: i for i, n in enumerate(self._nodes)}
        service.nodeCreated.connect(self._on_created)
        service.nodeUpdated.connect(self._on_updated)
        service.nodeMoved.connect(self._on_moved)
        service.nodeDeleted.connect(self._on_deleted)

    @property
    def space_id(self) -> str:
        return self._space_id

    def set_space_id(self, space_id: str) -> None:
        if space_id == self._space_id:
            return
        self.beginResetModel()
        self._space_id = space_id
        self._nodes = self._service.list(space_id)
        self._reindex()
        self.endResetModel()
        self.countChanged.emit()

    def node_at(self, row: int) -> Node:
        return self._nodes[row]

    def row_of(self, node_id: str) -> int | None:
        return self._rows.get(node_id)

    # QAbstractListModel interface

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._nodes)

    def roleNames(self) -> dict[int, QByteArray]:
        return {role: QByteArray(name.encode()) for role, name in _ROLES.items()}

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._nodes):
            return None
        name = _ROLES.get(role)
        if name is None:
            return None
        node = self._nodes[index.row()]
        if name == "onCanvas":
            return node.x is not None and node.y is not None
        return getattr(node, _ATTR.get(name, name))

    def _get_count(self) -> int:
        return len(self._nodes)

    count = Property(int, _get_count, notify=countChanged)

    # Service signal handlers

    def _reindex(self) -> None:
        self._rows = {n.id: i for i, n in enumerate(self._nodes)}

    def _on_created(self, node: Node) -> None:
        if node.space_id != self._space_id:
            return
        row = len(self._nodes)
        self.beginInsertRows(QModelIndex(), row, row)
        # A copy: _on_moved mutates rows in place and must not change the caller's object.
        self._nodes.append(replace(node))
        self._rows[node.id] = row
        self.endInsertRows()
        self.countChanged.emit()

    def _on_updated(self, node: Node) -> None:
        row = self._rows.get(node.id)
        if row is None:
            return
        self._nodes[row] = node
        index = self.index(row)
        self.dataChanged.emit(index, index)

    def _on_moved(self, node_id: str, x: float | None, y: float | None) -> None:
        row = self._rows.get(node_id)
        if row is None:
            return
        node = self._nodes[row]
        node.x, node.y = x, y
        index = self.index(row)
        self.dataChanged.emit(index, index, _POSITION_ROLES)

    def _on_deleted(self, node_id: str, space_id: str) -> None:
        row = self._rows.get(node_id)
        if row is None:
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._nodes[row]
        self._reindex()
        self.endRemoveRows()
        self.countChanged.emit()
