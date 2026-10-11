import QtQuick
import QtQuick.Layouts
import Brainstorm
import "../components"

// Tint picker above the selected frame.
Rectangle {
    id: root

    required property Item canvas

    readonly property Item frame: canvas.selectedItem
    readonly property var tints: ["#6ea8fe", "#6fcf97", "#f2c94c", "#eb5757", "#bb86fc", "#8b92a1"]
    readonly property bool shown: frame !== null && frame.isFrame && frame.selected
                                  && !frame.editing && !frame.resizing && !canvas.carried[frame.nodeId]
    readonly property point anchorPoint: frame
        ? canvas.worldToScreen(Qt.point(frame.x, frame.y)) : Qt.point(0, 0)

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

    MouseArea {
        anchors.fill: parent
    }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 6

        Text {
            text: "Tint"
            color: Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSize
        }
        Repeater {
            model: root.tints
            delegate: Rectangle {
                required property string modelData

                objectName: "tintSwatch"
                implicitWidth: 22
                implicitHeight: 22
                radius: 11
                color: modelData
                border.width: (root.frame?.props.tint ?? "#6ea8fe") === modelData ? 2 : 0
                border.color: Theme.text

                MouseArea {
                    anchors.fill: parent
                    onClicked: CanvasController.setProp(root.frame.nodeId, "tint", parent.modelData)
                }
            }
        }
    }
}
