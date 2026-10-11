from brainstorm.db.spaces import SpaceRepository
from brainstorm.services import SpaceService


def test_view_state_defaults_to_none(conn, global_space):
    assert SpaceService(SpaceRepository(conn)).view_state(global_space.id) is None


def test_view_state_round_trips(conn, global_space):
    service = SpaceService(SpaceRepository(conn))
    service.set_view_state(global_space.id, -120.5, 40.0, 0.25)
    assert service.view_state(global_space.id) == {"x": -120.5, "y": 40.0, "scale": 0.25}


def test_saving_view_state_does_not_touch_updated_at(conn, global_space):
    service = SpaceService(SpaceRepository(conn))
    service.set_view_state(global_space.id, 1, 2, 3)
    assert service.get(global_space.id).updated_at == global_space.updated_at


def test_view_state_survives_reopening_the_database(tmp_path):
    from brainstorm.db.connection import connect
    from brainstorm.db.migrations import migrate

    path = tmp_path / "t.db"
    conn = connect(path)
    migrate(conn)
    space = SpaceRepository(conn).ensure_global()
    SpaceService(SpaceRepository(conn)).set_view_state(space.id, 5, 6, 2)
    conn.close()

    conn = connect(path)
    migrate(conn)
    assert SpaceService(SpaceRepository(conn)).view_state(space.id) == {"x": 5, "y": 6, "scale": 2}
    conn.close()
