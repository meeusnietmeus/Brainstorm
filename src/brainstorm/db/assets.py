import sqlite3

from brainstorm.domain import Asset


class AssetRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def get(self, asset_hash: str) -> Asset | None:
        row = self._conn.execute("SELECT * FROM assets WHERE hash = ?", (asset_hash,)).fetchone()
        return Asset(**dict(row)) if row else None

    def add(self, asset: Asset) -> None:
        self._conn.execute(
            "INSERT INTO assets (hash, ext, width, height, bytes, source_url, created_at)"
            " VALUES (:hash, :ext, :width, :height, :bytes, :source_url, :created_at)",
            {s: getattr(asset, s) for s in asset.__slots__},
        )
        self._conn.commit()

    def set_source_url(self, asset_hash: str, source_url: str) -> None:
        self._conn.execute(
            "UPDATE assets SET source_url = ? WHERE hash = ?", (source_url, asset_hash)
        )
        self._conn.commit()
