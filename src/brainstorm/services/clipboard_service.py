"""Turns clipboard and drop content into nodes. One code path serves both."""

import base64
import re
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QMimeData, QUrl
from PySide6.QtGui import QGuiApplication, QImage

from brainstorm.domain import Node
from brainstorm.services.asset_store import AssetStore, NotAnImageError
from brainstorm.services.node_service import NodeService
from brainstorm.services.remote_fetcher import RemoteImageFetcher

MAX_IMAGE_SIDE = 600.0  # initial display size, in world units; the file keeps full size
PLACEHOLDER_SIZE = (240.0, 160.0)
LINK_SIZE = (280.0, 64.0)
NOTE_WIDTH = 300.0
STAGGER = 24.0  # offset between nodes created by one paste or drop

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".jpe", ".gif", ".webp", ".bmp"}
_IMG_SRC = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
_DATA_URL = re.compile(r"^data:image/[\w.+-]+;base64,(.*)$", re.IGNORECASE | re.DOTALL)

BytesReader = Callable[[], bytes]


def fit_size(width: float, height: float, longest: float = MAX_IMAGE_SIDE) -> tuple[float, float]:
    """Scale down (never up) so the longest side is at most `longest`, keeping the aspect."""
    factor = min(1.0, longest / max(width, height, 1))
    return width * factor, height * factor


def _is_http_url(text: str) -> bool:
    return bool(re.fullmatch(r"https?://\S+", text))


def _looks_like_image_url(url: str) -> bool:
    return Path(QUrl(url).path()).suffix.lower() in _IMAGE_EXTS


def _image_to_png(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


class ClipboardService:
    def __init__(
        self, nodes: NodeService, assets: AssetStore, fetcher: RemoteImageFetcher | None = None
    ):
        self._nodes = nodes
        self._assets = assets
        self._fetcher = fetcher or RemoteImageFetcher()

    def paste(self, space_id: str, x: float, y: float) -> list[Node]:
        mime = QGuiApplication.clipboard().mimeData()
        return self.import_mime(mime, space_id, x, y) if mime else []

    def import_mime(self, mime: QMimeData, space_id: str, x: float, y: float) -> list[Node]:
        """Create nodes centered on (x, y). Image data wins, then URLs, then HTML, then text."""
        html_sources = (
            [m.group(2) for m in _IMG_SRC.finditer(mime.html())] if mime.hasHtml() else []
        )

        if mime.hasImage():
            image = mime.imageData()
            if isinstance(image, QImage) and not image.isNull():
                source = next((s for s in html_sources if _is_http_url(s)), None)
                return self._image_nodes(space_id, x, y, [(lambda: _image_to_png(image), source)])

        if mime.hasUrls():
            nodes = self._from_urls(mime, space_id, x, y, html_sources)
            if nodes:
                return nodes

        if html_sources:
            return self._from_image_sources(space_id, x, y, html_sources)

        text = mime.text().strip() if mime.hasText() else ""
        if _is_http_url(text):
            return [self._link(space_id, x, y, text)]
        if text:
            return [
                self._nodes.create(
                    space_id, "note", body=text, x=x - NOTE_WIDTH / 2, y=y, w=NOTE_WIDTH
                )
            ]
        return []

    # Sources

    def _from_urls(
        self, mime: QMimeData, space_id: str, x: float, y: float, html_sources: list[str]
    ) -> list[Node]:
        nodes: list[Node] = []
        remote_images: list[str] = []
        for url in mime.urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.suffix.lower() in _IMAGE_EXTS and path.is_file():
                    nodes += self._image_nodes(
                        space_id, x, y, [(path.read_bytes, None)], offset=len(nodes)
                    )
                continue
            text = url.toString()
            # A dragged image arrives as its URL, with the <img> tag in the HTML alongside.
            if _looks_like_image_url(text) or text in html_sources:
                remote_images.append(text)
            elif _is_http_url(text):
                nodes.append(self._link(space_id, x, y, text, offset=len(nodes)))
        if remote_images:
            nodes += self._from_image_sources(space_id, x, y, remote_images, offset=len(nodes))
        return nodes

    def _from_image_sources(
        self, space_id: str, x: float, y: float, sources: list[str], offset: int = 0
    ) -> list[Node]:
        nodes: list[Node] = []
        for source in sources:
            data_url = _DATA_URL.match(source)
            if data_url:
                payload = base64.b64decode(data_url.group(1))
                nodes += self._image_nodes(
                    space_id, x, y, [(lambda p=payload: p, None)], offset=offset + len(nodes)
                )
            elif _is_http_url(source):
                nodes.append(self._pending_image(space_id, x, y, source, offset + len(nodes)))
        return nodes

    # Node builders

    @staticmethod
    def _place(x: float, y: float, w: float, h: float, offset: int) -> tuple[float, float]:
        return x - w / 2 + offset * STAGGER, y - h / 2 + offset * STAGGER

    def _image_nodes(
        self,
        space_id: str,
        x: float,
        y: float,
        readers: list[tuple[BytesReader, str | None]],
        offset: int = 0,
    ) -> list[Node]:
        nodes: list[Node] = []
        for read, source in readers:
            try:
                asset = self._assets.import_bytes(read(), source_url=source)
            except NotAnImageError:
                continue
            w, h = fit_size(asset.width, asset.height)
            nx, ny = self._place(x, y, w, h, offset + len(nodes))
            nodes.append(
                self._nodes.create(
                    space_id, "image", x=nx, y=ny, w=w, h=h, props={"asset": asset.hash}
                )
            )
        return nodes

    def _link(self, space_id: str, x: float, y: float, url: str, offset: int = 0) -> Node:
        w, h = LINK_SIZE
        nx, ny = self._place(x, y, w, h, offset)
        return self._nodes.create(
            space_id, "link", title=url, x=nx, y=ny, w=w, h=h, props={"url": url}
        )

    def _pending_image(self, space_id: str, x: float, y: float, url: str, offset: int) -> Node:
        """A placeholder node now; the download fills it in later on the main thread."""
        w, h = PLACEHOLDER_SIZE
        nx, ny = self._place(x, y, w, h, offset)
        node = self._nodes.create(
            space_id,
            "image",
            x=nx,
            y=ny,
            w=w,
            h=h,
            props={"asset": None, "pending": True, "source_url": url},
        )
        self._fetcher.fetch(
            url, lambda data, error: self._finish_download(node.id, url, data, error)
        )
        return node

    def _finish_download(
        self, node_id: str, url: str, data: bytes | None, error: str | None
    ) -> None:
        node = self._nodes.get(node_id)
        if node is None:  # deleted while downloading
            return
        try:
            if data is None:
                raise NotAnImageError(error or "Download failed")
            asset = self._assets.import_bytes(data, source_url=url)
        except NotAnImageError as exc:
            self._nodes.set_props(node_id, pending=False, error=str(exc))
            return
        w, h = fit_size(asset.width, asset.height)
        cx = node.x + (node.w or 0) / 2
        cy = node.y + (node.h or 0) / 2
        self._nodes.resize(
            node_id, cx - w / 2, cy - h / 2, w, h, props={"asset": asset.hash, "pending": False}
        )
