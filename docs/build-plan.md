# Game Brainstorm Tool: Build Plan

Oct 11, 2026 · @Seppe

## Overview and conventions

Build the tool in 12 phases, in order. Each phase ends with a runnable app, so you can stop and verify after every one.

**Decisions already made**

- One global canvas holds the idea board (inspiration collage, loose notes, open questions).
- Projects are separate spaces. Lasso or frame nodes on the global board, choose Start project, and they move into a new project that has its own brainstorm canvas.
- Local-only, single user. No sync, no collaboration, no Git integration.

**Stack**

- Python 3.12+, PySide6, Qt Quick (QML), `QtQuick.Shapes` for arrows
- SQLite through the stdlib `sqlite3`, no ORM
- `QThreadPool` for background work (code scanning, link metadata)
- `pytest` for the Python layer, `ruff` for linting

**Architecture rules**

1. Python owns all state and logic. QML renders and forwards input.
2. Every mutation is a command in a service layer (create node, move node, delete edge, and so on). QML never writes to SQLite directly. This is what makes undo (Phase 5) and autosave possible.
3. The canvas uses float world coordinates. Conversion to screen coordinates happens only in QML.
4. IDs are UUID strings. Timestamps are ISO-8601 UTC.
5. Schema changes are numbered migrations tracked with `PRAGMA user_version`.
6. Data lives in the OS app-data folder (`QStandardPaths.AppDataLocation`): `brainstorm.db` plus an `assets/` folder.

**Proposed layout**

```
brainstorm/
  pyproject.toml
  README.md
  src/brainstorm/
    main.py            # QGuiApplication + QML engine setup
    db/                # connection, migrations/, repositories
    domain/            # dataclasses: Node, Edge, Space, Resource
    services/          # commands: NodeService, EdgeService, ScanService, ...
    models/            # QAbstractListModel subclasses exposed to QML
    qml/
      Main.qml
      canvas/          # Canvas.qml, nodes/, edges/
      views/           # ListView.qml, KanbanView.qml, ...
      components/      # buttons, inputs, theme
  tests/
```

**Core data model** (details are added phase by phase)

| Table | Holds | Introduced |
| --- | --- | --- |
| `spaces` | The one global space and every project space | Phase 1 |
| `nodes` | Every item: note, image, link, question, feature, bug, doc, code-todo, frame | Phase 1 |
| `edges` | Arrows between two nodes, with an optional label | Phase 4 |
| `resources` | Saved articles and videos | Phase 9 |
| `pillars`, `devlog` | Design pillars and dated log entries | Phase 10 |

A node with no canvas position exists but is not drawn on the canvas. Code TODOs use this until you drop them onto a board.

**Definition of done for every phase**

- The app launches and the phase's manual checklist passes.
- `pytest` and `ruff` pass.
- The README gets a short section on what the phase added.
- One commit per phase, with the phase name in the message.

## Phase 1: Scaffold, app shell, SQLite layer

**Goal:** an empty but real app: a window, a database that migrates itself, and a service layer other phases plug into.

**Build**

- `pyproject.toml` with PySide6, pytest, ruff. App starts with `python -m brainstorm`.
- `main.py` creates the `QGuiApplication` and `QQmlApplicationEngine`, loads `Main.qml`, and registers Python types with `@QmlElement` under the import name `Brainstorm`.
- `db/connection.py` opens the database in the app-data folder with `PRAGMA foreign_keys=ON`, `journal_mode=WAL`, and `sqlite3.Row` as the row factory.
- `db/migrations/001_init.sql`, applied by a small runner that compares `PRAGMA user_version` to the highest migration number.
  - `spaces(id, kind, name, created_at, updated_at, archived_at)` with `kind` limited to `global` or `project`
  - `nodes(id, space_id, kind, title, body, status, x, y, w, h, z, props, created_at, updated_at)`, where `props` is a JSON text column for kind-specific fields and `x`/`y` may be null (not on canvas)
  - Indexes on `(space_id, kind)` and `(space_id, status)`
- On first launch, create the single `global` space.
- `domain/` dataclasses for `Space` and `Node`. `db/` repositories for each, with plain CRUD methods.
- `services/NodeService`: `create`, `update`, `move`, `delete`. Each method writes through the repository and emits a Qt signal. This is the only write path.
- `AppState` QObject exposed to QML with `currentSpaceId` and `currentView`.
- `Main.qml`: a window with a left sidebar (Board, Projects, placeholders for later phases) and a content area. Add a `Theme.qml` singleton (colors, spacing, fonts) with a dark default.
- `QSettings` stores window size and position.

**Rule to keep from here on:** writes during a drag or resize happen once, on release. Never write per mouse-move event.

**Tests:** the migration runner on a fresh in-memory database, and `NodeService` CRUD against an in-memory fixture.

**Done when**

- [ ] The app opens a window with the sidebar and an empty content area
- [ ] Deleting the database file and relaunching recreates it with the global space
- [ ] Window geometry is restored on relaunch

## Phase 2: Infinite canvas and node rendering

**Goal:** a pan/zoom canvas where draggable nodes are drawn from the database and positions survive a restart.

**Build**

- `models/NodeModel` (`QAbstractListModel`) scoped to one space. Roles: `nodeId`, `kind`, `title`, `body`, `status`, `x`, `y`, `w`, `h`, `z`, `props`. It listens to `NodeService` signals and emits `dataChanged`, `rowsInserted`, `rowsRemoved`. It never reloads the whole list after an edit.
- `canvas/Canvas.qml`: a clipped viewport `Item` containing one `world` `Item`.
  - Pan and zoom are `world.x`, `world.y` and `world.scale`, with `transformOrigin: Item.TopLeft`.
  - Wheel zooms around the cursor: before changing scale, convert the cursor to world coordinates, apply the new scale, then set `world.x`/`world.y` so that world point stays under the cursor. Clamp zoom to 0.05 to 8.
  - Pan with middle-mouse drag or space + left-drag (`DragHandler` on the world, `acceptedButtons` set accordingly). Add a `PinchHandler` for touchpads.
  - Expose `screenToWorld(point)` and `worldToScreen(point)` as functions. Every later feature (lasso, paste position, arrows) uses these.
- A `Repeater` over `NodeModel` with a `Loader` per delegate that picks a component by `kind`. For now every kind uses one generic `NodeBase.qml`: a rounded rectangle with the title. Kind-specific components come in later phases.
- Dragging a node: `DragHandler` on the delegate moves it visually. On release, call `nodeService.move(id, x, y)` and restore the `x: model.x` binding. Use a `Binding { when: !drag.active }` so the binding is not permanently broken.
- Click selects a node (single selection for now) and draws a selection outline. Click on empty canvas clears it.
- Creating nodes: a toolbar button adds a note at the viewport center, and double-click on empty canvas adds one at the cursor.
- Delete key removes the selected node through `NodeService.delete`.
- Migration `002`: add `spaces.view_state` (JSON with pan and zoom). Save it debounced (500 ms) on viewport change and restore it when the space opens.
- Optional: a dot grid that scales with zoom. Draw it cheaply (a tiled image or a `Canvas` redrawn at the end of a pan/zoom), not per frame.

**Tests:** the zoom-around-cursor math as a pure function (`zoom_at(offset, scale, cursor, factor)`), and `NodeModel` row updates when `NodeService` signals fire.

**Done when**

- [ ] Create 30 notes, drag them around, zoom from 5% to 800%
- [ ] The point under the cursor stays fixed while zooming
- [ ] After a restart, node positions and the viewport are restored
- [ ] Dragging stays smooth with 200 nodes

## Phase 3: Text, images, paste and drop

**Goal:** the Excalidraw-style collage workflow: paste a screenshot or drop an artwork onto the board and annotate it with free text.

**Build**

- **Text nodes** (`NoteNode.qml`)
  - Double-click enters edit mode with a `TextEdit` (`wrapMode: TextEdit.Wrap`). Escape or clicking away commits through `nodeService.update`.
  - When not editing, render the body with `textFormat: TextEdit.MarkdownText` so bullet lists and bold look right. While editing, show the raw text.
  - The `title` column is derived from the first line of the body, trimmed. List views in Phase 6 use it.
  - `props.style` is `plain` (no box, like loose Excalidraw text) or `card` (filled box). `props.fontSize` is S, M or L. A small floating inspector toggles both.
- **Resize handles** (`ResizeHandles.qml`)
  - Four corner handles on a selected node, scaled by `1 / world.scale` so they stay the same size on screen at any zoom.
  - Text nodes: width is set by the user, height follows `contentHeight` unless the user resizes vertically. Image nodes keep their aspect ratio (hold Shift to break it).
- **Asset store** (`services/AssetStore`)
  - `import_bytes(data, ext)` hashes with SHA-256 and writes `assets/<first 2 hex chars>/<hash>.<ext>`. Identical content is stored once.
  - Migration `003`: `assets(hash PRIMARY KEY, ext, width, height, bytes, source_url, created_at)`. Read the size with `QImageReader`, which does not decode the whole image.
  - Expose `path(hash)` as a `QUrl.fromLocalFile` URL, which also handles Windows paths correctly.
- **Image nodes** (`ImageNode.qml`): `props.asset` holds the hash. Use `Image { asynchronous: true; fillMode: Image.PreserveAspectFit }` and set `sourceSize.width` from displayed width times zoom, rounded up to a power of two. Large reference images then do not eat memory when zoomed out.
- **Paste** (`ClipboardService`, Ctrl+V): read `QGuiApplication.clipboard().mimeData()`.
  - Image data becomes an image node.
  - A URL becomes a `link` node showing the URL as its title (Phase 9 adds metadata).
  - Plain text becomes a note.
  - Place the node under the last cursor position on the canvas, tracked with a `HoverHandler`, or at the viewport center if the cursor is elsewhere.
- **Drop** (`DropArea` on the canvas)
  - Local image files go through `AssetStore`.
  - Images dragged from a browser (Pinterest, Google Images) arrive as a URL. Create the node immediately as a placeholder, download the bytes on `QThreadPool`, then fill it in. Keep the URL in `assets.source_url` so you can credit the source later.
- **Z-order:** `z` column. New nodes go on top. `]` and `[` move the selected node up or down.
- Keep originals at full size on disk. Only the display size is reduced.

**Tests:** `AssetStore` dedup (same bytes twice gives one file and one row), the path layout, and `ClipboardService` against a fake `QMimeData` for image, URL and text cases.

**Done when**

- [ ] Pasting a screenshot places it at the cursor with the right aspect ratio
- [ ] Pasting the same image twice leaves one file in `assets/`
- [ ] Dragging an image from a browser tab creates an image node
- [ ] A bullet list typed into a note renders as a list after you leave edit mode
- [ ] Resize handles keep a constant screen size at 25% and 400% zoom

## Phase 4: Arrows and frames

**Goal:** connect any two nodes with arrows that follow them live, and group nodes visually with frames.

**Build**

- **Data:** migration `004` adds `edges(id, space_id, source_id, target_id, label, style, created_at)` with `ON DELETE CASCADE` from both node foreign keys, and indexes on `source_id` and `target_id`. `style` is JSON: `dashed` (bool), `arrow` (`end`, `both` or `none`), `color`. Reject self-loops.
- `EdgeService` (create, set label, set style, reconnect, delete) and an `EdgeModel` scoped to the space, built like `NodeModel`.
- **Geometry as a tested pure function.** `geometry.edge_geometry(src_rect, dst_rect)` in Python returns start point, end point, two cubic control points and the two arrowhead points.
  - Pick the side of each rectangle that faces the other (top, right, bottom, left midpoints) based on the relative position of their centers.
  - Expose it to QML as a slot on a small helper object. Per-frame calls for the few edges touching a dragged node are cheap. If profiling shows otherwise, port it to a `.pragma library` JS file.
- **`EdgeItem.qml`:** a `Shape` with a `ShapePath` using `PathCubic` for the line and a second filled `ShapePath` for the arrowhead. Draw edges in a layer below the node delegates.
- **Following nodes live:** `Canvas.qml` keeps a registry of delegate items by node id with a `nodeItemsChanged` signal. Each `EdgeItem` resolves its source and target items from it and recomputes when their `x`, `y`, `width` or `height` change. This matters because during a drag the database is not yet written, so the arrows cannot depend on `NodeModel`.
- **Creating edges:** a selected node shows four small connection dots on its sides. Drag from a dot and a temporary line follows the cursor. Release on another node to connect. Release on empty canvas to create a new note at that point, already connected.
- **Selecting edges:** `Shape` does not hit-test strokes, so each edge shows a small chip at its midpoint that shows the label, or a dot when empty. Click it to select, double-click to edit the label, Delete removes the edge. A precise fallback is to sample the curve at about 20 points and test the click distance in Python.
- **Frames:** node kind `frame`, a titled rectangle with a translucent fill, drawn in a z-band below normal nodes. It is resizable and its title and tint are editable.
  - Dragging a frame moves every node whose rectangle was fully inside it when the drag started. Compute that set at drag start, never store it, and commit all moves as one `NodeService.move_many` call.
  - Frames are how you will mark a cluster for Phase 7.
- Deleting a node removes its edges through the cascade.

**Tests:** `edge_geometry` for each relative position (right-of, below, overlapping) and arrowhead angle, edge cascade on node delete, and the frame containment function.

**Done when**

- [ ] Dragging a node moves its arrows in real time with no lag at 100 nodes
- [ ] Dragging from a connection dot onto empty space creates a connected note
- [ ] Edge labels can be edited and survive a restart
- [ ] Moving a frame carries the nodes inside it and nothing else
- [ ] Deleting a node removes its arrows

## Phase 5: Node kinds, status, promotion, selection and undo

**Goal:** a loose note can become a tracked feature without being retyped, and every action on the canvas can be undone.

**Build**

- **Kind registry** in `domain/kinds.py`, the single source of truth read by Python and QML. Each kind defines label, icon, accent color, default size, allowed statuses and its `props` fields.

  | Kind | Statuses |
  | --- | --- |
  | `note`, `image`, `link`, `frame` | none |
  | `question` | open, answered, dropped |
  | `feature` | idea, planned, in\_progress, done, dropped |
  | `bug` | open, in\_progress, fixed, wontfix |
  | `doc` | draft, current, outdated |
  | `code_todo` | open, resolved, promoted (used in Phase 8) |
- **Migration `005`:** `nodes.priority` (0 to 3, default 0), `tags(id, name UNIQUE)` and `node_tags(node_id, tag_id)`. Tags are free-form (combat, audio, ui, level design) and used for filtering in Phase 6.
- **Visual language:** a small kind badge and a status pill on each card, and an accent border by kind. A toolbar toggle dims `done`, `fixed` and `dropped` nodes so the board shows what is still alive.
- **Promotion:** `NodeService.promote(id, kind, status=None)` changes kind and applies the default status. Position, size, edges and body are untouched. Reach it from the right-click menu (Turn into) and from the inspector. Demoting back to a note is allowed.
- **Answering a question:** an Answer action sets the question to `answered` and creates a connected node beside it (note, feature or doc, your choice) with an edge labelled answer.
- **Quick-add hotkeys** when no text field has focus: `N` note, `Q` question, `F` feature, `B` bug. The node appears under the cursor in edit mode.
- **Inspector dock** on the right for the selected node: kind, status (limited to that kind's statuses), priority, tags, created and updated times, and the body. With several nodes selected it shows only shared fields and applies changes to all of them.
- **Selection state** lives in a Python `SelectionState` QObject (a set of node ids) so shortcuts, the inspector and commands all see the same selection.
  - Shift-click toggles. Left-drag on empty canvas draws a rubber-band lasso that selects intersecting nodes (Ctrl adds). Ctrl+A selects all.
  - Dragging any selected node moves the whole selection and commits one `move_many` on release.
- **Copy, paste, duplicate:** Ctrl+C, Ctrl+V, Ctrl+D on the selection, including the edges between the selected nodes. Use an internal mime type `application/x-brainstorm-nodes` carrying JSON. This also lets you copy between the global board and a project later. Extend the Phase 3 `ClipboardService`.
- **Undo and redo** with `QUndoStack` and `QUndoCommand` subclasses (`CreateNodes`, `DeleteNodes`, `MoveNodes`, `UpdateNode`, `PromoteNode`, `ResizeNode`, `CreateEdge`, `DeleteEdge`).
  - Retrofit the Phase 1 to 4 service methods to push commands. This is why every write goes through services.
  - `DeleteNodes` must capture the nodes, their edges and their tags so undo restores everything.
  - Group compound actions with `beginMacro` (for example drag-an-arrow-to-empty-space, which creates a node and an edge).
  - Merge consecutive edits of the same text node made within one second. History is per session and is not stored in the database.
  - Ctrl+Z, and Ctrl+Shift+Z or Ctrl+Y for redo.

**Tests:** promotion keeps position and edges, allowed statuses are enforced per kind, undo and redo round trips (delete with edges, paste, promote), bulk edit applies to every selected node.

**Done when**

- [ ] Press `F` on the board, type, and a feature node appears under the cursor
- [ ] A note promoted to a feature keeps its arrows and position
- [ ] Lasso-select 10 nodes, drag them together, undo restores them in one step
- [ ] Deleting a node with arrows and then undoing brings back the arrows too
- [ ] Copy a cluster, paste it, and the arrows between the copies are intact

## Phase 6: List and kanban views

**Goal:** the overview your Windows todo list never gave you: the same nodes, shown by status and kind instead of by position.

**Build**

- **View switcher** in the content header: Canvas, List, Board. Later phases add Docs, Code, Resources. `AppState.currentView` drives it. Selection state and the inspector are shared, so selecting a node in the list also selects it on the canvas.
- **Filtering model:** a `QSortFilterProxyModel` subclass over `NodeModel`, with properties exposed to QML: `kinds`, `statuses`, `tags`, `minPriority`, `searchText`, `sortKey`, `sortOrder`. Add a `tags` role (list of strings) to `NodeModel` so tag filters work.
- **Preset filter chips** above every list: Open questions, Open bugs, In progress, Ideas, Done. They are shortcuts for the filters above.
- **Summary strip** at the top of the space, for example: 12 ideas, 4 in progress, 3 open bugs, 5 unanswered questions. Click an item to apply that filter.
- **List view** (`ListView.qml`): kind icon, title, status, priority, tags, updated time. The status cell is an inline dropdown limited to that kind's statuses. Group by kind, status, tag or nothing using `ListView.section`. Keyboard navigation with Up and Down. Enter opens the node on the canvas via `Canvas.focusNode(id)`, which animates the viewport (`NumberAnimation` on `world.x`, `world.y` and `world.scale`) to center on it.
- **Board view** (`KanbanView.qml`):
  - A kind selector (Feature, Bug, Question, Doc) chooses which statuses become columns, in the order defined in the kind registry.
  - Cards show title, tags, priority and a link icon if the node has edges or resources.
  - Dragging a card to another column calls `NodeService.set_status` as an undoable command. Implement with a `DragHandler` on the card and a `DropArea` per column, and show a ghost card while dragging.
  - Migration `006` adds `nodes.rank` (REAL). Reordering inside a column assigns the midpoint between neighbors. When the gap becomes too small, renumber that column. Put this in a tested helper `ranking.between(a, b)`.
  - A quick-add field at the bottom of each column creates a node of that kind and status.
- **Nodes without a canvas position:** items created from the list or board have `x` and `y` set to null. Add a Show on canvas action (places the node at the viewport center) and its inverse, Remove from canvas.
- **Filter highlight on the canvas:** when a filter is active, optionally dim canvas nodes that do not match. This shares filter state between views and is cheap to build.

**Tests:** proxy filtering and sorting combinations, `ranking.between` including renumbering, status changes through the undo stack.

**Done when**

- [ ] Open bugs and unanswered questions are each one click away
- [ ] Dragging a feature from Planned to In progress persists and can be undone
- [ ] Enter on a list row jumps the canvas to that node
- [ ] A feature added from the board does not appear on the canvas until Show on canvas is used
- [ ] Reordering cards within a column survives a restart

## Phase 7: Projects

**Goal:** lasso or frame a cluster on the global board, press Start project, and the cluster moves into its own space with a brainstorm canvas of its own, while the global board keeps a card pointing at it.

**Build**

- **Data:** migration `007` adds `spaces.description`, `spaces.status` (active, paused, shipped), `spaces.root_path` (the code folder, used in Phase 8) and `spaces.engine` (godot, odin, other). Add the node kind `project_link` to the registry.
- **Start project flow** (toolbar button, right-click menu, or `Ctrl+Shift+P` on a selection):
  - If a frame is selected, include every node inside it and use the frame title as the default name. Otherwise use the selected nodes and the title of the first one.
  - A dialog asks for name, engine, and an optional code folder (folder picker; can be set later).
- **`ProjectService.create_from_selection(node_ids, name, ...)`** runs in one SQLite transaction and one undo command:
  1. Insert the project space.
  2. Set `space_id` on the selected nodes to the new space. Translate positions so the cluster's bounding-box center becomes (0, 0).
  3. Move edges that connect two selected nodes into the new space.
  4. Create a `project_link` node on the global board at the cluster's former center. Its `props.project_id` points at the project.
  5. For each edge that crossed the cluster boundary, reattach the inside endpoint to the `project_link` node, keeping direction and label. Merge duplicates (same outside node and same direction).
  - Assets are stored by hash and shared, and tags stay attached to nodes, so neither needs copying.
- **Project link card:** shows the project name, status, a thumbnail of the first image node in the project, and counts such as open features and open bugs. Double-click opens the project.
- **Navigation**
  - Left sidebar lists the Global board and all non-archived projects with status and counts.
  - A breadcrumb in the header shows Board, then the project name.
  - Each space remembers its own viewport (Phase 2) and its last-used view.
  - Inside a project the header tabs are Brainstorm (the canvas), List, Board. Later phases add Docs, Code, Resources and Overview. Add tabs as their phases land.
- **Blank project** from the sidebar: creates an empty project space with no link card on the global board.
- **Move to project** for selected nodes on the global board, using the same rules as step 5 to reattach crossing edges to that project's existing link card. Between other spaces, use copy and paste (Phase 5).
- **Archive** a project (sets `archived_at`, hides it from the sidebar, keeps data). A separate confirmed Delete project removes the space, its nodes and its link card.

**Tests:** `create_from_selection` end to end (space ids, internal edges moved, crossing edges reattached and de-duplicated, link card position), undo restores the exact previous state, archive hides a project, `Move to project` reattaches edges.

**Done when**

- [ ] Framing 8 nodes with 3 arrows to the outside and pressing Start project leaves one card on the global board with the 3 arrows attached to it
- [ ] The project canvas shows the 8 nodes with their internal arrows intact
- [ ] Undo of Start project restores the board exactly
- [ ] Switching between the board and two projects keeps each viewport where you left it
- [ ] Thumbnails and counts on the link card update when the project changes

## Phase 8: Code TODO scanner

**Goal:** extract `TODO`, `PERF`, `FIXME` and `HACK` comments from a project's code folder into the tool, and keep them matched to the right node when the code changes. The scanner is read-only and never writes to the code folder.

**Build**

- **Config:** migration `008` adds `spaces.scan_config` (JSON) and `scans(id, space_id, started_at, finished_at, files_scanned, found, added, resolved)`. Defaults:
  - Tags: `TODO`, `FIXME`, `PERF`, `HACK`, `BUG`, `NOTE`. Uppercase only, to avoid matching ordinary prose.
  - Comment prefixes by extension: `#` for `.gd`, `.py`, `.gdshader`; `//` and `/* */` for `.odin`, `.c`, `.h`, `.cpp`, `.cs`, `.glsl`.
  - Ignore globs: `.git`, `.godot`, `addons`, `build`, `node_modules`, `*.import`. Also honor `.gitignore` if `pathspec` is installed.
  - Skip files over 1 MB and files containing null bytes.
- **Parser** (`scanner/parser.py`, pure functions)
  - Matches a prefix, a tag, an optional scope in parentheses, an optional separator and the text, for example `# TODO(enemy): flank when player reloads`. Comments after code on the same line count.
  - Following lines with the same prefix and indentation and no tag are appended to the text, up to 5 lines.
  - `TODO!` sets priority 2 and `TODO!!` sets priority 3.
  - Captures the trimmed code context (the nearest non-comment line, max 120 characters).
  - Tags inside string literals are a known false positive. Accept it.
- **Nodes:** every hit is a `code_todo` node with `x` and `y` null and `props`: `tag`, `file` (path relative to `root_path`), `line`, `text_hash`, `scope`, `context`. The title is the tag plus the text.
- **Reconciliation** (`scanner/reconcile.py`, pure and fully tested). Line numbers drift, so match in passes and mark each existing node and hit as used when matched:
  1. Exact: same file, tag and normalized text. Update the line number.
  2. Moved file: same tag and normalized text in a different file, only if the match is unique.
  3. Edited text: same file, `difflib.SequenceMatcher` ratio of 0.8 or higher on normalized text, best pairs first. Update the text.
  4. Leftover hits become new `code_todo` nodes. Leftover existing open nodes become `resolved` with a timestamp. They are never deleted.
  - Identical duplicates in one file match by order.
- **Promotion:** `NodeService.promote` keeps `props.code_ref` (file, line, text hash). The scanner tracks every node with a `code_ref`. If the comment disappears from a promoted node, flag it as source removed and leave its status alone.
- **Background work:** `ScanService` runs the walk and parse in a `QRunnable` on `QThreadPool` and emits progress and a result signal. Apply reconciliation and database writes on the main thread so there is a single writer. Trigger scans from a Rescan button, on opening the project, and on window refocus. Use a `QFileSystemWatcher` only if full scans prove too slow.
- **Code view** (`CodeView.qml`, a new project tab with a count badge):
  - Group by file or by tag, filter chips per tag, a toggle for resolved and ignored items, text search.
  - Row: tag chip, text, `file:line`.
  - Actions: **Open in editor**, **Promote** (to feature, bug or question), **Show on canvas** (drops it at the viewport center), **Ignore** (adds an `ignored` status that hides it).
- **Open in editor:** an app-wide command template with `{file}` and `{line}` placeholders, default `code --goto {file}:{line}`, with presets for VS Code, Sublime and Zed. Start it with `QProcess.startDetached(program, args)` using an argument list, never a shell string.
- **Reverse direction:** a Copy as TODO comment action on a feature node puts `# TODO: <title>` on the clipboard, with the prefix chosen from a setting.

**Tests:** the parser (each prefix, scope, priority marks, continuation lines, trailing comments), every reconciliation pass (line shift, file rename, text edit, deletion, duplicates), ignore globs, binary skipping. Use a fixture folder with sample `.gd` and `.odin` files.

**Done when**

- [ ] Scanning a real Godot project lists its tagged comments grouped by file
- [ ] Adding blank lines above a TODO and rescanning updates its line, not its identity
- [ ] Rewording a TODO slightly and rescanning keeps the same node
- [ ] Deleting a comment marks its node resolved
- [ ] Open in editor jumps to the right file and line
- [ ] A promoted TODO keeps its code reference

## Phase 9: Resource pane

**Goal:** a library of articles and videos (with timestamps) that you can search for, save, and reference from any node. Build it in three steps: 9a library, 9b mentions, 9c browser.

### 9a: Library and metadata

- **Data:** migration `009` adds
  - `resources(id, space_id, url, normalized_url, kind, title, site, author, description, thumbnail_hash, notes, fetch_status, created_at, fetched_at)`, where `kind` is article, video, image or other
  - `resource_refs(id, resource_id, label, timestamp_seconds, note)` for video timestamps and article sections
  - `node_resources(node_id, resource_id, ref_id)` for links from nodes to resources
  - `resource_tags(resource_id, tag_id)`, reusing the Phase 5 tags
- **URL normalization:** strip tracking parameters (`utm_*`, `si`, `fbclid`), convert `youtu.be` links to the canonical form, and turn a `t=` parameter into a timestamp ref automatically. Reject duplicates by normalized URL within a space.
- **Metadata fetch** (`ResourceFetcher`, a `QRunnable`): GET with a timeout of 8 seconds, a browser-like user agent and a 2 MB cap. Parse `og:title`, `og:description`, `og:image`, `og:site_name`, `<title>` and author tags with `html.parser`. For YouTube use the oEmbed endpoint (title, channel, thumbnail). Download the thumbnail into `AssetStore`. On failure keep the URL as the title, set `fetch_status` to failed, and offer a Retry. Everything must work offline with those fallbacks.
- **Resources tab** (`ResourcesView.qml`): grid or list toggle with thumbnail cards, search, and filters by kind and tag. Add a resource by pasting a URL, using the add field, or dropping a URL from a browser. A scope switch chooses This project, Global board or All.
- **Detail panel:** markdown notes, a timestamp list (type `12:40 hitstop on heavy attacks`, parsed to seconds), Open (uses `QDesktopServices.openUrl`, adding `&t=` for YouTube timestamps), and a Referenced by list of nodes.
- **Link nodes on the canvas** are now backed by a resource: `props.resource_id`. Pasting a URL (Phase 3) creates the resource and a link node showing thumbnail, title and site. A `DropArea` accepts `application/x-brainstorm-resource` so you can drag a resource from the pane onto the canvas.

### 9b: Attaching and @-mentions

- Typing `@` in any text editor (notes, the inspector body, Phase 10 docs) opens a fuzzy-searchable popup of resources. Picking one inserts a markdown link such as `[Hitstop breakdown @12:40](brainstorm://resource/<id>?ref=<ref_id>)`. Clicking it (`onLinkActivated`) opens the resource detail. The scheme `brainstorm://node/<id>` is reserved for Phase 10.
- A `MentionParser` extracts every `brainstorm://` link from a node body on save and syncs `node_resources`, so backlinks stay correct.
- The inspector gets a Resources section with an Add button (a picker) and a list with remove buttons.
- Ctrl+Shift+V with a node selected and a URL on the clipboard creates the resource and attaches it to that node without placing a new node.

### 9c: Embedded browser for searching and clipping

- Use `QtWebEngineQuick` (`WebEngineView`) in a Browse panel of the Resources tab, with an address bar, a search box (default search engine configurable) and quick buttons for YouTube and Pinterest.
- Setup details for PySide6: call `QtWebEngineQuick.initialize()` before creating the application, and give the `WebEngineProfile` a `storageName` so sign-ins persist in the app-data folder.
- Toolbar actions: **Save page** (current URL and title become a resource), **Save video at current time** (on YouTube, read `document.querySelector('video').currentTime` through `runJavaScript`, then create the resource and a timestamp ref), and an image context-menu action **Add to board** (`contextMenuRequested` gives the media URL, imported through `AssetStore` with its `source_url`).
- Keep this optional: wrap the import in a try/except and hide the Browse panel if QtWebEngine is unavailable. Everything in 9a and 9b must work without it.

**Tests:** URL normalization (tracking parameters, `youtu.be`, `t=`), metadata parsing from saved HTML fixtures with no network calls, the oEmbed parser, timestamp parse and format (`1:02:03`, `12:40`), `MentionParser` sync, duplicate detection.

**Done when**

- [ ] Pasting a YouTube link shows its title and thumbnail within a few seconds, and the app stays responsive
- [ ] A resource saved at 12:40 opens the video at 12:40
- [ ] Typing `@` in a feature note inserts a resource link, and the resource lists that node under Referenced by
- [ ] With the network off, pasted links still become nodes with their URL as the title
- [ ] Clipping an image from the embedded browser creates an image node with its source URL stored

## Phase 10: Docs, pillars, devlog, project overview

**Goal:** capture how complex parts work, keep the game's direction visible, and log progress, all linked to the nodes they concern.

**Build**

- **Data:** migration `010` adds `pillars(id, space_id, position, text, description)`, `node_pillars(node_id, pillar_id)`, `node_links(source_id, target_id)` for node-to-node mentions, and `devlog(id, space_id, body, created_at)`.
- **Docs tab** (`DocsView.qml`) for nodes of kind `doc`.
  - Left: a searchable list with an optional folder path in `props.folder` (for example `architecture/camera`). Right: the editor.
  - Editor: a monospace `TextArea` with a Python `MarkdownHighlighter` (`QSyntaxHighlighter` attached through the `textDocument` property) for headings, bold, code, lists, links and mentions. A toggle switches to a read-only preview using `textFormat: MarkdownText`.
  - Templates from a New doc dropdown: Implementation note (Context, How it works, Gotchas, Related), Design note, Postmortem, Playtest session. Store them as plain markdown files in the app.
  - Docs also appear on the canvas as `doc` nodes showing the title and first lines. Double-click opens the doc.
  - Stretch: pasting an image stores it through `AssetStore`, inserts `![](brainstorm://asset/<hash>)`, and resolves it for the preview through a `QQuickImageProvider`.
- **Node mentions:** typing `[[` opens the same popup as `@` (Phase 9) but lists nodes and docs. It inserts `brainstorm://node/<id>` links. Extend `MentionParser` to sync `node_links`. Every node and doc shows a Referenced by list.
- **Docs that go stale:** a doc can list related files in `props.code_paths`. Show them with Open in editor. If any listed file has a modification time newer than the doc's `updated_at`, show a badge: code changed since this doc was updated. This is a plain `os.stat` check.
- **Design pillars:** 3 to 5 short statements per project. Tag nodes with pillars in the inspector (chips), and filter the List and Board views by pillar. An Unaligned filter shows features with no pillar, which is the scope-creep check. Show a soft warning above 5 pillars. Each pillar shows the number of linked features and how many are done.
- **Devlog tab:** a quick-add field at the top (Enter submits, Shift+Enter inserts a newline). Entries are timestamped markdown, grouped by day, editable and deletable, and support `@` and `[[` mentions. An optional setting adds an automatic entry when a feature is marked done.
- **Overview tab** (the project landing page): editable name, status and description, the pillars pinned at the top, the Phase 6 summary strip, features in progress, the last 5 devlog entries, and the count of open code TODOs with a link to the Code tab.

**Tests:** the extended `MentionParser` and backlink sync, stale-doc detection with temporary files and set modification times, pillar coverage counts, devlog grouping by day.

**Done when**

- [ ] Creating an Implementation note from the template and linking it from a feature with `[[` shows the doc under the feature and the feature under the doc's Referenced by
- [ ] Editing a listed code file makes the doc show the stale badge
- [ ] Filtering by Unaligned lists only features without a pillar
- [ ] A devlog entry that mentions a node appears in that node's Referenced by list
- [ ] The Overview tab shows pillars, progress and recent log entries at a glance

## Phase 11: Game-dev extras and export

**Goal:** the creative and safety features that make the tool more than a todo list: asset tracking, palettes, brainstorming prompts, exports and backups. These are independent; build them in the order below.

**1. Asset tracker**

- New node kind `asset_need` with statuses `needed`, `placeholder`, `wip`, `final`. `props`: `category` (sprite, tileset, ui, sfx, music, vfx, model, shader), `file_path` (optional, relative to `root_path`).
- An **Assets tab**: a `TableView` grouped by category with an inline status dropdown and a progress bar showing the share that is `final`, plus a placeholder count. A warning icon shows when `file_path` is set but the file does not exist.
- Reference images are linked with ordinary edges from image nodes on the canvas.

**2. Palette extraction**

- New node kind `palette` with `props.colors` (a list of hex strings), shown as a row of swatches. Clicking a swatch copies its hex value. One palette per project can be flagged `props.project_palette` and shown on the Overview tab.
- Extract from the selected image nodes: downscale with `QImage` to about 64 by 64, run a pure-Python median-cut quantizer (no new dependency), and keep 5 to 8 colors sorted by population. Combined extraction over several images is allowed.
- Export formats: hex list, GIMP `.gpl`, a GDScript constant (`const PALETTE = [Color("#aabbcc"), ...]`), and an Odin array.

**3. Spark prompts** (offline, no network)

- A Spark button on the toolbar and a shortcut drop a random prompt as an accent-styled note at the cursor. Decks are JSON files in the app-data folder that the user can edit: Twists (what if the player cannot jump), Verbs (steal, bind, swap, grow), Genre mashups, Boss design questions, Level design questions.
- **Collide ideas:** pick two random nodes on the board, connect them with an edge labelled `?`, and add a question node asking how they could combine.
- **Starter questions:** one action inserts a framed grid of about 10 question nodes (gameplay loop, boss design, enemy AI and spawn timing, progression, camera, audio, art style, and so on). Load them from an editable `questions.json`.

**4. Export** (a Python `exporters/` package with one function per format)

- **Project Markdown folder:** `README.md` (pillars, status, description), `features.md` grouped by status, `bugs.md`, `questions.md`, `docs/*.md`, `devlog.md`, `resources.md`, and the referenced images copied to `assets/`. Write only to a folder the user chooses. The scanner stays read-only, so never write into `root_path` unless the user picked it as the destination.
- **GDD generator:** one `GDD.md` assembled from pillars, the docs tagged `gdd` (user selects and orders them in a dialog) and features grouped by pillar.
- **Board image:** render the whole canvas, or the selection, to PNG with `grabToImage`, fitting to a maximum of 8192 pixels on the longest side.

**5. Backup and restore**

- The app is local-only, so backups are the safety net. Create a zip of `brainstorm.db` plus `assets/`. Use the `sqlite3` backup API to copy the database to a temporary file first so a write in progress cannot corrupt it.
- Automatic backup on exit at most once a day, keeping the last 5 in `backups/`. Manual backup and restore (with a confirmation, then a restart) in settings.

**Tests:** the median-cut quantizer on synthetic images, each palette export format, Markdown export against golden files built from a fixture database, backup and restore round trip (row counts and asset files identical).

**Done when**

- [ ] Selecting three reference images and extracting a palette gives swatches that visibly match them, and the GDScript export pastes into Godot without edits
- [ ] Spark creates a prompt note at the cursor and Collide ideas connects two real nodes
- [ ] Exporting a project produces a readable folder of Markdown files with its images
- [ ] Restoring a backup on a clean install reproduces the board, projects and images
- [ ] A 300-node board exports to a PNG without freezing the window

## Phase 12: Excalidraw import, polish, packaging

**Goal:** bring your existing boards in, make the app fast and pleasant at real scale, and ship it as something you launch like any other program.

**1. Excalidraw import** (`importers/excalidraw.py`, pure Python, tested against fixture files)

- Read the `.excalidraw` JSON (`elements` plus the `files` map). Skip elements marked `isDeleted`. Keep relative layout and use the array order as z-order. Ignore rotation.
- Mapping:

  | Excalidraw element | Becomes |
  | --- | --- |
  | `text` | `note` with `style=plain`; text bound to a shape (`containerId`) is merged into that shape's card |
  | `rectangle`, `ellipse`, `diamond` with bound text | `note` with `style=card` |
  | `rectangle`, `ellipse`, `diamond` without text | skipped |
  | `image` | image node: decode `files[fileId].dataURL` (base64) into `AssetStore`, size from the element |
  | `arrow` with both `startBinding` and `endBinding` | edge, label from its bound text |
  | `arrow` with a free end, `line`, `freedraw` | skipped |
  | `frame` | `frame` node with its `name` as title |
- Run the whole import as one undo macro into the current space. Show a report dialog listing what was imported and what was skipped, by type.
- **Clipboard import:** the Phase 3 `ClipboardService` detects text of type `excalidraw/clipboard` and runs the same importer, so copying elements in Excalidraw and pasting in the app works.
- tldraw files (`.tldr`) are out of scope for now.

**2. Polish**

- **Command palette** (Ctrl+P): fuzzy search over nodes, docs, resources, projects and actions (Start project, Rescan code, Export, Backup). Selecting a node switches space and calls `Canvas.focusNode`.
- **Global search** with SQLite FTS5: `nodes_fts(title, body, tags)` kept in sync by triggers, results grouped by space.
- **Canvas navigation:** zoom to fit (`Shift+1`), zoom to selection (`Shift+2`), and an optional minimap in a corner.
- **Alignment:** smart guides while dragging (snap within 6 screen pixels to other nodes' edges and centers) and align and distribute actions in the context menu.
- **Performance pass:** build a test board with 1000 nodes and 300 images and profile with the Qt Quick Profiler.
  - Cull delegates outside the visible rectangle by switching `Loader.active`.
  - Draw all edges inside one `Shape` with a `Repeater` of `ShapePath` items to reduce scene graph nodes. Try `Shape.CurveRenderer` (Qt 6.6 or newer) for smoother curves.
- **Theme:** light and dark, following the system setting through `QGuiApplication.styleHints().colorScheme()` where available, with an accent color option.
- **Settings dialog:** editor command, default search engine, theme, backup options, Spark decks folder, scan defaults.
- **Hardening:** a rotating log file in the app-data folder, a global exception hook that logs and shows a dialog, confirmation for destructive actions, an undo toast after deletes, and a first-run empty state with three hints.
- **Safe upgrades:** make the Phase 1 migration runner copy the database to `backups/pre-migration-v<N>.db` before applying any migration.
- A keyboard shortcut cheat sheet on `?`.

**3. Packaging**

- Build a Windows folder distribution with PyInstaller first (`--onedir`). Include the QML directory as data (`--add-data "src/brainstorm/qml;brainstorm/qml"`) and resolve the QML path from `Path(__file__)` or `sys._MEIPASS` when frozen.
- If QtWebEngine is included, check that the Browse panel still works in the frozen build and that its resources are collected.
- Add a version string shown in an About dialog, a script that creates a Start menu shortcut, and an icon.
- The data folder lives outside the install folder, so updating the app never touches your boards.

**Explicitly out of scope:** sync, collaboration, Git integration, freehand drawing, tldraw import.

**Tests:** Excalidraw importer fixtures (text, bound text, image with base64, bound and unbound arrows, frame, deleted and unsupported elements), FTS triggers keep the index in sync, command palette ranking, pre-migration backup is created.

**Done when**

- [ ] Importing a real `.excalidraw` board reproduces its text, images, arrows and frames, and the report lists what was skipped
- [ ] Ctrl+P finds any node, doc or resource and jumps to it
- [ ] A 1000-node test board pans and zooms smoothly
- [ ] The packaged app launches on a machine without Python and keeps its data across an upgrade
- [ ] A migration run leaves a pre-migration backup behind
