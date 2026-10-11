"""Loads the real QML headlessly and drives the canvas through it."""

import math
import os

import pytest
from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication, QWheelEvent
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest

from brainstorm.app_state import AppState
from brainstorm.controllers import CanvasController
from brainstorm.db.connection import connect
from brainstorm.db.migrations import migrate
from brainstorm.db.nodes import NodeRepository
from brainstorm.db.spaces import SpaceRepository
from brainstorm.main import create_engine
from brainstorm.services import NodeService, SpaceService


@pytest.fixture(scope="module")
def app():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication.instance() or QGuiApplication([])
    app.setOrganizationName("BrainstormTest")
    app.setApplicationName("BrainstormTest")
    return app


@pytest.fixture(scope="module")
def env(app):
    conn = connect(":memory:")
    migrate(conn)
    space = SpaceRepository(conn).ensure_global()
    nodes = NodeService(NodeRepository(conn))
    spaces = SpaceService(SpaceRepository(conn))
    state = AppState(space.id)
    controller = CanvasController(nodes, spaces, state)
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


def test_add_note_creates_node_at_viewport_center(env):
    window, canvas, world, nodes, space, *_ = env
    canvas.addNoteAtCenter()
    created = nodes.list(space.id)
    assert len(created) == 1
    note = created[0]
    assert (note.x + note.w / 2, note.y + note.h / 2) == pytest.approx((0, 0))


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
