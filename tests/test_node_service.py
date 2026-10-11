import pytest

from brainstorm.db.spaces import SpaceRepository
from brainstorm.domain import Space, utc_now


def collect(signal):
    received = []
    signal.connect(lambda *args: received.append(args))
    return received


def test_ensure_global_is_idempotent(conn):
    repo = SpaceRepository(conn)
    first = repo.ensure_global()
    assert repo.ensure_global().id == first.id
    assert len(repo.list()) == 1


def test_create_persists_and_emits(node_service, global_space):
    created = collect(node_service.nodeCreated)
    node = node_service.create(global_space.id, "note", title="Hi", x=10, y=20, props={"a": 1})
    assert created == [(node,)]
    stored = node_service.get(node.id)
    assert stored == node
    assert (stored.x, stored.y, stored.props) == (10, 20, {"a": 1})


def test_new_nodes_go_on_top(node_service, global_space):
    a = node_service.create(global_space.id, "note")
    b = node_service.create(global_space.id, "note")
    assert b.z > a.z


def test_node_without_position_is_allowed(node_service, global_space):
    node = node_service.create(global_space.id, "code_todo")
    assert node.x is None and node.y is None


def test_half_a_position_is_rejected(node_service, global_space):
    with pytest.raises(ValueError):
        node_service.create(global_space.id, "note", x=1)
    node = node_service.create(global_space.id, "note", x=1, y=1)
    with pytest.raises(ValueError):
        node_service.move(node.id, 5, None)


def test_update_changes_fields_and_emits(node_service, global_space):
    node = node_service.create(global_space.id, "note")
    updated = collect(node_service.nodeUpdated)
    result = node_service.update(node.id, title="New", body="text", props={"style": "card"})
    assert updated == [(result,)]
    assert (result.title, result.body, result.props) == ("New", "text", {"style": "card"})
    assert result.updated_at >= node.updated_at


def test_update_rejects_unknown_and_protected_fields(node_service, global_space):
    node = node_service.create(global_space.id, "note")
    for field in ("nope", "space_id", "x", "kind"):
        with pytest.raises(ValueError):
            node_service.update(node.id, **{field: 1})


def test_move_sets_position_and_emits(node_service, global_space):
    node = node_service.create(global_space.id, "note", x=0, y=0)
    moved = collect(node_service.nodeMoved)
    node_service.move(node.id, 5.5, -3.25)
    assert moved == [(node.id, 5.5, -3.25)]
    stored = node_service.get(node.id)
    assert (stored.x, stored.y) == (5.5, -3.25)


def test_move_to_none_removes_from_canvas(node_service, global_space):
    node = node_service.create(global_space.id, "note", x=1, y=2)
    node_service.move(node.id, None, None)
    assert node_service.get(node.id).x is None


def test_delete_removes_and_emits(node_service, global_space):
    node = node_service.create(global_space.id, "note")
    deleted = collect(node_service.nodeDeleted)
    node_service.delete(node.id)
    assert deleted == [(node.id, global_space.id)]
    assert node_service.get(node.id) is None


def test_operations_on_missing_node_raise(node_service):
    for call in (
        lambda: node_service.update("nope", title="x"),
        lambda: node_service.move("nope", 0, 0),
        lambda: node_service.delete("nope"),
    ):
        with pytest.raises(KeyError):
            call()


def test_list_is_scoped_to_space(conn, node_service, global_space):
    now = utc_now()
    other = SpaceRepository(conn).add(Space("p1", "project", "P", now, now))
    node_service.create(global_space.id, "note")
    node_service.create(other.id, "note")
    assert len(node_service.list(global_space.id)) == 1
    assert len(node_service.list(other.id)) == 1


def test_deleting_a_space_cascades_to_nodes(conn, node_service):
    now = utc_now()
    repo = SpaceRepository(conn)
    space = repo.add(Space("p1", "project", "P", now, now))
    node = node_service.create(space.id, "note")
    repo.delete(space.id)
    assert node_service.get(node.id) is None
