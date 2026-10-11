"""Loads Main.qml headlessly to catch QML syntax and import errors."""

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuickControls2 import QQuickStyle

from brainstorm.app_state import AppState
from brainstorm.main import create_engine


@pytest.fixture(scope="module")
def qapp():
    import os

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication.instance() or QGuiApplication([])
    app.setOrganizationName("BrainstormTest")
    app.setApplicationName("BrainstormTest")
    return app


def test_main_qml_loads(qapp):
    engine = create_engine(AppState("space-1"))
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    assert window.property("title") == "Brainstorm"
    engine.deleteLater()
