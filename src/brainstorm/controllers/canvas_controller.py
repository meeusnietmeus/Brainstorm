from typing import Any

from PySide6.QtCore import Property, QMimeData, QObject, QUrl, Slot

from brainstorm import canvas_math
from brainstorm.app_state import AppState
from brainstorm.models import NodeModel
from brainstorm.services import AssetStore, ClipboardService, NodeService, SpaceService


class CanvasController(QObject):
    """What the canvas QML may call. Thin: every write goes through a service."""

    def __init__(
        self,
        nodes: NodeService,
        spaces: SpaceService,
        state: AppState,
        clipboard: ClipboardService,
        assets: AssetStore,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._nodes = nodes
        self._spaces = spaces
        self._state = state
        self._clipboard = clipboard
        self._assets = assets
        self._model = NodeModel(nodes, state.currentSpaceId, self)
        state.currentSpaceIdChanged.connect(lambda: self._model.set_space_id(state.currentSpaceId))

    def _get_model(self) -> QObject:
        return self._model

    nodes = Property(QObject, _get_model, constant=True)

    # Nodes

    @Slot(float, float, result=str)
    def createNoteCentered(self, cx: float, cy: float) -> str:
        """Create an empty note centered on the world point (cx, cy). Returns its id."""
        width = 260.0
        node = self._nodes.create(
            self._state.currentSpaceId, "note", x=cx - width / 2, y=cy - 20, w=width, h=40
        )
        return node.id

    @Slot(str, float, float)
    def moveNode(self, node_id: str, x: float, y: float) -> None:
        """Called once, on drag release."""
        self._nodes.move(node_id, x, y)

    @Slot(str, float, float, float, float, "QVariantMap")
    def resizeNode(
        self, node_id: str, x: float, y: float, w: float, h: float, props: dict[str, Any]
    ) -> None:
        """Called once, on handle release."""
        self._nodes.resize(node_id, x, y, w, h, props or None)

    @Slot(str)
    def deleteNode(self, node_id: str) -> None:
        self._nodes.delete(node_id)

    @Slot(str, str, float)
    def commitNoteText(self, node_id: str, body: str, height: float) -> None:
        """Called when editing ends. A note that was empty and still is gets removed."""
        node = self._nodes.get(node_id)
        if node is None:
            return
        if not body.strip() and not node.body.strip():
            self._nodes.delete(node_id)
            return
        if body != node.body or abs((node.h or 0) - height) > 0.5:
            self._nodes.update(node_id, body=body, h=height)

    @Slot(str, str, "QVariant")
    def setProp(self, node_id: str, key: str, value: Any) -> None:
        self._nodes.set_props(node_id, **{key: value})

    @Slot(str, int)
    def moveInZ(self, node_id: str, delta: int) -> None:
        self._nodes.shift_z(node_id, delta)

    # Clipboard and drops

    @Slot(float, float, result="QVariantList")
    def paste(self, x: float, y: float) -> list[str]:
        created = self._clipboard.paste(self._state.currentSpaceId, x, y)
        return [n.id for n in created]

    @Slot("QVariantList", str, str, float, float, result="QVariantList")
    def importDrop(self, urls: list[str], html: str, text: str, x: float, y: float) -> list[str]:
        mime = QMimeData()
        if urls:
            mime.setUrls([QUrl(u) for u in urls])
        if html:
            mime.setHtml(html)
        if text:
            mime.setText(text)
        created = self._clipboard.import_mime(mime, self._state.currentSpaceId, x, y)
        return [n.id for n in created]

    @Slot(str, result=str)
    def assetUrl(self, asset_hash: str) -> str:
        if not asset_hash or self._assets.get(asset_hash) is None:
            return ""
        return self._assets.url(asset_hash).toString()

    # Viewport

    @Slot(float, float, float, float, float, float, result="QVariantList")
    def zoomAt(self, ox: float, oy: float, scale: float, cx: float, cy: float, factor: float):
        return list(canvas_math.zoom_at((ox, oy), scale, (cx, cy), factor))

    @Slot(str, result="QVariantMap")
    def loadViewState(self, space_id: str) -> dict:
        return self._spaces.view_state(space_id) or {}

    @Slot(str, float, float, float)
    def saveViewState(self, space_id: str, x: float, y: float, scale: float) -> None:
        self._spaces.set_view_state(space_id, x, y, scale)
