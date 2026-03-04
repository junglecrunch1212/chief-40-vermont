-- ═══════════════════════════════════════════════════════════════
-- Migration 012: Omni-Channel Registry
-- Unified channel architecture for all inbound/outbound comms
-- ═══════════════════════════════════════════════════════════════

-- ─── Channels ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS comms_channels (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    icon TEXT DEFAULT '💬',
    category TEXT NOT NULL DEFAULT 'conversational'
        CHECK (category IN ('conversational','broadcast','capture','administrative')),
    adapter_id TEXT NOT NULL,
    enabled INTEGER DEFAULT 0,
    setup_complete INTEGER DEFAULT 0,
    
    -- Privacy & content storage
    privacy_level TEXT DEFAULT 'full'
        CHECK (privacy_level IN ('full','metadata_only','none')),
    content_storage TEXT DEFAULT 'full'
        CHECK (content_storage IN ('full','metadata_only','none','encrypted')),
    
    -- Behavior flags
    outbound_requires_approval INTEGER DEFAULT 1,
    reply_channel_default INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 100,
    
    -- Behavioral config (JSON)
    config_json TEXT,
    
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_channels_enabled ON comms_channels(enabled);
CREATE INDEX IF NOT EXISTS idx_channels_category ON comms_channels(category);

-- ─── Channel Health ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS comms_channel_health (
    channel_id TEXT PRIMARY KEY REFERENCES comms_channels(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'inactive'
        CHECK (status IN ('active','degraded','offline','inactive','error')),
    consecutive_failures INTEGER DEFAULT 0,
    last_poll_at TEXT,
    last_successful_at TEXT,
    last_error TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ─── Onboarding Steps ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS comms_onboarding_steps (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL REFERENCES comms_channels(id) ON DELETE CASCADE,
    step_key TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','in_progress','completed','skipped')),
    completed_at TEXT,
    UNIQUE(channel_id, step_key)
);
CREATE INDEX IF NOT EXISTS idx_onboarding_channel ON comms_onboarding_steps(channel_id);

-- ─── Devices ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS comms_devices (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    device_type TEXT NOT NULL
        CHECK (device_type IN ('mac','linux','raspberry_pi','android','ios','cloud')),
    status TEXT NOT NULL DEFAULT 'inactive'
        CHECK (status IN ('active','offline','degraded','error')),
    location TEXT,
    owner_member_id TEXT REFERENCES common_members(id),
    last_seen_at TEXT,
    config_json TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ─── Accounts ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS comms_accounts (
    id TEXT PRIMARY KEY,
    account_type TEXT NOT NULL
        CHECK (account_type IN ('email','phone','social','api','webhook')),
    address TEXT NOT NULL,
    display_name TEXT,
    owner_member_id TEXT REFERENCES common_members(id),
    provider TEXT,
    auth_status TEXT DEFAULT 'inactive'
        CHECK (auth_status IN ('active','expired','revoked','inactive')),
    capabilities_json TEXT,
    config_json TEXT,
    active INTEGER DEFAULT 1,
    last_auth_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(account_type, address)
);
CREATE INDEX IF NOT EXISTS idx_accounts_member ON comms_accounts(owner_member_id);

-- ═══════════════════════════════════════════════════════════════
-- Config seeds
-- ═══════════════════════════════════════════════════════════════

INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('channels_enabled', '1', 'Enable omni-channel routing');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('channel_poll_interval_seconds', '60', 'Seconds between channel health checks');

INSERT INTO meta_schema_version (version, description) VALUES (12, 'Omni-channel registry');

-- DOWN
DROP TABLE IF EXISTS comms_accounts;
DROP TABLE IF EXISTS comms_devices;
DROP TABLE IF EXISTS comms_onboarding_steps;
DROP TABLE IF EXISTS comms_channel_health;
DROP TABLE IF EXISTS comms_channels;
