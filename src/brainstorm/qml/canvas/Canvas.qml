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
    property string editingId: "" // note being edited, if any
    property Item selectedItem: null // NodeDelegate of the selected node
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
        if (editingId !== "" && editingId !== id)
            editingId = "" // leaving a note commits its edit
        selectedId = id
        forceActiveFocus()
    }

    function addNoteAt(worldPoint) {
        const id = CanvasController.createNoteCentered(worldPoint.x, worldPoint.y)
        select(id)
        editingId = id // new notes open straight into edit mode
    }

    // Where pasted content goes: under the cursor, or the viewport center if it is elsewhere.
    function pasteAtCursor() {
        const at = hover.hovered ? hover.point.position : Qt.point(width / 2, height / 2)
        const w = screenToWorld(at)
        const ids = CanvasController.paste(w.x, w.y)
        if (ids.length > 0)
            select(ids[0])
    }

    function deleteSelected() {
        if (selectedId === "")
            return
        editingId = ""
        CanvasController.deleteNode(selectedId)
        selectedId = ""
    }

    function moveSelectedInZ(delta) {
        if (selectedId !== "")
            CanvasController.moveInZ(selectedId, delta)
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
        } else if (event.matches(StandardKey.Paste)) {
            pasteAtCursor()
            event.accepted = true
        } else if (selectedId !== "" && event.key === Qt.Key_BracketRight) {
            moveSelectedInZ(1)
            event.accepted = true
        } else if (selectedId !== "" && event.key === Qt.Key_BracketLeft) {
            moveSelectedInZ(-1)
            event.accepted = true
        }
    }
    Keys.onReleased: event => {
        if (event.key === Qt.Key_Space && !event.isAutoRepeat) {
            spaceHeld = false
            event.accepted = true
        }
    }
    Keys.onDeletePressed: deleteSelected()
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
        onClicked: {
            root.selectedId = ""
            root.editingId = ""
        }
        onDoubleClicked: mouse => root.addNoteAt(root.screenToWorld(Qt.point(mouse.x, mouse.y)))
    }

    // Images dragged in from a browser arrive as a URL, local files as file URLs.
    DropArea {
        anchors.fill: parent
        onDropped: drop => {
            const at = root.screenToWorld(Qt.point(drop.x, drop.y))
            const urls = []
            if (drop.hasUrls)
                for (const u of drop.urls)
                    urls.push(u.toString())
            const ids = CanvasController.importDrop(urls, drop.hasHtml ? drop.html : "",
                                                    drop.hasText ? drop.text : "", at.x, at.y)
            if (ids.length > 0)
                root.select(ids[0])
        }
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
    // Panning moves `world` by the drag's translation. (Using the handler's `target` would make
    // the zero-sized world item jump so its origin sits under the cursor.)
    DragHandler {
        id: middlePan
        acceptedButtons: Qt.MiddleButton
        target: null
        property point start
        onActiveChanged: if (active) start = Qt.point(world.x, world.y)
        onTranslationChanged: {
            if (active) {
                world.x = start.x + translation.x
                world.y = start.y + translation.y
            }
        }
    }
    DragHandler {
        id: spacePan
        acceptedButtons: Qt.LeftButton
        enabled: root.spaceHeld
        target: null
        property point start
        onActiveChanged: if (active) start = Qt.point(world.x, world.y)
        onTranslationChanged: {
            if (active) {
                world.x = start.x + translation.x
                world.y = start.y + translation.y
            }
        }
    }
    PinchHandler {
        id: pinch
        target: null
        onScaleChanged: delta => root.zoomAt(pinch.centroid.position, delta)
    }
    HoverHandler {
        id: hover
        cursorShape: root.spaceHeld ? Qt.OpenHandCursor : Qt.ArrowCursor
    }

    NoteInspector {
        canvas: root
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
