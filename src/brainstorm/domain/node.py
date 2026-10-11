from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Node:
    """One item on a board. x/y of None means "exists, but not drawn on the canvas"."""

    id: str
    space_id: str
    kind: str
    created_at: str
    updated_at: str
    title: str = ""
    body: str = ""
    status: str | None = None
    x: float | None = None
    y: float | None = None
    w: float | None = None
    h: float | None = None
    z: int = 0
    props: dict[str, Any] = field(default_factory=dict)
