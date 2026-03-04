-- ═══════════════════════════════════════════════════════════════
-- Migration 013: Entity Hierarchy & Member-Channel Access
-- Per-member channel visibility, permissions, and digest preferences
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS comms_channel_member_access (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL REFERENCES common_members(id) ON DELETE CASCADE,
    channel_id TEXT NOT NULL REFERENCES comms_channels(id) ON DELETE CASCADE,
    
    -- Access level
    access_level TEXT NOT NULL DEFAULT 'read'
        CHECK (access_level IN ('none','read','write','admin')),
    
    -- UI visibility
    show_in_inbox INTEGER DEFAULT 1,
    
    -- Permissions
    can_approve_drafts INTEGER DEFAULT 0,
    receives_proactive INTEGER DEFAULT 1,
    
    -- Digest preferences
    digest_include INTEGER DEFAULT 1,
    notify_on_urgent INTEGER DEFAULT 1,
    batch_window TEXT
        CHECK (batch_window IS NULL OR batch_window IN ('morning','midday','evening')),
    
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    
    UNIQUE(member_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_channel_access_member ON comms_channel_member_access(member_id);
CREATE INDEX IF NOT EXISTS idx_channel_access_channel ON comms_channel_member_access(channel_id);
CREATE INDEX IF NOT EXISTS idx_channel_access_inbox ON comms_channel_member_access(show_in_inbox) WHERE show_in_inbox = 1;

-- ═══════════════════════════════════════════════════════════════
-- Link devices → channels
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS comms_channel_devices (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL REFERENCES comms_channels(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL REFERENCES comms_devices(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'primary' CHECK (role IN ('primary','backup','read_only')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(channel_id, device_id)
);
CREATE INDEX IF NOT EXISTS idx_channel_devices_channel ON comms_channel_devices(channel_id);
CREATE INDEX IF NOT EXISTS idx_channel_devices_device ON comms_channel_devices(device_id);

-- ═══════════════════════════════════════════════════════════════
-- Link accounts → channels
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS comms_channel_accounts (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL REFERENCES comms_channels(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES comms_accounts(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'primary' CHECK (role IN ('primary','secondary','read_only')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(channel_id, account_id)
);
CREATE INDEX IF NOT EXISTS idx_channel_accounts_channel ON comms_channel_accounts(channel_id);
CREATE INDEX IF NOT EXISTS idx_channel_accounts_account ON comms_channel_accounts(account_id);

INSERT INTO meta_schema_version (version, description) VALUES (13, 'Entity hierarchy & member-channel access');

-- DOWN
DROP TABLE IF EXISTS comms_channel_accounts;
DROP TABLE IF EXISTS comms_channel_devices;
DROP TABLE IF EXISTS comms_channel_member_access;
