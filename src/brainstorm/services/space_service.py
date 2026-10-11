from typing import Any

from brainstorm.db.spaces import SpaceRepository
from brainstorm.domain import Space


class SpaceService:
    """Write path for space-level data. Project commands arrive in Phase 7."""

    def __init__(self, repo: SpaceRepository):
        self._repo = repo

    def get(self, space_id: str) -> Space | None:
        return self._repo.get(space_id)

    def view_state(self, space_id: str) -> dict[str, Any] | None:
        space = self._repo.get(space_id)
        return space.view_state if space else None

    def set_view_state(self, space_id: str, x: float, y: float, scale: float) -> None:
        """Persist the canvas pan and zoom. Callers debounce; this writes every time."""
        self._repo.set_view_state(space_id, {"x": x, "y": y, "scale": scale})
