pragma Singleton
import QtQuick

// Colors, spacing and fonts. Dark by default; a light variant arrives in Phase 12.
QtObject {
    readonly property color background: "#1b1d22"
    readonly property color surface: "#23262d"
    readonly property color surfaceHover: "#2c303a"
    readonly property color border: "#343944"
    readonly property color accent: "#6ea8fe"
    readonly property color text: "#e6e8ec"
    readonly property color textMuted: "#8b92a1"
    readonly property color textDisabled: "#5a606d"

    readonly property int spacing: 8
    readonly property int spacingLarge: 16
    readonly property int radius: 6
    readonly property int sidebarWidth: 220

    readonly property int fontSizeSmall: 11
    readonly property int fontSize: 13
    readonly property int fontSizeTitle: 18
    readonly property string fontFamily: "Segoe UI"
}
