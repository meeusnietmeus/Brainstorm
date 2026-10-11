import QtQuick
import QtQuick.Layouts
import "../canvas"
import "../components"

ColumnLayout {
    id: root

    property alias canvas: canvas

    spacing: 0

    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: 44
        color: Theme.surface

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacingLarge
            anchors.rightMargin: Theme.spacingLarge
            spacing: Theme.spacing

            FlatButton {
                text: "Add note"
                onClicked: canvas.addNoteAtCenter()
            }
            Item { Layout.fillWidth: true }
            Text {
                text: Math.round(canvas.zoom * 100) + "%"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fontSize
            }
            FlatButton {
                text: "Reset view"
                onClicked: canvas.resetView()
            }
        }
    }

    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: 1
        color: Theme.border
    }

    Canvas {
        id: canvas
        Layout.fillWidth: true
        Layout.fillHeight: true
        focus: true
    }
}
