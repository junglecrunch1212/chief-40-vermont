-- 017_pre_bootstrap_fixes.sql
-- Tailscale identity mapping + media storage for photo capture pipeline

-- Map Tailscale login emails to household members
ALTER TABLE common_members ADD COLUMN tailscale_email TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_members_tailscale ON common_members(tailscale_email) WHERE tailscale_email IS NOT NULL;

-- Media storage for camera/photo capture pipeline
CREATE TABLE IF NOT EXISTS cap_media (
    id TEXT PRIMARY KEY,
    capture_id TEXT REFERENCES cap_captures(id),
    filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    ocr_text TEXT,
    ocr_confidence REAL,
    width INTEGER,
    height INTEGER,
    file_size_bytes INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_cap_media_capture ON cap_media(capture_id);

-- DOWN
-- DROP INDEX IF EXISTS idx_members_tailscale;
-- DROP TABLE IF EXISTS cap_media;
