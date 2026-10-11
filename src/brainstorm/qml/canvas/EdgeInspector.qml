import QtQuick
import QtQuick.Layouts
import Brainstorm
import "../components"

// Style options next to the selected arrow's midpoint chip.
Rectangle {
    id: root

    required property Item canvas

    readonly property Item edge: canvas.selectedEdgeItem
    readonly property bool shown: canvas.selectedEdgeId !== "" && edge !== null && edge.valid
                                  && edge.selected && !edge.editing
    readonly property point anchorPoint: shown
        ? canvas.worldToScreen(Qt.point(edge.g.mid.x, edge.g.mid.y)) : Qt.point(0, 0)

    visible: shown
    x: Math.max(4, Math.min(canvas.width - width - 4, anchorPoint.x - width / 2))
    y: Math.max(4, anchorPoint.y - height - 22)
    width: row.implicitWidth + 2 * Theme.spacing
    height: row.implicitHeight + 2 * Theme.spacing
    radius: Theme.radius
    color: Theme.surface
    border.width: 1
    border.color: Theme.border
    z: 1000

    MouseArea {
        anchors.fill: parent
    }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 4

        FlatButton {
            text: "Dashed"
            checked: root.edge?.model.dashed ?? false
            onClicked: CanvasController.setEdgeStyle(root.edge.edgeId, "dashed", !root.edge.model.dashed)
        }
        Item { Layout.preferredWidth: 6 }
        Repeater {
            model: [{ key: "end", text: "Arrow" }, { key: "both", text: "Both" }, { key: "none", text: "Line" }]
            delegate: FlatButton {
                required property var modelData
                text: modelData.text
                checked: root.edge?.model.arrow === modelData.key
                onClicked: CanvasController.setEdgeStyle(root.edge.edgeId, "arrow", modelData.key)
            }
        }
        Item { Layout.preferredWidth: 6 }
        FlatButton {
            text: "Label"
            onClicked: root.canvas.editingEdgeId = root.edge.edgeId
        }
    }
}
