from PySide6.QtCore import Property, QObject, Slot

from brainstorm import canvas_math
from brainstorm.app_state import AppState
from brainstorm.models import NodeModel
from brainstorm.services import NodeService, SpaceService
from brainstorm.services.node_service import DEFAULT_H, DEFAULT_W


class CanvasController(QObject):
    """What the canvas QML may call. Thin: every write goes through a service."""

    def __init__(
        self,
        nodes: NodeService,
        spaces: SpaceService,
        state: AppState,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._nodes = nodes
        self._spaces = spaces
        self._state = state
        self._model = NodeModel(nodes, state.currentSpaceId, self)
        state.currentSpaceIdChanged.connect(lambda: self._model.set_space_id(state.currentSpaceId))

    def _get_model(self) -> QObject:
        return self._model

    nodes = Property(QObject, _get_model, constant=True)

    @Slot(float, float, result=str)
    def createNoteCentered(self, cx: float, cy: float) -> str:
        """Create a note whose center is the world point (cx, cy). Returns its id."""
        node = self._nodes.create(
            self._state.currentSpaceId,
            "note",
            title="Note",
            x=cx - DEFAULT_W / 2,
            y=cy - DEFAULT_H / 2,
        )
        return node.id

    @Slot(str, float, float)
    def moveNode(self, node_id: str, x: float, y: float) -> None:
        """Called once, on drag release."""
        self._nodes.move(node_id, x, y)

    @Slot(str)
    def deleteNode(self, node_id: str) -> None:
        self._nodes.delete(node_id)

    @Slot(float, float, float, float, float, float, result="QVariantList")
    def zoomAt(self, ox: float, oy: float, scale: float, cx: float, cy: float, factor: float):
        return list(canvas_math.zoom_at((ox, oy), scale, (cx, cy), factor))

    @Slot(str, result="QVariantMap")
    def loadViewState(self, space_id: str) -> dict:
        return self._spaces.view_state(space_id) or {}

    @Slot(str, float, float, float)
    def saveViewState(self, space_id: str, x: float, y: float, scale: float) -> None:
        self._spaces.set_view_state(space_id, x, y, scale)
