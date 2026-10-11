import QtQuick
import QtQuick.Shapes
import Brainstorm
import "../components"

// One arrow. It follows the live position of its two node delegates (not the model), because
// during a drag the database has not been written yet.
Item {
    id: root
    objectName: "edgeItem"

    required property var model
    required property Item canvas

    readonly property string edgeId: model.edgeId
    readonly property Item src: canvas.nodeItems[model.sourceId] ?? null
    readonly property Item dst: canvas.nodeItems[model.targetId] ?? null
    readonly property bool valid: src !== null && dst !== null && src.visible && dst.visible
    readonly property bool selected: canvas.selectedEdgeId === edgeId
    readonly property bool editing: canvas.editingEdgeId === edgeId

    // Line and arrowheads keep a readable size on screen when zoomed out.
    readonly property real unit: 1 / Math.min(1, canvas.zoom)
    readonly property var g: valid
        ? CanvasController.edgeGeometry(src.x, src.y, src.width, src.height,
                                        dst.x, dst.y, dst.width, dst.height, 12 * unit)
        : null
    readonly property color lineColor: selected ? Theme.accent
        : (model.color !== "" ? model.color : Theme.textMuted)
    readonly property bool headAtEnd: model.arrow === "end" || model.arrow === "both"
    readonly property bool headAtStart: model.arrow === "both"

    visible: valid

    onSelectedChanged: if (selected) canvas.selectedEdgeItem = root

    Shape {
        antialiasing: true

        ShapePath {
            strokeColor: root.lineColor
            strokeWidth: (root.selected ? 3 : 2) * root.unit
            strokeStyle: root.model.dashed ? ShapePath.DashLine : ShapePath.SolidLine
            dashPattern: [4, 3]
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            startX: root.g ? root.g.start.x : 0
            startY: root.g ? root.g.start.y : 0
            PathCubic {
                x: root.g ? root.g.end.x : 0
                y: root.g ? root.g.end.y : 0
                control1X: root.g ? root.g.c1.x : 0
                control1Y: root.g ? root.g.c1.y : 0
                control2X: root.g ? root.g.c2.x : 0
                control2Y: root.g ? root.g.c2.y : 0
            }
        }

        ShapePath {
            strokeColor: "transparent"
            fillColor: root.headAtEnd ? root.lineColor : "transparent"
            startX: root.g ? root.g.end.x : 0
            startY: root.g ? root.g.end.y : 0
            PathLine { x: root.g ? root.g.headEnd[0].x : 0; y: root.g ? root.g.headEnd[0].y : 0 }
            PathLine { x: root.g ? root.g.headEnd[1].x : 0; y: root.g ? root.g.headEnd[1].y : 0 }
            PathLine { x: root.g ? root.g.end.x : 0; y: root.g ? root.g.end.y : 0 }
        }

        ShapePath {
            strokeColor: "transparent"
            fillColor: root.headAtStart ? root.lineColor : "transparent"
            startX: root.g ? root.g.start.x : 0
            startY: root.g ? root.g.start.y : 0
            PathLine { x: root.g ? root.g.headStart[0].x : 0; y: root.g ? root.g.headStart[0].y : 0 }
            PathLine { x: root.g ? root.g.headStart[1].x : 0; y: root.g ? root.g.headStart[1].y : 0 }
            PathLine { x: root.g ? root.g.start.x : 0; y: root.g ? root.g.start.y : 0 }
        }
    }

    // Strokes cannot be hit-tested, so each edge has a chip at its midpoint: the label, or a
    // dot when there is none. Click selects, double-click edits the label.
    Rectangle {
        id: chip

        objectName: "edgeChip"
        readonly property bool hasLabel: root.model.label !== "" || root.editing

        x: (root.g ? root.g.mid.x : 0) - width / 2
        y: (root.g ? root.g.mid.y : 0) - height / 2
        width: hasLabel ? Math.max(28, labelSizer.implicitWidth + 16) : 14
        height: hasLabel ? 22 : 14
        radius: height / 2
        color: root.selected || root.editing ? Theme.accent : Theme.surface
        border.width: 1
        border.color: root.selected || root.editing ? Theme.accent : root.lineColor
        scale: 1 / canvas.zoom // constant on-screen size
        transformOrigin: Item.Center

        Text {
            id: labelSizer
            visible: false
            text: root.editing ? input.text : root.model.label
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSize
        }

        Text {
            anchors.centerIn: parent
            visible: !root.editing && chip.hasLabel
            text: root.model.label
            color: root.selected ? Theme.background : Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSize
        }

        TextInput {
            id: input

            property bool open: false

            anchors.centerIn: parent
            visible: root.editing
            width: Math.max(24, parent.width - 16)
            horizontalAlignment: TextInput.AlignHCenter
            color: Theme.background
            selectionColor: Theme.surface
            selectedTextColor: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSize

            function finish(save) {
                if (!open)
                    return
                open = false
                const text = input.text
                root.canvas.editingEdgeId = ""
                if (save)
                    CanvasController.setEdgeLabel(root.edgeId, text)
                root.canvas.forceActiveFocus()
            }

            Keys.onReturnPressed: finish(true)
            Keys.onEnterPressed: finish(true)
            Keys.onEscapePressed: finish(false)
            onActiveFocusChanged: if (!activeFocus) finish(true)
        }

        Connections {
            target: root
            function onEditingChanged() {
                if (root.editing) {
                    input.open = true
                    input.text = root.model.label
                    input.forceActiveFocus()
                    input.selectAll()
                } else {
                    input.finish(true) // clicked away
                    input.focus = false
                }
            }
        }

        MouseArea {
            anchors.fill: parent
            onPressed: root.canvas.selectEdge(root.edgeId)
            onDoubleClicked: root.canvas.editingEdgeId = root.edgeId
            enabled: !root.editing
        }
    }
}
