import pytest

from brainstorm.db.connection import connect
from brainstorm.db.migrations import migrate
from brainstorm.db.nodes import NodeRepository
from brainstorm.db.spaces import SpaceRepository
from brainstorm.services import NodeService


@pytest.fixture
def conn():
    connection = connect(":memory:")
    migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def global_space(conn):
    return SpaceRepository(conn).ensure_global()


@pytest.fixture
def node_service(conn):
    return NodeService(NodeRepository(conn))
