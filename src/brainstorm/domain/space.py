from dataclasses import dataclass

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
