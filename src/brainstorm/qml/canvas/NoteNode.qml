import QtQuick
import "../components"

// Text note. Not editing: the body is rendered as Markdown. Editing: raw text in a TextEdit.
Item {
    id: root
    objectName: "noteNode"

    property string body
    property string noteStyle: "plain" // plain: loose text, card: filled box
    property string fontSizeKey: "M"
    property bool selected: false
    property bool editing: false
    property real zoom: 1

    // Height the note needs for its text at the current width (used unless the user fixed it).
    readonly property real naturalHeight: Math.max(
        40, (editing ? edit.contentHeight : view.contentHeight) + 2 * padding)

    readonly property bool rendersMarkdown: !editing && view.textFormat === Text.MarkdownText
    readonly property real padding: 12
    readonly property real fontPixels: ({ "S": 13, "M": 17, "L": 24 })[fontSizeKey] ?? 17

    signal editFinished(string text, real height)

    // True from the start of an edit until it has been committed, so it commits exactly once
    // however it ends: Escape, losing focus, or the canvas clearing `editing` on a click away.
    property bool _open: false

    function finishEditing() {
        if (!_open)
            return
        _open = false
        editFinished(edit.text, Math.max(40, edit.contentHeight + 2 * padding))
    }

    function _startEditing() {
        _open = true
        edit.text = body
        edit.forceActiveFocus()
        edit.cursorPosition = edit.length
    }

    onEditingChanged: {
        if (editing) {
            _startEditing()
        } else {
            finishEditing()
            edit.focus = false // otherwise the hidden editor keeps swallowing key presses
        }
    }
    Component.onCompleted: if (editing) _startEditing()

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: root.noteStyle === "card" ? Theme.surface : "transparent"
        border.width: (root.selected || root.editing ? 2 : (root.noteStyle === "card" ? 1 : 0)) / root.zoom
        border.color: root.selected || root.editing ? Theme.accent : Theme.border
    }

    Text {
        id: view
        objectName: "noteView"
        visible: !root.editing
        x: root.padding
        y: root.padding
        width: root.width - 2 * root.padding
        text: root.body.length > 0 ? root.body : "Double-click to type"
        textFormat: root.body.length > 0 ? Text.MarkdownText : Text.PlainText
        wrapMode: Text.Wrap
        color: root.body.length > 0 ? Theme.text : Theme.textDisabled
        font.family: Theme.fontFamily
        font.pixelSize: root.fontPixels
    }

    TextEdit {
        id: edit
        objectName: "noteEdit"
        visible: root.editing
        x: root.padding
        y: root.padding
        width: root.width - 2 * root.padding
        wrapMode: TextEdit.Wrap
        selectByMouse: true
        color: Theme.text
        selectionColor: Theme.accent
        font.family: Theme.fontFamily
        font.pixelSize: root.fontPixels

        Keys.onEscapePressed: root.finishEditing()
        onActiveFocusChanged: if (!activeFocus) root.finishEditing() // clicking away commits
    }
}
