import pytest
from PySide6.QtCore import QModelIndex, Qt

from brainstorm.db.spaces import SpaceRepository
from brainstorm.domain import Space, utc_now
from brainstorm.models import NodeModel


@pytest.fixture
def model(node_service, global_space):
    return NodeModel(node_service, global_space.id)


def role(model, name):
    return {bytes(v).decode(): k for k, v in model.roleNames().items()}[name]


def value(model, row, name):
    return model.data(model.index(row), role(model, name))


def record(signal):
    events = []
    signal.connect(lambda *args: events.append(args))
    return events


def test_loads_existing_nodes(node_service, global_space):
    node_service.create(global_space.id, "note", title="a", x=1, y=2)
    model = NodeModel(node_service, global_space.id)
    assert model.rowCount() == 1
    assert (value(model, 0, "title"), value(model, 0, "x"), value(model, 0, "y")) == ("a", 1, 2)


def test_create_inserts_one_row(model, node_service, global_space):
    inserted = record(model.rowsInserted)
    reset = record(model.modelReset)
    node = node_service.create(global_space.id, "note", title="a", x=0, y=0)
    assert inserted == [(QModelIndex(), 0, 0)]
    assert not reset
    assert value(model, 0, "nodeId") == node.id
    assert model.count == 1


def test_node_in_other_space_is_ignored(conn, model, node_service):
    now = utc_now()
    other = SpaceRepository(conn).add(Space("p1", "project", "P", now, now))
    node_service.create(other.id, "note")
    assert model.rowCount() == 0


def test_move_emits_data_changed_for_position_only(model, node_service, global_space):
    node = node_service.create(global_space.id, "note", x=0, y=0)
    changed = record(model.dataChanged)
    reset = record(model.modelReset)
    node_service.move(node.id, 10, 20)
    assert not reset
    assert len(changed) == 1
    _, _, roles = changed[0]
    assert set(roles) == {role(model, "x"), role(model, "y"), role(model, "onCanvas")}
    assert (value(model, 0, "x"), value(model, 0, "y")) == (10, 20)


def test_update_refreshes_row(model, node_service, global_space):
    node = node_service.create(global_space.id, "note", title="old", x=0, y=0)
    changed = record(model.dataChanged)
    node_service.update(node.id, title="new")
    assert len(changed) == 1
    assert value(model, 0, "title") == "new"


def test_delete_removes_row_and_reindexes(model, node_service, global_space):
    a = node_service.create(global_space.id, "note", title="a")
    b = node_service.create(global_space.id, "note", title="b")
    removed = record(model.rowsRemoved)
    node_service.delete(a.id)
    assert removed == [(QModelIndex(), 0, 0)]
    assert model.rowCount() == 1
    # The surviving node must still be addressable after the shift.
    node_service.move(b.id, 5, 6)
    assert (value(model, 0, "x"), value(model, 0, "y")) == (5, 6)


def test_node_without_position_is_not_on_canvas(model, node_service, global_space):
    node = node_service.create(global_space.id, "code_todo")
    assert value(model, 0, "onCanvas") is False
    node_service.move(node.id, 1, 1)
    assert value(model, 0, "onCanvas") is True


def test_invalid_index_returns_none(model):
    assert model.data(model.index(5), Qt.ItemDataRole.DisplayRole) is None


def test_set_space_id_resets_model(conn, model, node_service, global_space):
    now = utc_now()
    other = SpaceRepository(conn).add(Space("p1", "project", "P", now, now))
    node_service.create(global_space.id, "note")
    node_service.create(other.id, "note")
    node_service.create(other.id, "note")
    model.set_space_id(other.id)
    assert model.rowCount() == 2
