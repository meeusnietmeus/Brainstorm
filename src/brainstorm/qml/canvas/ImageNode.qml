import QtQuick
import "../components"

Item {
    id: root

    property url source
    property bool pending: false
    property string error
    property bool selected: false
    property real zoom: 1

    // Decode at roughly the on-screen size, rounded up to a power of two so the image is not
    // reloaded on every zoom step. The original file on disk is never touched.
    readonly property int decodeWidth: Math.min(
        8192, Math.max(32, Math.pow(2, Math.ceil(Math.log2(Math.max(1, width * zoom))))))

    Image {
        anchors.fill: parent
        visible: root.source.toString() !== ""
        source: root.source
        asynchronous: true
        fillMode: Image.PreserveAspectFit
        smooth: true
        sourceSize.width: root.decodeWidth
    }

    // Placeholder while a dragged-in image downloads, or if that failed.
    Rectangle {
        anchors.fill: parent
        visible: root.source.toString() === ""
        radius: 8
        color: Theme.surface
        border.width: 1 / root.zoom
        border.color: Theme.border

        Text {
            anchors.centerIn: parent
            width: parent.width - 2 * Theme.spacingLarge
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            color: root.error !== "" ? "#e57373" : Theme.textMuted
            font.family: Theme.fontFamily
            font.pixelSize: Theme.fontSize
            text: root.error !== "" ? "Could not load image\n" + root.error
                                    : (root.pending ? "Loading image…" : "No image")
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        visible: root.selected
        border.width: 2 / root.zoom
        border.color: Theme.accent
    }
}
