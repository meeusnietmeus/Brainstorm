import QtQuick
import Brainstorm

// One node on the canvas: position, selection and dragging. The visual comes from a Loader.
Item {
    id: slot

    required property var model
    required property Item canvas

    readonly property string nodeId: model.nodeId

    visible: model.onCanvas
    width: model.w ?? 200
    height: model.h ?? 100
    z: model.z

    // While dragging, the handler owns x/y. On release the new position is committed once and
    // the bindings take over again (RestoreNone keeps the dragged value until then).
    Binding {
        target: slot
        property: "x"
        value: slot.model.x ?? 0
        when: !drag.active
        restoreMode: Binding.RestoreNone
    }
    Binding {
        target: slot
        property: "y"
        value: slot.model.y ?? 0
        when: !drag.active
        restoreMode: Binding.RestoreNone
    }

    Loader {
        anchors.fill: parent
        active: slot.model.onCanvas
        sourceComponent: genericNode // later phases pick a component by slot.model.kind
    }

    Component {
        id: genericNode
        NodeBase {
            title: slot.model.title
            selected: slot.canvas.selectedId === slot.nodeId
            zoom: slot.canvas.zoom
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: !slot.canvas.spaceHeld
        onPressed: slot.canvas.select(slot.nodeId)
    }

    DragHandler {
        id: drag
        target: slot
        acceptedButtons: Qt.LeftButton
        enabled: !slot.canvas.spaceHeld
        onActiveChanged: {
            if (!active)
                CanvasController.moveNode(slot.nodeId, slot.x, slot.y)
        }
    }
}
