import sqlite3

import pytest
from PySide6.QtCore import QModelIndex

from brainstorm.db.connection import connect
from brainstorm.db.edges import EdgeRepository
from brainstorm.db.migrations import migrate
from brainstorm.db.nodes import NodeRepository
from brainstorm.db.spaces import SpaceRepository
from brainstorm.domain import Space, utc_now
from brainstorm.models import EdgeModel
from brainstorm.services import EdgeService, NodeService
from tests.test_node_service import collect


@pytest.fixture
def pair(node_service, global_space):
    a = node_service.create(global_space.id, "note", x=0, y=0)
    b = node_service.create(global_space.id, "note", x=300, y=0)
    return a, b


def test_create_persists_and_emits(edge_service, pair):
    a, b = pair
    created = collect(edge_service.edgeCreated)
    edge = edge_service.create(a.id, b.id, "leads to", {"dashed": True})
    assert created == [(edge,)]
    stored = edge_service.get(edge.id)
    assert (stored.source_id, stored.target_id, stored.label) == (a.id, b.id, "leads to")
    assert stored.dashed is True and stored.arrow == "end"


def test_self_loops_are_rejected(edge_service, pair):
    a, _ = pair
    with pytest.raises(ValueError):
        edge_service.create(a.id, a.id)


def test_self_loops_are_also_rejected_by_the_database(conn, pair):
    a, _ = pair
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO edges (id, space_id, source_id, target_id, created_at)"
            " VALUES ('e', ?, ?, ?, 't')",
            (a.space_id, a.id, a.id),
        )


def test_duplicate_direction_is_rejected_but_reverse_is_fine(edge_service, pair):
    a, b = pair
    edge_service.create(a.id, b.id)
    with pytest.raises(ValueError):
        edge_service.create(a.id, b.id)
    edge_service.create(b.id, a.id)


def test_missing_nodes_and_cross_space_edges_are_rejected(conn, edge_service, node_service, pair):
    a, _ = pair
    with pytest.raises(KeyError):
        edge_service.create(a.id, "nope")
    now = utc_now()
    other = SpaceRepository(conn).add(Space("p1", "project", "P", now, now))
    foreign = node_service.create(other.id, "note", x=0, y=0)
    with pytest.raises(ValueError):
        edge_service.create(a.id, foreign.id)


def test_label_and_style_changes_emit_updates(edge_service, pair):
    a, b = pair
    edge = edge_service.create(a.id, b.id)
    updated = collect(edge_service.edgeUpdated)
    assert edge_service.set_label(edge.id, "yes").label == "yes"
    styled = edge_service.set_style(edge.id, dashed=True, arrow="both", color="#ff0000")
    assert (styled.dashed, styled.arrow, styled.color) == (True, "both", "#ff0000")
    assert len(updated) == 2
    assert edge_service.set_style(edge.id, color=None).color == ""


def test_invalid_style_is_rejected(edge_service, pair):
    a, b = pair
    edge = edge_service.create(a.id, b.id)
    with pytest.raises(ValueError):
        edge_service.set_style(edge.id, arrow="sideways")
    with pytest.raises(ValueError):
        edge_service.set_style(edge.id, glow=True)


def test_reconnect_moves_an_end(edge_service, node_service, global_space, pair):
    a, b = pair
    c = node_service.create(global_space.id, "note", x=0, y=300)
    edge = edge_service.create(a.id, b.id)
    moved = edge_service.reconnect(edge.id, target_id=c.id)
    assert (moved.source_id, moved.target_id) == (a.id, c.id)
    with pytest.raises(ValueError):
        edge_service.reconnect(edge.id, source_id=c.id)  # would become a self-loop


def test_delete_edge_emits(edge_service, pair):
    a, b = pair
    edge = edge_service.create(a.id, b.id)
    deleted = collect(edge_service.edgeDeleted)
    edge_service.delete(edge.id)
    assert deleted == [(edge.id, a.space_id)]
    assert edge_service.get(edge.id) is None


def test_deleting_a_node_cascades_to_its_edges(edge_service, node_service, global_space, pair):
    a, b = pair
    c = node_service.create(global_space.id, "note", x=0, y=300)
    edge_service.create(a.id, b.id)
    edge_service.create(c.id, a.id)
    keep = edge_service.create(b.id, c.id)
    node_service.delete(a.id)
    assert [e.id for e in edge_service.list(global_space.id)] == [keep.id]


def test_edge_survives_a_restart_with_label_and_style(tmp_path):
    path = tmp_path / "t.db"
    conn = connect(path)
    migrate(conn)
    space = SpaceRepository(conn).ensure_global()
    nodes = NodeService(NodeRepository(conn))
    edges = EdgeService(EdgeRepository(conn), NodeRepository(conn))
    a = nodes.create(space.id, "note", x=0, y=0)
    b = nodes.create(space.id, "note", x=1, y=1)
    edge = edges.create(a.id, b.id, "reload test", {"dashed": True, "arrow": "both"})
    conn.close()

    conn = connect(path)
    migrate(conn)
    again = EdgeRepository(conn).get(edge.id)
    assert (again.label, again.dashed, again.arrow) == ("reload test", True, "both")
    conn.close()


# EdgeModel


@pytest.fixture
def model(edge_service, node_service, global_space):
    return EdgeModel(edge_service, node_service, global_space.id)


def role(model, name):
    return {bytes(v).decode(): k for k, v in model.roleNames().items()}[name]


def test_model_follows_edge_signals(model, edge_service, pair):
    a, b = pair
    inserted = collect(model.rowsInserted)
    edge = edge_service.create(a.id, b.id, "x")
    assert inserted == [(QModelIndex(), 0, 0)]
    assert model.data(model.index(0), role(model, "label")) == "x"
    assert model.data(model.index(0), role(model, "sourceId")) == a.id

    changed = collect(model.dataChanged)
    edge_service.set_label(edge.id, "y")
    assert len(changed) == 1
    assert model.data(model.index(0), role(model, "label")) == "y"

    edge_service.set_style(edge.id, dashed=True)
    assert model.data(model.index(0), role(model, "dashed")) is True

    removed = collect(model.rowsRemoved)
    edge_service.delete(edge.id)
    assert removed == [(QModelIndex(), 0, 0)] and model.count == 0


def test_model_drops_rows_when_a_node_is_deleted(model, edge_service, node_service, pair):
    a, b = pair
    edge_service.create(a.id, b.id)
    edge_service.create(b.id, a.id)
    reset = collect(model.modelReset)
    node_service.delete(a.id)
    assert model.count == 0
    assert not reset  # rows were removed individually, not reloaded
