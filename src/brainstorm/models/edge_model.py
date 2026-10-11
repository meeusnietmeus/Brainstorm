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

from brainstorm.domain import Edge
from brainstorm.services import EdgeService, NodeService

_ROLE_NAMES = ["edgeId", "sourceId", "targetId", "label", "dashed", "arrow", "color"]
_ATTR = {"edgeId": "id", "sourceId": "source_id", "targetId": "target_id"}
_FIRST_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_ROLES = {_FIRST_ROLE + i: name for i, name in enumerate(_ROLE_NAMES)}


class EdgeModel(QAbstractListModel):
    """Edges of one space, built like NodeModel: row-level updates from service signals."""

    countChanged = Signal()

    def __init__(
        self,
        edges: EdgeService,
        nodes: NodeService,
        space_id: str,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._service = edges
        self._space_id = space_id
        self._edges: list[Edge] = edges.list(space_id)
        edges.edgeCreated.connect(self._on_created)
        edges.edgeUpdated.connect(self._on_updated)
        edges.edgeDeleted.connect(self._on_deleted)
        # The database cascades edge deletion when a node goes; follow it without re-reading.
        nodes.nodeDeleted.connect(self._on_node_deleted)

    def set_space_id(self, space_id: str) -> None:
        if space_id == self._space_id:
            return
        self.beginResetModel()
        self._space_id = space_id
        self._edges = self._service.list(space_id)
        self.endResetModel()
        self.countChanged.emit()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._edges)

    def roleNames(self) -> dict[int, QByteArray]:
        return {role: QByteArray(name.encode()) for role, name in _ROLES.items()}

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._edges):
            return None
        name = _ROLES.get(role)
        if name is None:
            return None
        return getattr(self._edges[index.row()], _ATTR.get(name, name))

    def _get_count(self) -> int:
        return len(self._edges)

    count = Property(int, _get_count, notify=countChanged)

    def _row(self, edge_id: str) -> int | None:
        return next((i for i, e in enumerate(self._edges) if e.id == edge_id), None)

    def _remove_row(self, row: int) -> None:
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._edges[row]
        self.endRemoveRows()
        self.countChanged.emit()

    def _on_created(self, edge: Edge) -> None:
        if edge.space_id != self._space_id:
            return
        row = len(self._edges)
        self.beginInsertRows(QModelIndex(), row, row)
        self._edges.append(edge)
        self.endInsertRows()
        self.countChanged.emit()

    def _on_updated(self, edge: Edge) -> None:
        row = self._row(edge.id)
        if row is None:
            return
        self._edges[row] = edge
        index = self.index(row)
        self.dataChanged.emit(index, index)

    def _on_deleted(self, edge_id: str, space_id: str) -> None:
        row = self._row(edge_id)
        if row is not None:
            self._remove_row(row)

    def _on_node_deleted(self, node_id: str, space_id: str) -> None:
        for row in reversed(range(len(self._edges))):
            edge = self._edges[row]
            if node_id in (edge.source_id, edge.target_id):
                self._remove_row(row)
