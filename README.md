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
