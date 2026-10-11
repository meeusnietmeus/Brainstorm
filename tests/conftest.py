import os

import pytest
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QGuiApplication, QImage

from brainstorm.db.assets import AssetRepository
from brainstorm.db.connection import connect
from brainstorm.db.migrations import migrate
from brainstorm.db.nodes import NodeRepository
from brainstorm.db.spaces import SpaceRepository
from brainstorm.services import AssetStore, NodeService

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Image plugins and the clipboard need an application object."""
    app = QGuiApplication.instance() or QGuiApplication([])
    yield app


def make_png(width: int = 40, height: int = 20, color: str = "#336699") -> bytes:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


@pytest.fixture
def png():
    return make_png


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


@pytest.fixture
def asset_store(conn, tmp_path):
    return AssetStore(AssetRepository(conn), tmp_path / "assets")
