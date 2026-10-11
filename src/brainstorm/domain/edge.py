from dataclasses import dataclass, field
from typing import Any

ARROWS = ("end", "both", "none")
DEFAULT_STYLE: dict[str, Any] = {"dashed": False, "arrow": "end"}


@dataclass(slots=True)
class Edge:
    id: str
    space_id: str
    source_id: str
    target_id: str
    created_at: str
    label: str = ""
    style: dict[str, Any] = field(default_factory=dict)

    @property
    def dashed(self) -> bool:
        return bool(self.style.get("dashed", DEFAULT_STYLE["dashed"]))

    @property
    def arrow(self) -> str:
        return self.style.get("arrow", DEFAULT_STYLE["arrow"])

    @property
    def color(self) -> str:
        return self.style.get("color", "")
