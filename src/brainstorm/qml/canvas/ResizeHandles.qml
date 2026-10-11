import QtQuick
import Brainstorm
import "../components"

// Four corner handles. They live in world space, so their size is divided by the zoom to stay
// constant on screen. While dragging, the target shows `liveRect`; the write happens on release.
Item {
    id: root

    required property Item target // the NodeDelegate
    readonly property real zoom: target.canvas.zoom

    Repeater {
        model: [
            { cx: 0, cy: 0 }, { cx: 1, cy: 0 }, { cx: 0, cy: 1 }, { cx: 1, cy: 1 }
        ]

        delegate: Rectangle {
            id: handle

            required property var modelData

            objectName: "resizeHandle"
            width: 10 / root.zoom
            height: width
            x: modelData.cx * root.width - width / 2
            y: modelData.cy * root.height - height / 2
            color: Theme.background
            border.width: 1.5 / root.zoom
            border.color: Theme.accent

            MouseArea {
                anchors.fill: parent
                anchors.margins: -4 / root.zoom
                preventStealing: true
                cursorShape: handle.modelData.cx === handle.modelData.cy ? Qt.SizeFDiagCursor
                                                                         : Qt.SizeBDiagCursor

                property real anchorX
                property real anchorY
                property real startW
                property real startH
                property bool touchedHeight: false

                onPressed: {
                    const t = root.target
                    // The opposite corner stays where it is.
                    anchorX = handle.modelData.cx === 0 ? t.x + t.width : t.x
                    anchorY = handle.modelData.cy === 0 ? t.y + t.height : t.y
                    startW = t.width
                    startH = t.height
                    touchedHeight = false
                    t.liveRect = Qt.rect(t.x, t.y, t.width, t.height)
                    t.resizing = true
                }

                onPositionChanged: mouse => {
                    const t = root.target
                    const p = mapToItem(t.parent, mouse.x, mouse.y) // pointer in world coordinates
                    let w = Math.max(t.minWidth, Math.abs(p.x - anchorX))
                    let h = Math.max(t.minHeight, Math.abs(p.y - anchorY))

                    if (t.keepAspect && !(mouse.modifiers & Qt.ShiftModifier)) {
                        const aspect = startW / startH
                        w = Math.max(w, h * aspect)
                        h = w / aspect
                    } else if (t.autoHeight) {
                        // Text height follows its content unless the user drags vertically.
                        if (Math.abs(h - startH) > 3 / root.zoom)
                            touchedHeight = true
                        if (!touchedHeight)
                            h = startH
                    }

                    t.liveRect = Qt.rect(handle.modelData.cx === 0 ? anchorX - w : anchorX,
                                         handle.modelData.cy === 0 ? anchorY - h : anchorY, w, h)
                }

                onReleased: {
                    const t = root.target
                    const r = t.liveRect
                    const props = touchedHeight ? { "fixedHeight": true } : {}
                    CanvasController.resizeNode(t.nodeId, r.x, r.y, r.width, r.height, props)
                    t.resizing = false
                }
            }
        }
    }
}
