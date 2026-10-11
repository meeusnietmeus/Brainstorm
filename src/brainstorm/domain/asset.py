from dataclasses import dataclass


@dataclass(slots=True)
class Asset:
    hash: str
    ext: str
    width: int
    height: int
    bytes: int
    created_at: str
    source_url: str | None = None
