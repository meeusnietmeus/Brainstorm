import QtQuick
import "../components"

// A titled, translucent rectangle that groups nodes visually. Only the title bar takes mouse
// input (the delegate arranges that), so the inside stays usable for the nodes it contains.
Item {
    id: root

    property string title
    property string tint: "#6ea8fe"
    property bool selected: false
    property bool editing: false
    property real zoom: 1

    readonly property real headerHeight: 34

    signal titleFinished(string text)

    property bool _open: false

    function finishEditing(save) {
        if (!_open)
            return
        _open = false
        titleFinished(save ? input.text : root.title)
    }

    onEditingChanged: {
        if (editing) {
            _open = true
            input.text = title
            input.forceActiveFocus()
            input.selectAll()
        } else {
            finishEditing(true)
            input.focus = false
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: Qt.rgba(Qt.color(root.tint).r, Qt.color(root.tint).g, Qt.color(root.tint).b, 0.10)
        border.width: (root.selected ? 3 : 2) / root.zoom
        border.color: root.selected ? Theme.accent
                                    : Qt.rgba(Qt.color(root.tint).r, Qt.color(root.tint).g,
                                              Qt.color(root.tint).b, 0.55)
    }

    Rectangle {
        width: parent.width
        height: root.headerHeight
        radius: 10
        color: Qt.rgba(Qt.color(root.tint).r, Qt.color(root.tint).g, Qt.color(root.tint).b, 0.22)

        Text {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            verticalAlignment: Text.AlignVCenter
            visible: !root.editing
            text: root.title !== "" ? root.title : "Untitled frame"
            elide: Text.ElideRight
            color: root.title !== "" ? Theme.text : Theme.textDisabled
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSize + 2
            font.bold: true
        }

        TextInput {
            id: input
            objectName: "frameTitleInput"
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            verticalAlignment: TextInput.AlignVCenter
            visible: root.editing
            clip: true
            color: Theme.text
            selectionColor: Theme.accent
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSize + 2
            font.bold: true

            Keys.onReturnPressed: root.finishEditing(true)
            Keys.onEnterPressed: root.finishEditing(true)
            Keys.onEscapePressed: root.finishEditing(false)
            onActiveFocusChanged: if (!activeFocus) root.finishEditing(true)
        }
    }
}
