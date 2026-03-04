-- PIB v5 Migration 002: Per-member settings table
-- Extends the flat pib_config (system-wide) with member-scoped key-value settings.
-- Complements per-member columns on common_members with extensible overrides.

CREATE TABLE IF NOT EXISTS pib_member_settings (
    member_id TEXT NOT NULL REFERENCES common_members(id),
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_by TEXT DEFAULT 'system',
    PRIMARY KEY(member_id, key)
);

INSERT INTO meta_schema_version (version, description) VALUES (2, 'Add pib_member_settings table');
