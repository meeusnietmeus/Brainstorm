import QtQuick

Rectangle {
    id: root

    property string text

    signal clicked

    implicitWidth: label.implicitWidth + 2 * Theme.spacingLarge
    implicitHeight: 28
    radius: Theme.radius
    color: mouse.pressed ? Theme.border : (mouse.containsMouse ? Theme.surfaceHover : Theme.surface)
    border.width: 1
    border.color: Theme.border

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        onClicked: root.clicked()
    }
}
