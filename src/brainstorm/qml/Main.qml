import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import Brainstorm
import "components"

ApplicationWindow {
    id: window

    width: 1280
    height: 800
    minimumWidth: 800
    minimumHeight: 500
    visible: true
    title: "Brainstorm"
    color: Theme.background

    // Geometry is restored by Settings (QSettings) before this runs.
    Component.onCompleted: {
        // A saved position can end up off-screen (monitor unplugged); recenter then.
        let onScreen = false
        for (const s of Qt.application.screens) {
            if (x + 100 > s.virtualX && x + 100 < s.virtualX + s.width
                    && y + 20 > s.virtualY && y + 20 < s.virtualY + s.height)
                onScreen = true
        }
        if (!onScreen) {
            const s = Qt.application.screens[0]
            x = s.virtualX + (s.width - width) / 2
            y = s.virtualY + (s.height - height) / 2
        }
    }

    Settings {
        category: "window"
        property alias x: window.x
        property alias y: window.y
        property alias width: window.width
        property alias height: window.height
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Sidebar
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: Theme.sidebarWidth
            color: Theme.surface

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.spacing
                spacing: 2

                Text {
                    Layout.margins: Theme.spacing
                    text: "Brainstorm"
                    color: Theme.text
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.fontSizeTitle
                    font.bold: true
                }

                SidebarItem {
                    Layout.fillWidth: true
                    label: "Board"
                    selected: AppState.currentView === "board"
                    onClicked: AppState.currentView = "board"
                }
                SidebarItem {
                    Layout.fillWidth: true
                    label: "Projects"
                    selected: AppState.currentView === "projects"
                    onClicked: AppState.currentView = "projects"
                }

                Item { Layout.preferredHeight: Theme.spacing }

                SidebarItem { Layout.fillWidth: true; label: "Resources"; placeholder: true }
                SidebarItem { Layout.fillWidth: true; label: "Docs"; placeholder: true }
                SidebarItem { Layout.fillWidth: true; label: "Code"; placeholder: true }

                Item { Layout.fillHeight: true }
            }
        }

        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: 1
            color: Theme.border
        }

        // Content area
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Text {
                anchors.centerIn: parent
                horizontalAlignment: Text.AlignHCenter
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSizeTitle
                text: AppState.currentView === "board"
                    ? "Board\nThe canvas arrives in Phase 2."
                    : "Projects\nNo projects yet."
            }
        }
    }
}
