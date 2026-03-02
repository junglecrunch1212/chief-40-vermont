-- Migration 006: Capture Domain — The Second Brain
-- ADHD memory prosthetic: zero-friction capture, deterministic triage,
-- LLM deep organization, FTS5 search, proactive resurfacing.

-- ═══════════════════════════════════════════════════════════════
-- cap_notebooks — Taxonomy buckets (must exist before cap_captures FK)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS cap_notebooks (
    id TEXT PRIMARY KEY,                              -- nb-{ULID}
    member_id TEXT REFERENCES common_members(id),      -- NULL = household-wide
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    icon TEXT,
    description TEXT,
    sort_order INTEGER DEFAULT 100,
    is_system INTEGER DEFAULT 0,
    capture_count INTEGER DEFAULT 0,                   -- Denormalized
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(member_id, slug)
);

-- ═══════════════════════════════════════════════════════════════
-- cap_captures — Main capture storage
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS cap_captures (
    id TEXT PRIMARY KEY,                              -- cap-{ULID}
    member_id TEXT NOT NULL REFERENCES common_members(id),
    raw_text TEXT NOT NULL,                            -- Original input, unmodified
    title TEXT,                                        -- Short title (deterministic or LLM)
    body TEXT,                                         -- Enriched/cleaned body
    source TEXT NOT NULL DEFAULT 'chat',               -- chat, voice, sms, prefix, api
    source_ref TEXT,                                   -- Optional: session_id, comm_id
    capture_type TEXT NOT NULL DEFAULT 'note'
        CHECK (capture_type IN ('note','idea','recipe','bookmark','quote','log','snippet','question','reference')),
    notebook TEXT NOT NULL DEFAULT 'inbox',            -- Taxonomy bucket slug
    priority TEXT DEFAULT 'normal'
        CHECK (priority IN ('high','normal','low','archive')),
    tags TEXT DEFAULT '[]',                            -- JSON array
    connections TEXT DEFAULT '[]',                     -- JSON: [{type, target_table, target_id, reason}]
    extracted_entities TEXT DEFAULT '[]',              -- JSON: [{name, type}]
    summary TEXT,                                      -- LLM 1-line summary
    spawned_task_id TEXT REFERENCES ops_tasks(id),     -- Dual routing
    spawned_memory_id INTEGER REFERENCES mem_long_term(id),
    recipe_data TEXT,                                  -- JSON: {servings, prep_min, cook_min, ingredients, steps, cuisine, dietary_tags}
    household_visible INTEGER NOT NULL DEFAULT 0,
    privacy TEXT NOT NULL DEFAULT 'full' CHECK (privacy IN ('full','privileged','redacted')),
    triage_status TEXT NOT NULL DEFAULT 'triaged'
        CHECK (triage_status IN ('raw','triaged','organized','failed')),
    organize_attempts INTEGER DEFAULT 0,
    last_organized_at TEXT,
    resurface_after TEXT,
    last_resurfaced_at TEXT,
    resurface_count INTEGER DEFAULT 0,
    pinned INTEGER DEFAULT 0,
    archived INTEGER DEFAULT 0,
    archived_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_cap_member ON cap_captures(member_id);
CREATE INDEX IF NOT EXISTS idx_cap_notebook ON cap_captures(notebook);
CREATE INDEX IF NOT EXISTS idx_cap_type ON cap_captures(capture_type);
CREATE INDEX IF NOT EXISTS idx_cap_triage ON cap_captures(triage_status);
CREATE INDEX IF NOT EXISTS idx_cap_resurface ON cap_captures(resurface_after) WHERE resurface_after IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cap_household ON cap_captures(household_visible) WHERE household_visible = 1;
CREATE INDEX IF NOT EXISTS idx_cap_pinned ON cap_captures(pinned) WHERE pinned = 1;

-- ═══════════════════════════════════════════════════════════════
-- cap_connections — Cross-capture and cross-domain links
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS cap_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_capture_id TEXT NOT NULL REFERENCES cap_captures(id),
    target_type TEXT NOT NULL CHECK (target_type IN ('capture','task','event','memory','comm','item','notebook')),
    target_id TEXT NOT NULL,
    connection_type TEXT NOT NULL DEFAULT 'related'
        CHECK (connection_type IN ('related','derived_from','supports','contradicts','extends','recipe_variation')),
    reason TEXT,
    confidence REAL DEFAULT 1.0,
    created_by TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(source_capture_id, target_type, target_id)
);

-- ═══════════════════════════════════════════════════════════════
-- FTS5 full-text search index
-- ═══════════════════════════════════════════════════════════════

CREATE VIRTUAL TABLE IF NOT EXISTS cap_captures_fts USING fts5(
    raw_text, title, body, tags, summary,
    content='cap_captures', content_rowid='rowid'
);

-- FTS5 sync triggers
CREATE TRIGGER IF NOT EXISTS cap_fts_insert AFTER INSERT ON cap_captures BEGIN
    INSERT INTO cap_captures_fts(rowid, raw_text, title, body, tags, summary)
    VALUES (NEW.rowid, NEW.raw_text, NEW.title, NEW.body, NEW.tags, NEW.summary);
END;

CREATE TRIGGER IF NOT EXISTS cap_fts_update AFTER UPDATE ON cap_captures BEGIN
    INSERT INTO cap_captures_fts(cap_captures_fts, rowid, raw_text, title, body, tags, summary)
    VALUES ('delete', OLD.rowid, OLD.raw_text, OLD.title, OLD.body, OLD.tags, OLD.summary);
    INSERT INTO cap_captures_fts(rowid, raw_text, title, body, tags, summary)
    VALUES (NEW.rowid, NEW.raw_text, NEW.title, NEW.body, NEW.tags, NEW.summary);
END;

CREATE TRIGGER IF NOT EXISTS cap_fts_delete AFTER DELETE ON cap_captures BEGIN
    INSERT INTO cap_captures_fts(cap_captures_fts, rowid, raw_text, title, body, tags, summary)
    VALUES ('delete', OLD.rowid, OLD.raw_text, OLD.title, OLD.body, OLD.tags, OLD.summary);
END;

-- ═══════════════════════════════════════════════════════════════
-- Seed config
-- ═══════════════════════════════════════════════════════════════

INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('capture_deep_organizer_enabled', '1', 'Enable LLM deep organizer for captures');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('capture_deep_organizer_interval_minutes', '30', 'Deep organizer run interval');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('capture_deep_organizer_batch_size', '20', 'Max captures per organizer run');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('capture_resurfacing_enabled', '1', 'Enable proactive capture resurfacing');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('capture_resurfacing_max_per_day', '3', 'Max resurfaces per day per member');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('capture_cross_user_connections', '1', 'Enable cross-user connection discovery');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('capture_recipe_extraction', '1', 'Enable structured recipe data extraction');

INSERT INTO meta_schema_version (version, description) VALUES (6, 'Capture domain');

-- DOWN
DROP TRIGGER IF EXISTS cap_fts_insert;
DROP TRIGGER IF EXISTS cap_fts_update;
DROP TRIGGER IF EXISTS cap_fts_delete;
DROP TABLE IF EXISTS cap_captures_fts;
DROP TABLE IF EXISTS cap_connections;
DROP TABLE IF EXISTS cap_captures;
DROP TABLE IF EXISTS cap_notebooks;
DELETE FROM pib_config WHERE key LIKE 'capture_%';
DELETE FROM meta_schema_version WHERE version = 6;
