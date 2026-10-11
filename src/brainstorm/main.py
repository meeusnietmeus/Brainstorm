import sys

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
from PySide6.QtQuickControls2 import QQuickStyle

from brainstorm import __version__, paths
from brainstorm.app_state import AppState
from brainstorm.controllers import CanvasController
from brainstorm.db.assets import AssetRepository
from brainstorm.db.connection import connect
from brainstorm.db.edges import EdgeRepository
from brainstorm.db.migrations import migrate
from brainstorm.db.nodes import NodeRepository
from brainstorm.db.spaces import SpaceRepository
from brainstorm.services import (
    AssetStore,
    ClipboardService,
    EdgeService,
    NodeService,
    SpaceService,
)

QML_URI = "Brainstorm"


def create_engine(state: AppState, canvas: CanvasController) -> QQmlApplicationEngine:
    """Expose Python objects to QML and load Main.qml."""
    # Must happen before the engine exists: registering afterwards breaks QtQuick type
    # resolution ("expected QObject" errors).
    qmlRegisterSingletonInstance(AppState, QML_URI, 1, 0, "AppState", state)
    qmlRegisterSingletonInstance(CanvasController, QML_URI, 1, 0, "CanvasController", canvas)
    engine = QQmlApplicationEngine()
    qml = paths.qml_dir()
    engine.addImportPath(str(qml))
    engine.load(QUrl.fromLocalFile(str(qml / "Main.qml")))
    return engine


def main() -> int:
    QCoreApplication.setOrganizationName("Brainstorm")
    QCoreApplication.setApplicationName("Brainstorm")
    QCoreApplication.setApplicationVersion(__version__)
    QQuickStyle.setStyle("Basic")  # the native style cannot be themed
    app = QGuiApplication(sys.argv)

    conn = connect(paths.db_path())
    migrate(conn)
    global_space = SpaceRepository(conn).ensure_global()

    # Services are the only write path. Kept referenced here so they outlive the engine.
    node_repo = NodeRepository(conn)
    node_service = NodeService(node_repo)
    edge_service = EdgeService(EdgeRepository(conn), node_repo)
    space_service = SpaceService(SpaceRepository(conn))
    state = AppState(global_space.id)
    assets = AssetStore(AssetRepository(conn), paths.assets_dir())
    clipboard = ClipboardService(node_service, assets)
    canvas = CanvasController(node_service, edge_service, space_service, state, clipboard, assets)

    engine = create_engine(state, canvas)
    if not engine.rootObjects():
        return 1

    app.aboutToQuit.connect(conn.close)
    return app.exec()
