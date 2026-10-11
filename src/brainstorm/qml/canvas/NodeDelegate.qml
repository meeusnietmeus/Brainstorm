import QtQuick
import Brainstorm

// One node on the canvas: position, selection, dragging and resizing. The visual comes from a
// Loader that picks a component by kind.
Item {
    id: slot

    required property var model
    required property Item canvas

    readonly property string nodeId: model.nodeId
    readonly property string kind: model.kind
    readonly property var props: model.props ?? ({})
    readonly property bool selected: canvas.selectedId === nodeId
    readonly property bool editing: canvas.editingId === nodeId

    // Resizing: the handles drive liveRect while dragging, and commit once on release.
    property bool resizing: false
    property rect liveRect: Qt.rect(0, 0, 0, 0)
    readonly property bool keepAspect: kind === "image"
    // Notes grow with their text unless the user has set a height.
    readonly property bool autoHeight: kind === "note" && !(props.fixedHeight ?? false)
    readonly property bool isFrame: kind === "frame"
    readonly property real minWidth: isFrame ? 120 : (kind === "note" ? 80 : 40)
    readonly property real minHeight: isFrame ? 80 : (kind === "note" ? 40 : 30)
    // While a frame is dragged, the nodes inside it follow by this offset (see Canvas.carried).
    readonly property real carryX: canvas.carried[nodeId] ? canvas.carryOffset.x : 0
    readonly property real carryY: canvas.carried[nodeId] ? canvas.carryOffset.y : 0
    readonly property real naturalHeight: loader.item && loader.item.naturalHeight !== undefined
        ? loader.item.naturalHeight : 0

    visible: model.onCanvas
    width: resizing ? liveRect.width : (model.w ?? 200)
    height: resizing ? liveRect.height
                     : (autoHeight && naturalHeight > 0 ? naturalHeight : (model.h ?? 100))
    z: isFrame ? model.z - 1000000 : model.z // frames live in a band below everything else

    onSelectedChanged: if (selected) canvas.selectedItem = slot

    Component.onCompleted: canvas.registerNode(nodeId, slot)
    Component.onDestruction: canvas.unregisterNode(nodeId)

    function _updateCarry() {
        if (drag.active && isFrame)
            canvas.carryOffset = Qt.point(slot.x - drag.startX, slot.y - drag.startY)
    }
    onXChanged: _updateCarry()
    onYChanged: _updateCarry()

    // While dragging, the handler owns x/y. On release the new position is committed once and
    // the bindings take over again (RestoreNone keeps the dragged value until then).
    Binding {
        target: slot
        property: "x"
        value: slot.resizing ? slot.liveRect.x : (slot.model.x ?? 0) + slot.carryX
        when: !drag.active
        restoreMode: Binding.RestoreNone
    }
    Binding {
        target: slot
        property: "y"
        value: slot.resizing ? slot.liveRect.y : (slot.model.y ?? 0) + slot.carryY
        when: !drag.active
        restoreMode: Binding.RestoreNone
    }

    Loader {
        id: loader
        anchors.fill: parent
        active: slot.model.onCanvas
        sourceComponent: {
            switch (slot.kind) {
            case "note": return noteNode
            case "image": return imageNode
            case "frame": return frameNode
            default: return genericNode
            }
        }
    }

    Component {
        id: genericNode
        NodeBase {
            title: slot.model.title
            selected: slot.selected
            zoom: slot.canvas.zoom
        }
    }

    Component {
        id: noteNode
        NoteNode {
            body: slot.model.body
            noteStyle: slot.props.style ?? "plain"
            fontSizeKey: slot.props.fontSize ?? "M"
            selected: slot.selected
            editing: slot.editing
            zoom: slot.canvas.zoom
            onEditFinished: (text, height) => {
                slot.canvas.editingId = "" // first, so losing focus below does not commit twice
                CanvasController.commitNoteText(slot.nodeId, text, height)
                slot.canvas.forceActiveFocus()
            }
        }
    }

    Component {
        id: frameNode
        FrameNode {
            title: slot.model.title
            tint: slot.props.tint ?? "#6ea8fe"
            selected: slot.selected
            editing: slot.editing
            zoom: slot.canvas.zoom
            onTitleFinished: text => {
                slot.canvas.editingId = ""
                CanvasController.setTitle(slot.nodeId, text)
                slot.canvas.forceActiveFocus()
            }
        }
    }

    Component {
        id: imageNode
        ImageNode {
            source: CanvasController.assetUrl(slot.props.asset ?? "")
            pending: slot.props.pending ?? false
            error: slot.props.error ?? ""
            selected: slot.selected
            zoom: slot.canvas.zoom
        }
    }

    // Frames react only on their title bar, so the inside stays free for the nodes it holds.
    MouseArea {
        id: hit
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: slot.isFrame ? 34 : parent.height
        enabled: !slot.canvas.spaceHeld && !slot.editing
        onPressed: slot.canvas.select(slot.nodeId)
        onDoubleClicked: {
            if (slot.kind === "note" || slot.isFrame)
                slot.canvas.editingId = slot.nodeId
            else if (slot.kind === "link" && String(slot.props.url ?? "").startsWith("http"))
                Qt.openUrlExternally(slot.props.url)
        }

        DragHandler {
            id: drag

            property real startX
            property real startY

            target: slot
            acceptedButtons: Qt.LeftButton
            enabled: !slot.canvas.spaceHeld && !slot.editing
            onActiveChanged: {
                if (active) {
                    startX = slot.x
                    startY = slot.y
                    if (slot.isFrame)
                        slot.canvas.beginCarry(CanvasController.nodesInsideFrame(slot.nodeId))
                } else if (slot.isFrame) {
                    CanvasController.moveFrame(slot.nodeId, slot.x, slot.y)
                    slot.canvas.endCarry()
                } else {
                    CanvasController.moveNode(slot.nodeId, slot.x, slot.y)
                }
            }
        }
    }

    ResizeHandles {
        anchors.fill: parent
        target: slot
        visible: slot.selected && !slot.editing
    }

    ConnectionDots {
        anchors.fill: parent
        target: slot
        visible: slot.selected && !slot.editing && !slot.isFrame && !slot.resizing
    }
}
