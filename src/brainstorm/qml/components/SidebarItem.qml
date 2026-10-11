import QtQuick

// One row in the sidebar. Disabled rows are placeholders for later phases.
Rectangle {
    id: root

    property string label
    property bool selected: false
    property bool placeholder: false

    signal clicked

    implicitHeight: 32
    radius: Theme.radius
    color: selected ? Theme.surfaceHover : (mouse.containsMouse && !placeholder ? Theme.surface : "transparent")

    Rectangle {
        visible: root.selected
        width: 3
        height: parent.height - 12
        radius: 1.5
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.accent
    }

    Text {
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: Theme.spacingLarge
        text: root.label
        color: root.placeholder ? Theme.textDisabled : Theme.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSize
    }

    Text {
        visible: root.placeholder
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.rightMargin: Theme.spacing
        text: "soon"
        color: Theme.textDisabled
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fontSizeSmall
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: !root.placeholder
        onClicked: root.clicked()
    }
}
