import pytest

from brainstorm.app_state import AppState
from brainstorm.controllers import CanvasController
from brainstorm.db.spaces import SpaceRepository
from brainstorm.services import ClipboardService, SpaceService


@pytest.fixture
def controller(conn, node_service, edge_service, asset_store, global_space):
    spaces = SpaceService(SpaceRepository(conn))
    clipboard = ClipboardService(node_service, asset_store)
    return CanvasController(
        node_service, edge_service, spaces, AppState(global_space.id), clipboard, asset_store
    )


def test_new_note_is_empty_and_centered(controller, node_service, global_space):
    node = node_service.get(controller.createNoteCentered(100, 50))
    assert (node.body, node.title) == ("", "")
    assert node.x + node.w / 2 == pytest.approx(100)


def test_committing_text_updates_body_title_and_height(controller, node_service, global_space):
    note_id = controller.createNoteCentered(0, 0)
    controller.commitNoteText(note_id, "Plan\n- one\n- two", 90)
    node = node_service.get(note_id)
    assert (node.body, node.title, node.h) == ("Plan\n- one\n- two", "Plan", 90)


def test_note_that_stays_empty_is_removed(controller, node_service, global_space):
    note_id = controller.createNoteCentered(0, 0)
    controller.commitNoteText(note_id, "   ", 40)
    assert node_service.get(note_id) is None


def test_clearing_an_existing_note_keeps_it(controller, node_service, global_space):
    note_id = controller.createNoteCentered(0, 0)
    controller.commitNoteText(note_id, "text", 40)
    controller.commitNoteText(note_id, "", 40)
    assert node_service.get(note_id) is not None


def test_committing_unchanged_text_does_not_write(controller, node_service, global_space):
    note_id = controller.createNoteCentered(0, 0)
    controller.commitNoteText(note_id, "text", 50)
    updated = []
    node_service.nodeUpdated.connect(updated.append)
    controller.commitNoteText(note_id, "text", 50)
    assert updated == []


def test_asset_url_is_empty_for_unknown_asset(controller):
    assert controller.assetUrl("") == ""
    assert controller.assetUrl("missing") == ""


def test_asset_url_for_known_asset(controller, asset_store, png):
    asset = asset_store.import_bytes(png())
    assert controller.assetUrl(asset.hash).startswith("file:///")
