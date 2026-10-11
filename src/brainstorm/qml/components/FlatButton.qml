import QtQuick

Rectangle {
    id: root

    property string text
    property bool checked: false

    opacity: enabled ? 1 : 0.4

    signal clicked

    implicitWidth: label.implicitWidth + 2 * Theme.spacingLarge
    implicitHeight: 28
    radius: Theme.radius
    color: checked ? Theme.accent
                   : (mouse.pressed ? Theme.border : (mouse.containsMouse ? Theme.surfaceHover : Theme.surface))
    border.width: 1
    border.color: checked ? Theme.accent : Theme.border

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: root.checked ? Theme.background : Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.enabled
        onClicked: root.clicked()
    }
}
