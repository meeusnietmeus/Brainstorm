-- Content-addressed image store index. The files live in assets/<first 2 hex>/<hash>.<ext>.
CREATE TABLE assets (
    hash        TEXT PRIMARY KEY,   -- SHA-256 of the file bytes
    ext         TEXT NOT NULL,
    width       INTEGER NOT NULL,
    height      INTEGER NOT NULL,
    bytes       INTEGER NOT NULL,
    source_url  TEXT,
    created_at  TEXT NOT NULL
);
