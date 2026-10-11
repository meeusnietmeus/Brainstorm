import base64

import pytest
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QImage

from brainstorm.services import ClipboardService
from brainstorm.services.clipboard_service import MAX_IMAGE_SIDE, STAGGER


class FakeFetcher:
    """Collects requests so a test decides when and how each download finishes."""

    def __init__(self):
        self.requests = []

    def fetch(self, url, callback):
        self.requests.append((url, callback))


@pytest.fixture
def fetcher():
    return FakeFetcher()


@pytest.fixture
def clipboard(node_service, asset_store, fetcher):
    return ClipboardService(node_service, asset_store, fetcher)


def center(node):
    return node.x + node.w / 2, node.y + node.h / 2


def mime_with_image(png_bytes):
    mime = QMimeData()
    mime.setImageData(QImage.fromData(png_bytes))
    return mime


def test_image_becomes_image_node_with_right_aspect_centered_on_cursor(
    clipboard, global_space, asset_store, png
):
    [node] = clipboard.import_mime(mime_with_image(png(400, 200)), global_space.id, 100, 50)
    assert node.kind == "image"
    assert node.w / node.h == pytest.approx(2.0)
    assert center(node) == pytest.approx((100, 50))
    asset = asset_store.get(node.props["asset"])
    assert (asset.width, asset.height) == (400, 200)


def test_large_image_is_displayed_smaller_but_stored_full_size(
    clipboard, global_space, asset_store, png
):
    [node] = clipboard.import_mime(mime_with_image(png(3000, 1500)), global_space.id, 0, 0)
    assert max(node.w, node.h) == pytest.approx(MAX_IMAGE_SIDE)
    assert asset_store.get(node.props["asset"]).width == 3000


def test_pasting_the_same_image_twice_stores_one_asset(clipboard, global_space, conn, png):
    mime = mime_with_image(png(30, 30))
    first = clipboard.import_mime(mime, global_space.id, 0, 0)
    second = clipboard.import_mime(mime, global_space.id, 0, 0)
    assert first[0].props["asset"] == second[0].props["asset"]
    assert conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1


def test_image_with_html_source_records_where_it_came_from(
    clipboard, global_space, asset_store, png
):
    mime = mime_with_image(png())
    mime.setHtml('<img src="https://example.com/art.png" alt="">')
    [node] = clipboard.import_mime(mime, global_space.id, 0, 0)
    assert asset_store.get(node.props["asset"]).source_url == "https://example.com/art.png"


def test_page_url_becomes_link_node(clipboard, global_space):
    mime = QMimeData()
    mime.setText("https://example.com/some/page")
    [node] = clipboard.import_mime(mime, global_space.id, 10, 10)
    assert node.kind == "link"
    assert node.title == "https://example.com/some/page"
    assert node.props["url"] == "https://example.com/some/page"


def test_plain_text_becomes_note(clipboard, global_space):
    mime = QMimeData()
    mime.setText("  an idea\nwith two lines ")
    [node] = clipboard.import_mime(mime, global_space.id, 0, 0)
    assert node.kind == "note"
    assert node.body == "an idea\nwith two lines"
    assert node.title == "an idea"


def test_text_with_spaces_is_not_mistaken_for_a_url(clipboard, global_space):
    mime = QMimeData()
    mime.setText("see https://example.com for details")
    [node] = clipboard.import_mime(mime, global_space.id, 0, 0)
    assert node.kind == "note"


def test_empty_clipboard_creates_nothing(clipboard, global_space):
    assert clipboard.import_mime(QMimeData(), global_space.id, 0, 0) == []


def test_dropped_local_image_files_are_imported_and_staggered(
    clipboard, global_space, png, tmp_path
):
    files = []
    for i, color in enumerate(["#ff0000", "#00ff00"]):
        path = tmp_path / f"art{i}.png"
        path.write_bytes(png(50, 50, color))
        files.append(QUrl.fromLocalFile(str(path)))
    (tmp_path / "notes.txt").write_text("not an image")
    files.append(QUrl.fromLocalFile(str(tmp_path / "notes.txt")))
    mime = QMimeData()
    mime.setUrls(files)
    first, second = clipboard.import_mime(mime, global_space.id, 0, 0)
    assert (second.x - first.x, second.y - first.y) == pytest.approx((STAGGER, STAGGER))


def test_remote_image_drop_creates_placeholder_then_fills_it_in(
    clipboard, node_service, global_space, asset_store, fetcher, png
):
    mime = QMimeData()
    mime.setUrls([QUrl("https://img.example.com/pic.jpg")])
    mime.setHtml('<img src="https://img.example.com/pic.jpg">')
    [placeholder] = clipboard.import_mime(mime, global_space.id, 200, 100)
    assert placeholder.kind == "image"
    assert placeholder.props["pending"] is True and placeholder.props["asset"] is None
    assert center(placeholder) == pytest.approx((200, 100))
    [(url, callback)] = fetcher.requests
    assert url == "https://img.example.com/pic.jpg"

    callback(png(300, 150), None)

    node = node_service.get(placeholder.id)
    assert node.props["pending"] is False
    assert node.w / node.h == pytest.approx(2.0)
    assert center(node) == pytest.approx((200, 100))
    asset = asset_store.get(node.props["asset"])
    assert asset.source_url == "https://img.example.com/pic.jpg"


def test_failed_download_marks_the_placeholder(clipboard, node_service, global_space, fetcher):
    mime = QMimeData()
    mime.setUrls([QUrl("https://img.example.com/missing.png")])
    [placeholder] = clipboard.import_mime(mime, global_space.id, 0, 0)
    fetcher.requests[0][1](None, "HTTP Error 404")
    node = node_service.get(placeholder.id)
    assert node.props["pending"] is False
    assert node.props["error"] == "HTTP Error 404"


def test_download_that_is_not_an_image_is_an_error(clipboard, node_service, global_space, fetcher):
    mime = QMimeData()
    mime.setUrls([QUrl("https://example.com/pic.png")])
    [placeholder] = clipboard.import_mime(mime, global_space.id, 0, 0)
    fetcher.requests[0][1](b"<html>nope</html>", None)
    assert "error" in node_service.get(placeholder.id).props


def test_download_finishing_after_the_node_was_deleted_is_ignored(
    clipboard, node_service, global_space, fetcher, png, conn
):
    mime = QMimeData()
    mime.setUrls([QUrl("https://example.com/pic.png")])
    [placeholder] = clipboard.import_mime(mime, global_space.id, 0, 0)
    node_service.delete(placeholder.id)
    fetcher.requests[0][1](png(), None)
    assert conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0


def test_page_link_drag_creates_link_not_image(clipboard, global_space, fetcher):
    mime = QMimeData()
    mime.setUrls([QUrl("https://example.com/article")])
    [node] = clipboard.import_mime(mime, global_space.id, 0, 0)
    assert node.kind == "link"
    assert fetcher.requests == []


def test_data_url_image_in_html_is_decoded_locally(clipboard, global_space, fetcher, png):
    payload = base64.b64encode(png(20, 20)).decode()
    mime = QMimeData()
    mime.setHtml(f'<img src="data:image/png;base64,{payload}">')
    [node] = clipboard.import_mime(mime, global_space.id, 0, 0)
    assert node.kind == "image" and node.props["asset"]
    assert fetcher.requests == []
