import QtQuick
import Brainstorm
import "../components"

// Pannable, zoomable viewport. All nodes live in `world`, which is moved and scaled; node
// positions are float world coordinates and are only converted to screen coordinates here.
FocusScope {
    id: root
    objectName: "boardCanvas"

    property string spaceId: AppState.currentSpaceId
    property string selectedId: ""
    property bool spaceHeld: false
    readonly property real zoom: world.scale

    property bool _restored: false
    property string _viewSpaceId: "" // the space whose view is currently on screen

    clip: true

    function screenToWorld(p) {
        return Qt.point((p.x - world.x) / world.scale, (p.y - world.y) / world.scale)
    }

    function worldToScreen(p) {
        return Qt.point(p.x * world.scale + world.x, p.y * world.scale + world.y)
    }

    function viewportCenterWorld() {
        return screenToWorld(Qt.point(width / 2, height / 2))
    }

    // Zoom by `factor`, keeping the world point under `cursor` (viewport coordinates) fixed.
    function zoomAt(cursor, factor) {
        const r = CanvasController.zoomAt(world.x, world.y, world.scale, cursor.x, cursor.y, factor)
        world.x = r[0]
        world.y = r[1]
        world.scale = r[2]
    }

    function resetView() {
        world.scale = 1
        world.x = width / 2
        world.y = height / 2
    }

    function select(id) {
        selectedId = id
        forceActiveFocus()
    }

    function addNoteAt(worldPoint) {
        select(CanvasController.createNoteCentered(worldPoint.x, worldPoint.y))
    }

    function addNoteAtCenter() {
        addNoteAt(viewportCenterWorld())
    }

    function _restoreViewState() {
        if (width <= 0 || height <= 0)
            return
        const s = CanvasController.loadViewState(spaceId)
        if (s.scale !== undefined) {
            world.scale = s.scale
            world.x = s.x
            world.y = s.y
        } else {
            resetView() // first visit: world origin in the middle of the viewport
        }
        selectedId = ""
        _viewSpaceId = spaceId
        _restored = true
    }

    function _saveViewState() {
        if (_restored)
            CanvasController.saveViewState(_viewSpaceId, world.x, world.y, world.scale)
    }

    onWidthChanged: if (!_restored) _restoreViewState()
    onHeightChanged: if (!_restored) _restoreViewState()
    onSpaceIdChanged: {
        if (saveTimer.running) { // flush the old space's view before switching
            saveTimer.stop()
            _saveViewState()
        }
        _restored = false
        _restoreViewState()
    }

    Keys.onPressed: event => {
        if (event.key === Qt.Key_Space && !event.isAutoRepeat) {
            spaceHeld = true
            event.accepted = true
        }
    }
    Keys.onReleased: event => {
        if (event.key === Qt.Key_Space && !event.isAutoRepeat) {
            spaceHeld = false
            event.accepted = true
        }
    }
    Keys.onDeletePressed: {
        if (selectedId !== "") {
            CanvasController.deleteNode(selectedId)
            selectedId = ""
        }
    }
    onActiveFocusChanged: if (!activeFocus) spaceHeld = false

    // Debounced persistence of pan and zoom; flushed on quit.
    Timer {
        id: saveTimer
        interval: 500
        onTriggered: root._saveViewState()
    }
    Connections {
        target: Qt.application
        function onAboutToQuit() {
            if (saveTimer.running) {
                saveTimer.stop()
                root._saveViewState()
            }
        }
    }

    // Dot grid: one tile image (32 world units) repeated across the viewport. It is positioned
    // modulo the tile size and scaled with the zoom, so panning and zooming cost nothing.
    Image {
        id: grid

        readonly property real tile: 32
        readonly property real cell: tile * world.scale

        source: "dot.png"
        fillMode: Image.Tile
        smooth: true
        visible: cell >= 8
        scale: world.scale
        transformOrigin: Item.TopLeft
        width: root.width / world.scale + 2 * tile
        height: root.height / world.scale + 2 * tile
        x: ((world.x - cell / 2) % cell) - cell
        y: ((world.y - cell / 2) % cell) - cell
    }

    // Empty-canvas interaction: click clears the selection, double-click adds a note.
    MouseArea {
        anchors.fill: parent
        enabled: !root.spaceHeld
        onPressed: root.forceActiveFocus()
        onClicked: root.selectedId = ""
        onDoubleClicked: mouse => root.addNoteAt(root.screenToWorld(Qt.point(mouse.x, mouse.y)))
    }

    Item {
        id: world
        objectName: "world"

        transformOrigin: Item.TopLeft

        onXChanged: saveTimer.restart()
        onYChanged: saveTimer.restart()
        onScaleChanged: saveTimer.restart()

        Repeater {
            model: CanvasController.nodes
            delegate: NodeDelegate {
                canvas: root
            }
        }
    }

    // Navigation
    WheelHandler {
        id: wheel
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: event => root.zoomAt(wheel.point.position, Math.pow(1.0015, event.angleDelta.y))
    }
    DragHandler {
        acceptedButtons: Qt.MiddleButton
        target: world
    }
    DragHandler {
        acceptedButtons: Qt.LeftButton
        enabled: root.spaceHeld
        target: world
    }
    PinchHandler {
        id: pinch
        target: null
        onScaleChanged: delta => root.zoomAt(pinch.centroid.position, delta)
    }
    HoverHandler {
        cursorShape: root.spaceHeld ? Qt.OpenHandCursor : Qt.ArrowCursor
    }

    // Hint for an empty board
    Text {
        anchors.centerIn: parent
        visible: CanvasController.nodes.count === 0
        text: "Double-click to add a note"
        color: Theme.textDisabled
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeTitle
    }
}
