CREATE TABLE spaces (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('global', 'project')),
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    archived_at TEXT
);

-- Exactly one global space may exist.
CREATE UNIQUE INDEX idx_spaces_one_global ON spaces (kind) WHERE kind = 'global';

CREATE TABLE nodes (
    id          TEXT PRIMARY KEY,
    space_id    TEXT NOT NULL REFERENCES spaces (id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    body        TEXT NOT NULL DEFAULT '',
    status      TEXT,
    x           REAL,
    y           REAL,
    w           REAL,
    h           REAL,
    z           INTEGER NOT NULL DEFAULT 0,
    props       TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(props)),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX idx_nodes_space_kind   ON nodes (space_id, kind);
CREATE INDEX idx_nodes_space_status ON nodes (space_id, status);
