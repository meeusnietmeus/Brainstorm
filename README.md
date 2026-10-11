# Brainstorm

A local-only, single-user game brainstorm tool: an infinite idea canvas, projects, and todo views.
The full roadmap is in [docs/build-plan.md](docs/build-plan.md).

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

```powershell
python -m brainstorm
```

To launch it from the Start menu, run `scripts\install_start_menu_shortcut.ps1` once (add `-Remove`
to delete the shortcut). It points at this checkout's venv, so re-run it if you move the folder.

Data lives in the OS app-data folder (`brainstorm.db` plus `assets/`). Set `BRAINSTORM_DATA_DIR`
to use a different folder, which is handy for experiments.

## Develop

```powershell
pytest
ruff check .
```

## Phases

### Phase 1: Scaffold, app shell, SQLite layer

- Window with a sidebar (Board, Projects, placeholders) and an empty content area; dark `Theme`
  singleton; window geometry restored through `QSettings`.
- SQLite database that migrates itself on launch (`db/migrations/NNN_name.sql`, tracked with
  `PRAGMA user_version`, each migration atomic). The single global space is created on first run.
- `domain/` dataclasses (`Space`, `Node`), repositories in `db/`, and `NodeService`
  (`create`, `update`, `move`, `delete`), the only write path, which emits Qt signals.
- `AppState` exposed to QML as a singleton in the `Brainstorm` module.
- Rule from here on: writes during a drag or resize happen once, on release.

### Phase 2: Infinite canvas and node rendering

- Pan/zoom canvas (`qml/canvas/Canvas.qml`): wheel zooms around the cursor (5% to 800%), pan with
  middle-mouse drag or Space + left-drag, pinch on touchpads. Zoom math lives in
  `canvas_math.zoom_at` (tested); QML calls it through `CanvasController`.
- Nodes are drawn from `NodeModel`, which updates rows from `NodeService` signals and never
  reloads after an edit. Dragging a node writes once, on release.
- Click selects, click on empty canvas clears, Delete removes. "Add note" in the toolbar adds a
  note at the viewport center; double-click on empty canvas adds one at the cursor.
- Migration 002 stores each space's pan and zoom (`spaces.view_state`), saved 500 ms after the
  last change and restored when the space opens.
- Dot grid is one tiled image positioned modulo the tile size, so panning costs nothing.
