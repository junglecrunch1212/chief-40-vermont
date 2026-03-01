-- Migration 004: Voice Intelligence
-- Date: 2026-03-01
-- Description: Creates cos_voice_corpus and cos_voice_profiles tables for
--   voice-matched draft generation. Part of Comms Domain (Section 14).

-- ============================================================================
-- up_sql
-- ============================================================================

-- Raw outbound message samples, dimensionally labeled.
-- Accumulates passively — every approved draft or direct reply adds a row.
-- No user effort required. Labels come from existing ops_items and
-- pib_energy_states data at write time.
CREATE TABLE IF NOT EXISTS cos_voice_corpus (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES common_members(id),
    channel TEXT NOT NULL,
    comm_type TEXT,
    recipient_type TEXT CHECK (recipient_type IN ('professional','friend','family','service','unknown')),
    item_ref TEXT REFERENCES ops_items(id),
    body TEXT NOT NULL,
    word_count INTEGER,
    formality_score REAL,
    energy_state TEXT,
    labels TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_voice_corpus_member
    ON cos_voice_corpus(member_id, created_at);

CREATE INDEX IF NOT EXISTS idx_voice_corpus_scope
    ON cos_voice_corpus(member_id, channel, recipient_type);

-- Synthesized voice descriptions at hierarchical scope levels.
-- Rebuilt weekly from corpus by LLM. Resolution at draft time:
-- person > channel_x_type > person_type > domain > channel > baseline.
-- Narrow scopes override broad.
CREATE TABLE IF NOT EXISTS cos_voice_profiles (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES common_members(id),
    scope TEXT NOT NULL,
    scope_level INTEGER NOT NULL DEFAULT 0,
    sample_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.0,
    style_summary TEXT,
    vocabulary TEXT,
    avg_length REAL,
    avg_formality REAL,
    rebuilt_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(member_id, scope)
);

CREATE INDEX IF NOT EXISTS idx_voice_profiles_member
    ON cos_voice_profiles(member_id, scope_level DESC);

-- Register migration
INSERT OR IGNORE INTO meta_migrations (version, name, up_sql, down_sql, applied_at, checksum)
VALUES (4, '004_voice_intelligence', 'migrations/004_voice_intelligence.sql', 'See down_sql section in file', strftime('%Y-%m-%dT%H:%M:%SZ','now'), 'pending');

-- ============================================================================
-- down_sql
-- ============================================================================

-- DROP INDEX IF EXISTS idx_voice_corpus_member;
-- DROP INDEX IF EXISTS idx_voice_corpus_scope;
-- DROP INDEX IF EXISTS idx_voice_profiles_member;
-- DROP TABLE IF EXISTS cos_voice_corpus;
-- DROP TABLE IF EXISTS cos_voice_profiles;
-- DELETE FROM meta_migrations WHERE id = 4;
