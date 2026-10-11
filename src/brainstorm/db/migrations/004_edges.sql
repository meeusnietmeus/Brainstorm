-- Arrows between two nodes. Deleting either node deletes the edge (ON DELETE CASCADE).
-- style is JSON: {"dashed": bool, "arrow": "end" | "both" | "none", "color": "#rrggbb"}
CREATE TABLE edges (
    id          TEXT PRIMARY KEY,
    space_id    TEXT NOT NULL REFERENCES spaces (id) ON DELETE CASCADE,
    source_id   TEXT NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
    target_id   TEXT NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
    label       TEXT NOT NULL DEFAULT '',
    style       TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(style)),
    created_at  TEXT NOT NULL,
    CHECK (source_id <> target_id),         -- no self-loops
    UNIQUE (source_id, target_id)           -- one arrow per direction between two nodes
);

CREATE INDEX idx_edges_space  ON edges (space_id);
CREATE INDEX idx_edges_source ON edges (source_id);
CREATE INDEX idx_edges_target ON edges (target_id);
