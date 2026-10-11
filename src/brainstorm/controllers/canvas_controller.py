from typing import Any

from PySide6.QtCore import Property, QMimeData, QObject, QUrl, Slot

from brainstorm import canvas_math, geometry
from brainstorm.app_state import AppState
from brainstorm.models import EdgeModel, NodeModel
from brainstorm.services import (
    AssetStore,
    ClipboardService,
    EdgeService,
    NodeService,
    SpaceService,
)


class CanvasController(QObject):
    """What the canvas QML may call. Thin: every write goes through a service."""

    def __init__(
        self,
        nodes: NodeService,
        edges: EdgeService,
        spaces: SpaceService,
        state: AppState,
        clipboard: ClipboardService,
        assets: AssetStore,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._nodes = nodes
        self._edges = edges
        self._spaces = spaces
        self._state = state
        self._clipboard = clipboard
        self._assets = assets
        self._model = NodeModel(nodes, state.currentSpaceId, self)
        self._edge_model = EdgeModel(edges, nodes, state.currentSpaceId, self)
        state.currentSpaceIdChanged.connect(self._on_space_changed)

    def _on_space_changed(self) -> None:
        self._model.set_space_id(self._state.currentSpaceId)
        self._edge_model.set_space_id(self._state.currentSpaceId)

    def _get_model(self) -> QObject:
        return self._model

    nodes = Property(QObject, _get_model, constant=True)

    def _get_edge_model(self) -> QObject:
        return self._edge_model

    edges = Property(QObject, _get_edge_model, constant=True)

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

    @Slot(str, str)
    def setTitle(self, node_id: str, title: str) -> None:
        self._nodes.update(node_id, title=title)

    # Frames

    @Slot(float, float, result=str)
    def createFrameCentered(self, cx: float, cy: float) -> str:
        w, h = 420.0, 300.0
        node = self._nodes.create(
            self._state.currentSpaceId,
            "frame",
            title="Frame",
            x=cx - w / 2,
            y=cy - h / 2,
            w=w,
            h=h,
            props={"tint": "#6ea8fe"},
        )
        return node.id

    def _contents(self, frame_id: str):
        frame = self._nodes.get(frame_id)
        if frame is None:
            return None, []
        return frame, geometry.nodes_inside(frame, self._nodes.list(frame.space_id))

    @Slot(str, result="QVariantList")
    def nodesInsideFrame(self, frame_id: str) -> list[str]:
        """Called at drag start so the canvas can move these along with the frame."""
        return [n.id for n in self._contents(frame_id)[1]]

    @Slot(str, float, float)
    def moveFrame(self, frame_id: str, x: float, y: float) -> None:
        """Commit a frame drag: the frame and everything that was inside it, in one write.

        Nothing is written during the drag, so the stored rectangles are still the ones the
        drag started from and the contents can be worked out again here.
        """
        frame, inside = self._contents(frame_id)
        if frame is None:
            return
        dx, dy = x - frame.x, y - frame.y
        moves = [(frame_id, x, y)] + [(n.id, n.x + dx, n.y + dy) for n in inside]
        self._nodes.move_many(moves)

    # Edges

    @Slot(str, str, result=str)
    def createEdge(self, source_id: str, target_id: str) -> str:
        """Returns the new edge's id, or "" if the connection is not allowed (duplicate etc.)."""
        try:
            return self._edges.create(source_id, target_id).id
        except (ValueError, KeyError):
            return ""

    @Slot(str, float, float, result=str)
    def createConnectedNote(self, source_id: str, cx: float, cy: float) -> str:
        """Release of a connection drag on empty canvas: a new note at that point, linked."""
        source = self._nodes.get(source_id)
        if source is None:
            return ""
        note = self._nodes.create(source.space_id, "note", x=cx - 130, y=cy - 20, w=260, h=40)
        self._edges.create(source_id, note.id)
        return note.id

    @Slot(str, str)
    def setEdgeLabel(self, edge_id: str, label: str) -> None:
        self._edges.set_label(edge_id, label.strip())

    @Slot(str, str, "QVariant")
    def setEdgeStyle(self, edge_id: str, key: str, value: Any) -> None:
        self._edges.set_style(edge_id, **{key: value})

    @Slot(str)
    def deleteEdge(self, edge_id: str) -> None:
        self._edges.delete(edge_id)

    @Slot(float, float, float, float, float, float, float, float, float, result="QVariantMap")
    def edgeGeometry(
        self,
        sx: float,
        sy: float,
        sw: float,
        sh: float,
        dx: float,
        dy: float,
        dw: float,
        dh: float,
        head_size: float,
    ) -> dict:
        return geometry.edge_geometry((sx, sy, sw, sh), (dx, dy, dw, dh), head_size).as_dict()

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
