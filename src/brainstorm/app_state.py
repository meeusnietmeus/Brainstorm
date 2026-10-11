from PySide6.QtCore import Property, QObject, Signal

VIEWS = ("board", "projects")


class AppState(QObject):
    """UI-level state shared with QML: which space is open and which view is showing."""

    currentSpaceIdChanged = Signal()
    currentViewChanged = Signal()

    def __init__(self, space_id: str, view: str = "board", parent: QObject | None = None):
        super().__init__(parent)
        self._space_id = space_id
        self._view = view

    def _get_space_id(self) -> str:
        return self._space_id

    def _set_space_id(self, value: str) -> None:
        if value != self._space_id:
            self._space_id = value
            self.currentSpaceIdChanged.emit()

    def _get_view(self) -> str:
        return self._view

    def _set_view(self, value: str) -> None:
        if value not in VIEWS:
            raise ValueError(f"Unknown view: {value}")
        if value != self._view:
            self._view = value
            self.currentViewChanged.emit()

    currentSpaceId = Property(str, _get_space_id, _set_space_id, notify=currentSpaceIdChanged)
    currentView = Property(str, _get_view, _set_view, notify=currentViewChanged)
