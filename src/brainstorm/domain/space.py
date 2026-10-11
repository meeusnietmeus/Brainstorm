from dataclasses import dataclass
from typing import Any

GLOBAL = "global"
PROJECT = "project"


@dataclass(slots=True)
class Space:
    id: str
    kind: str
    name: str
    created_at: str
    updated_at: str
    archived_at: str | None = None
    view_state: dict[str, Any] | None = None  # saved canvas pan and zoom
