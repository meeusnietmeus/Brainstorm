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
from brainstorm.db.edges import EdgeRepository
from brainstorm.db.migrations import migrate
from brainstorm.db.nodes import NodeRepository
from brainstorm.db.spaces import SpaceRepository
from brainstorm.main import create_engine
from brainstorm.services import (
    AssetStore,
    ClipboardService,
    EdgeService,
    NodeService,
    SpaceService,
)


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
    node_repo = NodeRepository(conn)
    nodes = NodeService(node_repo)
    edges = EdgeService(EdgeRepository(conn), node_repo)
    spaces = SpaceService(SpaceRepository(conn))
    state = AppState(space.id)
    assets = AssetStore(AssetRepository(conn), tmp_path_factory.mktemp("assets"))
    clipboard = ClipboardService(nodes, assets)
    controller = CanvasController(nodes, edges, spaces, state, clipboard, assets)
    engine = create_engine(state, controller)
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    QTest.qWait(100)  # let the layout run
    canvas = window.findChild(QObject, "boardCanvas")
    world = window.findChild(QObject, "world")
    yield window, canvas, world, nodes, space, conn, edges
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
    window, canvas, world, nodes, space, conn, *_ = env
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


# Regressions and toolbar


def test_clicking_outside_a_note_being_edited_saves_it(env):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    canvas.resetView()
    window.requestActivate()
    canvas.addNoteAtCenter()
    for char in "kept":
        QTest.keyClick(window, char)
    empty_spot = canvas_point(window, canvas, 40, 40).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, empty_spot)
    QTest.qWait(20)
    [note] = nodes.list(space.id)
    assert note.body == "kept"
    assert canvas.property("editingId") == ""


def test_clicking_another_node_while_editing_saves_the_edit(env):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    canvas.resetView()
    other = nodes.create(space.id, "note", body="other", x=300, y=200, w=200, h=60)
    window.requestActivate()
    canvas.addNoteAtCenter()
    for char in "first":
        QTest.keyClick(window, char)
    s = world.property("scale")
    spot = canvas_point(
        window,
        canvas,
        world.property("x") + (other.x + 20) * s,
        world.property("y") + (other.y + 20) * s,
    ).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, spot)
    QTest.qWait(20)
    bodies = {n.body for n in nodes.list(space.id)}
    assert bodies == {"first", "other"}


def pan_by(window, canvas, button, dx, dy):
    start = canvas_point(window, canvas, 500, 300).toPoint()
    QTest.mousePress(window, button, Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 11):
        QTest.mouseMove(window, start + QPoint(dx * step // 10, dy * step // 10))
        QTest.qWait(5)
    QTest.mouseRelease(window, button, Qt.KeyboardModifier.NoModifier, start + QPoint(dx, dy))


def test_middle_mouse_pan_moves_the_view_by_the_drag_distance(env):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    canvas.resetView()
    before = (world.property("x"), world.property("y"))
    # Press far from the origin: the old bug snapped the view so its origin followed the cursor.
    pan_by(window, canvas, Qt.MouseButton.MiddleButton, 80, 40)
    assert world.property("x") == pytest.approx(before[0] + 80)
    assert world.property("y") == pytest.approx(before[1] + 40)


def test_space_left_drag_pans_without_jumping(env):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    canvas.resetView()
    canvas.forceActiveFocus()
    before = (world.property("x"), world.property("y"))
    QTest.keyPress(window, Qt.Key.Key_Space)
    pan_by(window, canvas, Qt.MouseButton.LeftButton, -60, 30)
    QTest.keyRelease(window, Qt.Key.Key_Space)
    assert world.property("x") == pytest.approx(before[0] - 60)
    assert world.property("y") == pytest.approx(before[1] + 30)


def find_button(window, text):
    found = []

    def walk(item):
        if item.property("text") == text and item.property("checked") is not None:
            found.append(item)
        for child in item.childItems():
            walk(child)

    walk(window.contentItem())
    [button] = found
    return button


def click_item(window, item):
    center = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
    QTest.qWait(20)


def test_toolbar_buttons_are_disabled_without_a_selection(env):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    canvas.select("")
    QTest.qWait(20)
    for label in ("Forward", "Backward", "Delete"):
        assert find_button(window, label).property("enabled") is False


def test_toolbar_stacking_and_delete_buttons(env):
    window, canvas, world, nodes, space, *_ = env
    clear(nodes, space)
    canvas.resetView()
    first = nodes.create(space.id, "note", body="a", x=-400, y=-250, w=100, h=60)
    second = nodes.create(space.id, "note", body="b", x=-380, y=-240, w=100, h=60)
    canvas.select(first.id)
    QTest.qWait(20)

    click_item(window, find_button(window, "Forward"))
    assert nodes.get(first.id).z > nodes.get(second.id).z
    click_item(window, find_button(window, "Backward"))
    assert nodes.get(first.id).z < nodes.get(second.id).z

    click_item(window, find_button(window, "Delete"))
    assert nodes.get(first.id) is None
    assert nodes.get(second.id) is not None
    assert canvas.property("selectedId") == ""


# Phase 4: arrows and frames


def scene_center(item):
    return item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()


def world_to_window(window, canvas, world, x, y):
    s = world.property("scale")
    return canvas_point(
        window, canvas, world.property("x") + x * s, world.property("y") + y * s
    ).toPoint()


def drag(window, start, end, steps=12):
    QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, steps + 1):
        dx = (end.x() - start.x()) * step // steps
        dy = (end.y() - start.y()) * step // steps
        QTest.mouseMove(window, start + QPoint(dx, dy))
        QTest.qWait(5)
    QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end)
    QTest.qWait(30)


def right_dot(window):
    dots = [d for d in find_items(window, "connectionDot") if d.property("visible")]
    assert len(dots) == 4
    return max(dots, key=lambda d: d.mapToScene(QPointF(0, 0)).x())


def two_notes(nodes, space):
    a = nodes.create(space.id, "note", body="A", x=-400, y=-100, w=200, h=44)
    b = nodes.create(space.id, "note", body="B", x=100, y=-100, w=200, h=44)
    return a, b


def test_dragging_from_a_connection_dot_onto_a_node_creates_an_edge(env):
    window, canvas, world, nodes, space, conn, edges = env
    clear(nodes, space)
    canvas.resetView()
    a, b = two_notes(nodes, space)
    canvas.select(a.id)
    QTest.qWait(30)
    start = scene_center(right_dot(window))
    drag(window, start, world_to_window(window, canvas, world, b.x + 100, b.y + 22))
    [edge] = edges.list(space.id)
    assert (edge.source_id, edge.target_id) == (a.id, b.id)
    assert canvas.property("selectedEdgeId") == edge.id
    assert len(nodes.list(space.id)) == 2


def test_dragging_from_a_dot_onto_empty_canvas_creates_a_connected_note(env):
    window, canvas, world, nodes, space, conn, edges = env
    clear(nodes, space)
    canvas.resetView()
    a, _ = two_notes(nodes, space)
    canvas.select(a.id)
    QTest.qWait(30)
    start = scene_center(right_dot(window))
    drag(window, start, world_to_window(window, canvas, world, -50, 200))
    created = [n for n in nodes.list(space.id) if n.body == "" and n.id != a.id]
    [new_note] = created
    [edge] = edges.list(space.id)
    assert (edge.source_id, edge.target_id) == (a.id, new_note.id)
    assert canvas.property("editingId") == new_note.id  # ready to type into


def test_arrow_follows_a_node_live_during_a_drag(env):
    window, canvas, world, nodes, space, conn, edges = env
    clear(nodes, space)
    canvas.resetView()
    a, b = two_notes(nodes, space)
    edges.create(a.id, b.id)
    QTest.qWait(30)
    [chip] = find_items(window, "edgeChip")
    before = chip.mapToScene(QPointF(0, 0)).y()

    grab = world_to_window(window, canvas, world, b.x + 100, b.y + 22)
    QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grab)
    for step in range(1, 11):
        QTest.mouseMove(window, grab + QPoint(0, step * 20))
        QTest.qWait(5)
    during = chip.mapToScene(QPointF(0, 0)).y()
    assert nodes.get(b.id).y == -100  # nothing written yet
    QTest.mouseRelease(
        window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grab + QPoint(0, 200)
    )
    assert during > before + 50  # the midpoint chip moved with the node


def test_double_clicking_the_chip_edits_the_label(env):
    window, canvas, world, nodes, space, conn, edges = env
    clear(nodes, space)
    canvas.resetView()
    a, b = two_notes(nodes, space)
    edge = edges.create(a.id, b.id)
    QTest.qWait(30)
    [chip] = find_items(window, "edgeChip")
    window.requestActivate()
    QTest.mouseDClick(
        window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, scene_center(chip)
    )
    assert canvas.property("editingEdgeId") == edge.id
    for char in "causes":
        QTest.keyClick(window, char)
    QTest.keyClick(window, Qt.Key.Key_Return)
    QTest.qWait(30)
    assert edges.get(edge.id).label == "causes"
    assert canvas.property("editingEdgeId") == ""


def test_clicking_away_commits_an_edge_label_and_escape_cancels(env):
    window, canvas, world, nodes, space, conn, edges = env
    clear(nodes, space)
    canvas.resetView()
    a, b = two_notes(nodes, space)
    edge = edges.create(a.id, b.id, "old")
    QTest.qWait(30)
    window.requestActivate()
    canvas.selectEdge(edge.id)
    canvas.setProperty("editingEdgeId", edge.id)
    QTest.qWait(30)
    QTest.keyClick(window, "X")
    QTest.keyClick(window, Qt.Key.Key_Escape)
    QTest.qWait(30)
    assert edges.get(edge.id).label == "old"

    canvas.setProperty("editingEdgeId", edge.id)
    QTest.qWait(30)
    QTest.keyClick(window, "Z")
    QTest.mouseClick(
        window,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        canvas_point(window, canvas, 40, 400).toPoint(),
    )
    QTest.qWait(30)
    assert edges.get(edge.id).label.endswith("Z")


def test_selecting_an_edge_and_pressing_delete_removes_only_the_edge(env):
    window, canvas, world, nodes, space, conn, edges = env
    clear(nodes, space)
    canvas.resetView()
    a, b = two_notes(nodes, space)
    edge = edges.create(a.id, b.id)
    QTest.qWait(30)
    [chip] = find_items(window, "edgeChip")
    QTest.mouseClick(
        window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, scene_center(chip)
    )
    assert canvas.property("selectedEdgeId") == edge.id
    QTest.keyClick(window, Qt.Key.Key_Delete)
    assert edges.get(edge.id) is None
    assert len(nodes.list(space.id)) == 2


def test_deleting_a_node_removes_its_arrow_from_the_canvas(env):
    window, canvas, world, nodes, space, conn, edges = env
    clear(nodes, space)
    canvas.resetView()
    a, b = two_notes(nodes, space)
    edges.create(a.id, b.id)
    QTest.qWait(30)
    assert len(find_items(window, "edgeItem")) == 1
    nodes.delete(a.id)
    QTest.qWait(30)
    assert find_items(window, "edgeItem") == []
    assert edges.list(space.id) == []


def test_edges_follow_a_resized_node(env):
    window, canvas, world, nodes, space, conn, edges = env
    clear(nodes, space)
    canvas.resetView()
    a, b = two_notes(nodes, space)
    edges.create(a.id, b.id)
    QTest.qWait(30)
    [chip] = find_items(window, "edgeChip")
    before = chip.mapToScene(QPointF(0, 0)).x()
    nodes.resize(a.id, -400, -100, 100, 44)  # a shrinks: its right side moves left
    QTest.qWait(30)
    assert chip.mapToScene(QPointF(0, 0)).x() < before


def test_frame_is_added_titled_and_dragged_with_its_contents(env):
    window, canvas, world, nodes, space, conn, edges = env
    clear(nodes, space)
    canvas.resetView()
    window.requestActivate()
    canvas.addFrameAtCenter()
    [frame] = nodes.list(space.id)
    assert frame.kind == "frame" and canvas.property("editingId") == frame.id
    for char in "Boss":
        QTest.keyClick(window, char)
    QTest.keyClick(window, Qt.Key.Key_Return)
    QTest.qWait(30)
    assert nodes.get(frame.id).title == "Boss"

    inside = nodes.create(space.id, "note", body="in", x=frame.x + 30, y=frame.y + 60, w=100, h=44)
    outside = nodes.create(space.id, "note", body="out", x=frame.x + 600, y=frame.y, w=100, h=44)
    QTest.qWait(30)
    moves = []
    nodes.nodeMoved.connect(lambda *args: moves.append(args))

    header = world_to_window(window, canvas, world, frame.x + frame.w - 60, frame.y + 15)
    drag(window, header, header + QPoint(120, 80))

    assert len(moves) == 2  # the frame and the one node inside it
    moved_frame, moved_inside = nodes.get(frame.id), nodes.get(inside.id)
    assert moved_frame.x == pytest.approx(frame.x + 120, abs=2)
    assert moved_inside.x - inside.x == pytest.approx(moved_frame.x - frame.x)
    assert moved_inside.y - inside.y == pytest.approx(moved_frame.y - frame.y)
    assert nodes.get(outside.id).x == outside.x


def test_frame_body_is_click_through_so_double_click_adds_a_note_inside(env):
    window, canvas, world, nodes, space, conn, edges = env
    clear(nodes, space)
    canvas.resetView()
    frame = nodes.create(space.id, "frame", title="F", x=-200, y=-150, w=400, h=300)
    QTest.qWait(30)
    inside_point = world_to_window(window, canvas, world, 0, 50)
    QTest.mouseDClick(
        window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, inside_point
    )
    notes = [n for n in nodes.list(space.id) if n.kind == "note"]
    assert len(notes) == 1
    assert canvas.property("selectedId") != frame.id


def test_frames_are_drawn_below_notes_and_tint_can_change(env):
    window, canvas, world, nodes, space, conn, edges = env
    clear(nodes, space)
    canvas.resetView()
    note = nodes.create(space.id, "note", body="n", x=0, y=0)
    frame = nodes.create(
        space.id, "frame", title="F", x=-100, y=-100, w=500, h=400, props={"tint": "#6ea8fe"}
    )
    canvas.select(frame.id)
    QTest.qWait(30)
    delegates = {}

    def walk(item):
        if item.property("nodeId"):
            delegates[item.property("nodeId")] = item
        for child in item.childItems():
            walk(child)

    walk(window.contentItem())
    assert delegates[frame.id].property("z") < delegates[note.id].property("z")
    swatches = [s for s in find_items(window, "tintSwatch") if s.property("visible")]
    assert len(swatches) == 6
    QTest.mouseClick(
        window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, scene_center(swatches[1])
    )
    assert nodes.get(frame.id).props["tint"] == "#6fcf97"
