import pytest

from brainstorm.app_state import AppState
from brainstorm.controllers import CanvasController
from brainstorm.db.spaces import SpaceRepository
from brainstorm.services import ClipboardService, SpaceService
from tests.test_node_service import collect


@pytest.fixture
def controller(conn, node_service, edge_service, asset_store, global_space):
    return CanvasController(
        node_service,
        edge_service,
        SpaceService(SpaceRepository(conn)),
        AppState(global_space.id),
        ClipboardService(node_service, asset_store),
        asset_store,
    )


def test_move_many_is_one_write_and_signals_each_node(node_service, global_space, conn):
    a = node_service.create(global_space.id, "note", x=0, y=0)
    b = node_service.create(global_space.id, "note", x=10, y=10)
    moved = collect(node_service.nodeMoved)
    before = conn.total_changes
    node_service.move_many([(a.id, 5, 5), (b.id, 15, 15)])
    assert len(moved) == 2
    assert conn.total_changes - before == 2
    assert (node_service.get(b.id).x, node_service.get(b.id).y) == (15, 15)


def test_move_many_with_an_unknown_id_changes_nothing(node_service, global_space):
    a = node_service.create(global_space.id, "note", x=0, y=0)
    with pytest.raises(KeyError):
        node_service.move_many([(a.id, 9, 9), ("nope", 1, 1)])
    assert node_service.get(a.id).x == 0


def test_create_frame_is_a_titled_tinted_frame_centered_on_the_point(controller, node_service):
    frame = node_service.get(controller.createFrameCentered(100, 50))
    assert frame.kind == "frame" and frame.title == "Frame"
    assert frame.props["tint"]
    assert (frame.x + frame.w / 2, frame.y + frame.h / 2) == pytest.approx((100, 50))


def test_moving_a_frame_carries_exactly_what_was_inside(controller, node_service, global_space):
    frame = node_service.create(global_space.id, "frame", x=0, y=0, w=500, h=400)
    inside = node_service.create(global_space.id, "note", x=50, y=60, w=100, h=50)
    nested = node_service.create(global_space.id, "image", x=300, y=200, w=100, h=100)
    sticking_out = node_service.create(global_space.id, "note", x=450, y=10, w=100, h=50)
    outside = node_service.create(global_space.id, "note", x=900, y=900, w=100, h=50)

    assert set(controller.nodesInsideFrame(frame.id)) == {inside.id, nested.id}

    moved = collect(node_service.nodeMoved)
    controller.moveFrame(frame.id, 1000, 2000)

    assert len(moved) == 3  # frame + two contained nodes, nothing else
    get = node_service.get
    assert (get(frame.id).x, get(frame.id).y) == (1000, 2000)
    assert (get(inside.id).x, get(inside.id).y) == (1050, 2060)
    assert (get(nested.id).x, get(nested.id).y) == (1300, 2200)
    assert (get(sticking_out.id).x, get(sticking_out.id).y) == (450, 10)
    assert (get(outside.id).x, get(outside.id).y) == (900, 900)


def test_frame_band_is_separate_for_stacking_order(node_service, global_space):
    frame = node_service.create(global_space.id, "frame", x=0, y=0, w=300, h=300)
    note = node_service.create(global_space.id, "note", x=10, y=10)
    # A frame and a note never swap places: they are drawn in different bands.
    assert node_service.shift_z(note.id, -1) == []
    assert node_service.shift_z(frame.id, 1) == []


def test_controller_edge_helpers(controller, node_service, edge_service, global_space):
    a = node_service.create(global_space.id, "note", x=0, y=0)
    b = node_service.create(global_space.id, "note", x=300, y=0)
    edge_id = controller.createEdge(a.id, b.id)
    assert edge_id
    assert controller.createEdge(a.id, b.id) == ""  # duplicate
    assert controller.createEdge(a.id, a.id) == ""  # self loop
    controller.setEdgeLabel(edge_id, "  hello ")
    assert edge_service.get(edge_id).label == "hello"
    controller.setEdgeStyle(edge_id, "arrow", "none")
    assert edge_service.get(edge_id).arrow == "none"
    controller.deleteEdge(edge_id)
    assert edge_service.get(edge_id) is None


def test_connected_note_is_created_at_the_point_and_linked(
    controller, node_service, edge_service, global_space
):
    source = node_service.create(global_space.id, "note", x=0, y=0)
    note = node_service.get(controller.createConnectedNote(source.id, 500, 300))
    assert note.x + note.w / 2 == pytest.approx(500)
    [edge] = edge_service.list(global_space.id)
    assert (edge.source_id, edge.target_id) == (source.id, note.id)


def test_edge_geometry_slot_returns_points(controller):
    g = controller.edgeGeometry(0, 0, 100, 50, 300, 0, 100, 50, 14)
    assert g["start"] == {"x": 100, "y": 25}
    assert g["end"] == {"x": 300, "y": 25}
