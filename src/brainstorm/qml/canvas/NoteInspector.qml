import QtQuick
import QtQuick.Layouts
import Brainstorm
import "../components"

// Small floating toolbar above the selected note (screen space, not scaled with the canvas).
Rectangle {
    id: root

    required property Item canvas

    readonly property Item note: canvas.selectedItem
    readonly property bool shown: note !== null && note.kind === "note" && note.selected
                                  && !note.editing && !note.resizing
    readonly property point anchorPoint: note
        ? canvas.worldToScreen(Qt.point(note.x, note.y)) : Qt.point(0, 0)

    visible: shown
    x: Math.max(4, Math.min(canvas.width - width - 4, anchorPoint.x))
    y: Math.max(4, anchorPoint.y - height - 8)
    width: row.implicitWidth + 2 * Theme.spacing
    height: row.implicitHeight + 2 * Theme.spacing
    radius: Theme.radius
    color: Theme.surface
    border.width: 1
    border.color: Theme.border
    z: 1000

    // Swallow clicks so they do not fall through to the canvas behind.
    MouseArea {
        anchors.fill: parent
    }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 4

        FlatButton {
            text: "Plain"
            checked: (root.note?.props.style ?? "plain") === "plain"
            onClicked: CanvasController.setProp(root.note.nodeId, "style", "plain")
        }
        FlatButton {
            text: "Card"
            checked: root.note?.props.style === "card"
            onClicked: CanvasController.setProp(root.note.nodeId, "style", "card")
        }
        Item { Layout.preferredWidth: 6 }
        Repeater {
            model: ["S", "M", "L"]
            delegate: FlatButton {
                required property string modelData
                text: modelData
                checked: (root.note?.props.fontSize ?? "M") === modelData
                onClicked: CanvasController.setProp(root.note.nodeId, "fontSize", modelData)
            }
        }
        Item { Layout.preferredWidth: 6 }
        FlatButton {
            text: "Auto height"
            checked: root.note ? root.note.autoHeight : false
            onClicked: CanvasController.setProp(root.note.nodeId, "fixedHeight", root.note.autoHeight)
        }
    }
}
