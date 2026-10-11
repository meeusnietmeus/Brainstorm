import sys

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
from PySide6.QtQuickControls2 import QQuickStyle

from brainstorm import __version__, paths
from brainstorm.app_state import AppState
from brainstorm.db.connection import connect
from brainstorm.db.migrations import migrate
from brainstorm.db.nodes import NodeRepository
from brainstorm.db.spaces import SpaceRepository
from brainstorm.services import NodeService

QML_URI = "Brainstorm"


def create_engine(state: AppState) -> QQmlApplicationEngine:
    """Expose Python objects to QML and load Main.qml."""
    # Must happen before the engine exists: registering afterwards breaks QtQuick type
    # resolution ("expected QObject" errors).
    qmlRegisterSingletonInstance(AppState, QML_URI, 1, 0, "AppState", state)
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
    paths.assets_dir()
    global_space = SpaceRepository(conn).ensure_global()

    # Services are the only write path. Kept referenced here so they outlive the engine.
    node_service = NodeService(NodeRepository(conn))  # noqa: F841
    state = AppState(global_space.id)

    engine = create_engine(state)
    if not engine.rootObjects():
        return 1

    app.aboutToQuit.connect(conn.close)
    return app.exec()
