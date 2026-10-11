import hashlib
import os
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QUrl
from PySide6.QtGui import QImageReader

from brainstorm.db.assets import AssetRepository
from brainstorm.domain import Asset, utc_now

_EXT_ALIASES = {"jpeg": "jpg", "jpe": "jpg"}


class NotAnImageError(ValueError):
    pass


def _probe(data: bytes) -> tuple[str, int, int]:
    """Format, width and height of image bytes. QImageReader reads only the header."""
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    size = reader.size()
    fmt = bytes(reader.format()).decode().lower()
    if not fmt or not size.isValid():
        raise NotAnImageError("Not a readable image")
    return _EXT_ALIASES.get(fmt, fmt), size.width(), size.height()


class AssetStore:
    """Content-addressed image files: identical bytes are stored once, at full size."""

    def __init__(self, repo: AssetRepository, root: Path):
        self._repo = repo
        self._root = root

    def import_bytes(
        self, data: bytes, ext: str | None = None, source_url: str | None = None
    ) -> Asset:
        digest = hashlib.sha256(data).hexdigest()
        existing = self._repo.get(digest)
        if existing:
            if source_url and not existing.source_url:
                self._repo.set_source_url(digest, source_url)
                existing.source_url = source_url
            return existing

        detected, width, height = _probe(data)
        ext = (
            _EXT_ALIASES.get(ext.lower().lstrip("."), ext.lower().lstrip(".")) if ext else detected
        )
        asset = Asset(digest, ext, width, height, len(data), utc_now(), source_url)
        path = self._file(asset)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_bytes(data)
            os.replace(temp, path)  # never leave a half-written asset behind
        self._repo.add(asset)
        return asset

    def import_file(self, path: str | Path, source_url: str | None = None) -> Asset:
        path = Path(path)
        return self.import_bytes(path.read_bytes(), path.suffix, source_url)

    def get(self, asset_hash: str) -> Asset | None:
        return self._repo.get(asset_hash)

    def path(self, asset_hash: str) -> Path:
        asset = self._repo.get(asset_hash)
        if asset is None:
            raise KeyError(f"No such asset: {asset_hash}")
        return self._file(asset)

    def url(self, asset_hash: str) -> QUrl:
        """file: URL for QML. fromLocalFile handles Windows drive letters correctly."""
        return QUrl.fromLocalFile(str(self.path(asset_hash)))

    def _file(self, asset: Asset) -> Path:
        return self._root / asset.hash[:2] / f"{asset.hash}.{asset.ext}"
