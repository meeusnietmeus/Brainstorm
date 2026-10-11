import hashlib

import pytest

from brainstorm.services import NotAnImageError


def test_import_stores_file_and_row(asset_store, png, tmp_path):
    data = png(40, 20)
    asset = asset_store.import_bytes(data, source_url="https://example.com/a.png")
    digest = hashlib.sha256(data).hexdigest()
    assert asset.hash == digest
    assert (asset.ext, asset.width, asset.height, asset.bytes) == ("png", 40, 20, len(data))
    assert asset.source_url == "https://example.com/a.png"
    expected = tmp_path / "assets" / digest[:2] / f"{digest}.png"
    assert asset_store.path(digest) == expected
    assert expected.read_bytes() == data


def test_same_bytes_twice_stores_one_file_and_one_row(asset_store, conn, png, tmp_path):
    data = png()
    first = asset_store.import_bytes(data)
    second = asset_store.import_bytes(data)
    assert first.hash == second.hash
    files = [p for p in (tmp_path / "assets").rglob("*") if p.is_file()]
    assert len(files) == 1
    assert conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1


def test_different_bytes_get_different_assets(asset_store, png):
    red = asset_store.import_bytes(png(color="#ff0000"))
    green = asset_store.import_bytes(png(color="#00ff00"))
    assert red.hash != green.hash


def test_source_url_is_filled_in_when_a_later_import_knows_it(asset_store, png):
    data = png()
    asset_store.import_bytes(data)
    asset = asset_store.import_bytes(data, source_url="https://example.com/x.png")
    assert asset.source_url == "https://example.com/x.png"
    assert asset_store.get(asset.hash).source_url == "https://example.com/x.png"


def test_unreadable_bytes_are_rejected_and_nothing_is_stored(asset_store, conn, tmp_path):
    with pytest.raises(NotAnImageError):
        asset_store.import_bytes(b"definitely not an image")
    assert conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0
    assert not list((tmp_path / "assets").rglob("*.*"))


def test_import_file_uses_the_file_extension_and_keeps_full_size(asset_store, png, tmp_path):
    source = tmp_path / "photo.PNG"
    source.write_bytes(png(1200, 800))
    asset = asset_store.import_file(source)
    assert (asset.ext, asset.width, asset.height) == ("png", 1200, 800)


def test_url_is_a_proper_file_url(asset_store, png):
    asset = asset_store.import_bytes(png())
    url = asset_store.url(asset.hash)
    assert url.isLocalFile()
    assert url.toLocalFile().replace("\\", "/").endswith(f"{asset.hash}.png")


def test_path_of_unknown_asset_raises(asset_store):
    with pytest.raises(KeyError):
        asset_store.path("nope")
