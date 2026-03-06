-- 018_working_context.sql
-- Working context for active tracking, decisions, temporary notes

CREATE TABLE IF NOT EXISTS mem_working_context (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    context_type TEXT DEFAULT 'tracking'
        CHECK (context_type IN ('tracking','active_project','pending_decision','temporary')),
    member_id TEXT REFERENCES common_members(id),
    expires_at TEXT,
    source TEXT DEFAULT 'manual' 
        CHECK (source IN ('manual','conversation','proactive','console')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_working_context_member ON mem_working_context(member_id);
CREATE INDEX IF NOT EXISTS idx_working_context_expires ON mem_working_context(expires_at) 
    WHERE expires_at IS NOT NULL;

-- Add governance gate for memory operations
INSERT OR IGNORE INTO pib_config (key, value, description) 
    VALUES ('governance_memory_edit', 'true', 'Auto-approve memory edits from console');
INSERT OR IGNORE INTO pib_config (key, value, description) 
    VALUES ('governance_memory_create', 'true', 'Auto-approve memory creation from console');
INSERT OR IGNORE INTO pib_config (key, value, description) 
    VALUES ('governance_memory_update', 'true', 'Auto-approve memory updates from console');

-- DOWN
-- DROP TABLE IF EXISTS mem_working_context;
-- DELETE FROM pib_config WHERE key LIKE 'governance_memory_%';
