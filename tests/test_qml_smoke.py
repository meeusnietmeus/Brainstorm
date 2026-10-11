"""Loads the real QML headlessly and drives the canvas through it."""

import math
import os

import pytest
from PySide6.QtCore import QMimeData, QObject, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QGuiApplication, QImage, QWheelEvent
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest

from brainstorm.app_state import AppState
from brainstorm.controllers import CanvasController
from brainstorm.db.assets import AssetRepository
from brainstorm.db.connection import connect
from brainstorm.db.migrations import migrate
from brainstorm.db.nodes import NodeRepository
from brainstorm.db.spaces import SpaceRepository
from brainstorm.main import create_engine
from brainstorm.services import AssetStore, ClipboardService, NodeService, SpaceService


@pytest.fixture(scope="module")
def app():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication.instance() or QGuiApplication([])
    app.setOrganizationName("BrainstormTest")
    app.setApplicationName("BrainstormTest")
    return app


@pytest.fixture(scope="module")
def env(app, tmp_path_factory):
    conn = connect(":memory:")
    migrate(conn)
    space = SpaceRepository(conn).ensure_global()
    nodes = NodeService(NodeRepository(conn))
    spaces = SpaceService(SpaceRepository(conn))
    state = AppState(space.id)
    assets = AssetStore(AssetRepository(conn), tmp_path_factory.mktemp("assets"))
    clipboard = ClipboardService(nodes, assets)
    controller = CanvasController(nodes, spaces, state, clipboard, assets)
    engine = create_engine(state, controller)
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    QTest.qWait(100)  # let the layout run
    canvas = window.findChild(QObject, "boardCanvas")
    world = window.findChild(QObject, "world")
    yield window, canvas, world, nodes, space, conn
    engine.deleteLater()
    conn.close()


def canvas_origin(window, canvas):
    """Top-left of the canvas in window coordinates."""
    return canvas.mapToScene(QPointF(0, 0)).toPoint()


def test_window_loads(env):
    window, canvas, world, *_ = env
    assert window.property("title") == "Brainstorm"
    assert canvas is not None and world is not None
    # First visit: world origin is centered in the viewport.
    assert world.property("x") == pytest.approx(canvas.width() / 2)
    assert world.property("y") == pytest.approx(canvas.height() / 2)


def test_add_note_opens_in_edit_mode_and_commits_on_escape(env):
    window, canvas, world, nodes, space, *_ = env
    window.requestActivate()
    canvas.addNoteAtCenter()
    [note] = nodes.list(space.id)
    assert (note.x + note.w / 2, note.y + note.h / 2) == pytest.approx((0, 0))
    assert canvas.property("editingId") == note.id

    for char in "Hello world":
        QTest.keyClick(window, char)
    QTest.keyClick(window, Qt.Key.Key_Escape)

    assert canvas.property("editingId") == ""
    saved = nodes.get(note.id)
    assert saved.body == "Hello world"
    assert saved.title == "Hello world"


def test_wheel_zoom_keeps_world_point_under_cursor(env):
    window, canvas, world, *_ = env
    origin = canvas_origin(window, canvas)
    cursor = QPointF(150, 90)  # canvas coordinates

    def world_point_under(c):
        s = world.property("scale")
        return ((c.x() - world.property("x")) / s, (c.y() - world.property("y")) / s)

    before = world_point_under(cursor)
    scale_before = world.property("scale")
    pos = QPointF(origin.x() + cursor.x(), origin.y() + cursor.y())
    event = QWheelEvent(
        pos,
        pos,
        QPoint(0, 0),
        QPoint(0, 240),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QGuiApplication.sendEvent(window, event)
    assert world.property("scale") > scale_before
    after = world_point_under(cursor)
    assert after[0] == pytest.approx(before[0], abs=1e-6)
    assert after[1] == pytest.approx(before[1], abs=1e-6)


def test_dragging_a_node_commits_one_move_on_release(env):
    window, canvas, world, nodes, space, *_ = env
    canvas.resetView()
    [note] = nodes.list(space.id)
    moves = []
    nodes.nodeMoved.connect(lambda *args: moves.append(args))

    origin = canvas_origin(window, canvas)
    s = world.property("scale")
    start = QPoint(
        int(origin.x() + world.property("x") + (note.x + 20) * s),
        int(origin.y() + world.property("y") + (note.y + 20) * s),
    )
    QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 11):
        QTest.mouseMove(window, start + QPoint(step * 10, step * 5))
        QTest.qWait(5)
    assert moves == []  # nothing written while dragging
    QTest.mouseRelease(
        window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start + QPoint(100, 50)
    )
    QTest.qWait(20)

    assert len(moves) == 1
    moved = nodes.get(note.id)
    assert moved.x == pytest.approx(note.x + 100 / s, abs=2)
    assert moved.y == pytest.approx(note.y + 50 / s, abs=2)
    assert canvas.property("selectedId") == note.id


def test_view_state_is_saved_after_debounce(env):
    window, canvas, world, nodes, space, conn = env
    canvas.zoomAt(QPointF(100, 100), 2.0)
    assert math.isclose(world.property("scale"), 2.0, rel_tol=1e-6)
    QTest.qWait(700)
    controller_state = SpaceService(SpaceRepository(conn)).view_state(space.id)
    assert controller_state["scale"] == pytest.approx(2.0)


def test_delete_key_removes_selected_node(env):
    window, canvas, world, nodes, space, *_ = env
    [note] = nodes.list(space.id)
    canvas.select(note.id)
    QTest.keyClick(window, Qt.Key.Key_Delete)
    assert nodes.list(space.id) == []


# Phase 3


def find_items(window, name):
    """Visual-tree search. findChildren misses items created by Repeaters and Loaders."""
    found = []

    def walk(item):
        if item.objectName() == name:
            found.append(item)
        for child in item.childItems():
            walk(child)

    walk(window.contentItem())
    return found


def clear(nodes, space):
    for node in nodes.list(space.id):
        nodes.delete(node.id)


def canvas_point(window, canvas, x, y):
    origin = canvas.mapToScene(QPointF(0, 0))
    return QPointF(origin.x() + x, origin.y() + y)


def test_ctrl_v_pastes_text_as_note_at_viewport_center(env):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    canvas.resetView()
    QGuiApplication.clipboard().setText("pasted idea")
    QTest.mouseMove(window, QPoint(5, 5))  # cursor outside the canvas (over the sidebar)
    QTest.qWait(20)
    canvas.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    [note] = nodes.list(space.id)
    assert note.kind == "note" and note.body == "pasted idea"
    assert note.x + note.w / 2 == pytest.approx(0)
    assert canvas.property("selectedId") == note.id


def test_ctrl_v_pastes_under_the_cursor_when_it_is_over_the_canvas(env):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    canvas.resetView()
    QGuiApplication.clipboard().setText("here")
    cursor = canvas_point(window, canvas, 400, 300).toPoint()
    QTest.mouseMove(window, cursor)
    QTest.qWait(20)
    canvas.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    [note] = nodes.list(space.id)
    expected = (400 - world.property("x"), 300 - world.property("y"))
    assert (note.x + note.w / 2, note.y) == pytest.approx(expected, abs=2)


def test_ctrl_v_pastes_image(env, png):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    QGuiApplication.clipboard().setImage(QImage.fromData(png(200, 100)))
    canvas.forceActiveFocus()
    QTest.keyClick(window, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    [image] = nodes.list(space.id)
    assert image.kind == "image"
    assert image.w / image.h == pytest.approx(2.0)


def test_note_body_is_rendered_as_markdown(env):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    nodes.create(space.id, "note", body="- one\n- two", x=0, y=0, w=200)
    QTest.qWait(50)
    [note] = find_items(window, "noteNode")
    assert note.property("rendersMarkdown") is True


def test_bracket_keys_change_stacking_order(env):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    first = nodes.create(space.id, "note", body="a", x=0, y=0)
    second = nodes.create(space.id, "note", body="b", x=10, y=10)
    canvas.select(first.id)
    QTest.keyClick(window, Qt.Key.Key_BracketRight)
    assert nodes.get(first.id).z > nodes.get(second.id).z
    QTest.keyClick(window, Qt.Key.Key_BracketLeft)
    assert nodes.get(first.id).z < nodes.get(second.id).z


@pytest.mark.parametrize("zoom", [0.25, 4.0])
def test_resize_handles_keep_constant_screen_size(env, zoom):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    note = nodes.create(space.id, "note", body="x", x=0, y=0, w=200)
    canvas.select(note.id)
    world.setProperty("scale", zoom)
    QTest.qWait(50)
    handles = [h for h in find_items(window, "resizeHandle") if h.property("visible")]
    assert len(handles) == 4
    for handle in handles:
        assert handle.property("width") * zoom == pytest.approx(10)


def test_dragging_a_handle_commits_one_resize_on_release(env):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    canvas.resetView()
    note = nodes.create(space.id, "note", body="x", x=0, y=0, w=200)
    canvas.select(note.id)
    QTest.qWait(50)
    updates = []
    nodes.nodeUpdated.connect(lambda n: updates.append(n))

    handles = [h for h in find_items(window, "resizeHandle") if h.property("visible")]
    corner = max(
        handles, key=lambda h: h.mapToScene(QPointF(0, 0)).x() + h.mapToScene(QPointF(0, 0)).y()
    )
    start = corner.mapToScene(QPointF(corner.width() / 2, corner.height() / 2)).toPoint()

    QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 7):
        QTest.mouseMove(window, start + QPoint(step * 10, 0))
        QTest.qWait(5)
    assert updates == []
    QTest.mouseRelease(
        window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start + QPoint(60, 0)
    )
    QTest.qWait(20)

    assert len(updates) == 1
    resized = nodes.get(note.id)
    assert resized.w == pytest.approx(260, abs=2)
    assert "fixedHeight" not in resized.props  # only widened, so the height still follows the text
    assert resized.x == pytest.approx(0)


def test_dropping_a_local_image_file_creates_an_image_node(env, png, tmp_path):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    canvas.resetView()
    path = tmp_path / "dropped.png"
    path.write_bytes(png(80, 40))
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    pos = canvas_point(window, canvas, 300, 200)
    window.requestActivate()
    enter = QDragEnterEvent(
        pos.toPoint(),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QGuiApplication.sendEvent(window, enter)
    drop = QDropEvent(
        pos,
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QGuiApplication.sendEvent(window, drop)
    [image] = nodes.list(space.id)
    assert image.kind == "image"
