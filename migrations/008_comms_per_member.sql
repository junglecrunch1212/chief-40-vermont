-- Migration 008: Per-member comms database schema
-- Creates the schema used for individual member comms databases (comms_james.db, comms_laura.db)
-- These are separate databases from the main pib.db for privacy isolation.

CREATE TABLE IF NOT EXISTS raw_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bridge_message_id TEXT UNIQUE,
    text TEXT,
    sender TEXT,
    recipient TEXT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    channel TEXT DEFAULT 'imessage',
    direction TEXT DEFAULT 'inbound' CHECK (direction IN ('inbound','outbound')),
    metadata TEXT DEFAULT '{}',
    indexed INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_raw_messages_timestamp ON raw_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_messages_indexed ON raw_messages(indexed);

-- Privacy config for this member's comms store
CREATE TABLE IF NOT EXISTS comms_privacy_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

INSERT OR IGNORE INTO comms_privacy_config (key, value) VALUES
    ('owner_member_id', ''),
    ('privileged_domains', '[]'),
    ('retention_days', '90');

-- DOWN
DROP TABLE IF EXISTS comms_privacy_config;
DROP TABLE IF EXISTS raw_messages;
