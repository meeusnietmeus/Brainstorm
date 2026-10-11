import QtQuick
import "../components"

// Generic node card. Kind-specific components (note, image, ...) replace this in later phases.
Rectangle {
    id: root

    property string title
    property bool selected: false
    property real zoom: 1

    radius: 8
    color: Theme.surface
    // Borders are divided by zoom so the selection outline keeps a constant on-screen width.
    border.width: (selected ? 2 : 1) / zoom
    border.color: selected ? Theme.accent : Theme.border

    Text {
        anchors.fill: parent
        anchors.margins: Theme.spacingLarge
        text: root.title
        color: Theme.text
        wrapMode: Text.Wrap
        elide: Text.ElideRight
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize + 2
    }
}
