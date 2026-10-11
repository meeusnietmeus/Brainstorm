import pytest

from brainstorm.app_state import AppState


def test_view_change_emits_once():
    state = AppState("space-1")
    changes = []
    state.currentViewChanged.connect(lambda: changes.append(1))
    state.currentView = "projects"
    state.currentView = "projects"
    assert state.currentView == "projects"
    assert len(changes) == 1


def test_unknown_view_is_rejected():
    with pytest.raises(ValueError):
        AppState("space-1").currentView = "nope"
