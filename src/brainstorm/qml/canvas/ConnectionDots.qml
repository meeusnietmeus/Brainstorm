import QtQuick
import "../components"

// Four dots on the sides of the selected node. Drag from one to connect to another node, or
// release on empty canvas to create a new connected note.
Item {
    id: root

    required property Item target // the NodeDelegate
    readonly property real zoom: target.canvas.zoom

    Repeater {
        model: [
            { fx: 0.5, fy: 0, dx: 0, dy: -1 },
            { fx: 1, fy: 0.5, dx: 1, dy: 0 },
            { fx: 0.5, fy: 1, dx: 0, dy: 1 },
            { fx: 0, fy: 0.5, dx: -1, dy: 0 }
        ]

        delegate: Rectangle {
            id: dot

            required property var modelData

            objectName: "connectionDot"
            width: 10 / root.zoom
            height: width
            radius: width / 2
            // Just outside the node so the dots do not collide with the resize handles.
            x: modelData.fx * root.width + modelData.dx * 14 / root.zoom - width / 2
            y: modelData.fy * root.height + modelData.dy * 14 / root.zoom - height / 2
            color: area.containsMouse || area.pressed ? Theme.accent : Theme.background
            border.width: 1.5 / root.zoom
            border.color: Theme.accent

            MouseArea {
                id: area
                anchors.fill: parent
                anchors.margins: -5 / root.zoom
                hoverEnabled: true
                preventStealing: true
                cursorShape: Qt.CrossCursor

                function worldPoint(mouse) {
                    return mapToItem(root.target.parent, mouse.x, mouse.y)
                }

                onPressed: mouse => {
                    // The line starts at the middle of the side, not at the dot.
                    const side = root.target.mapToItem(root.target.parent,
                                                       dot.modelData.fx * root.width,
                                                       dot.modelData.fy * root.height)
                    root.target.canvas.beginConnect(root.target.nodeId, side)
                    root.target.canvas.updateConnect(worldPoint(mouse))
                }
                onPositionChanged: mouse => root.target.canvas.updateConnect(worldPoint(mouse))
                onReleased: mouse => root.target.canvas.finishConnect(worldPoint(mouse))
            }
        }
    }
}
