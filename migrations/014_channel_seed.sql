-- ═══════════════════════════════════════════════════════════════
-- Migration 014: Default Channel Seed Data
-- Family household default channels, devices, and accounts
-- ═══════════════════════════════════════════════════════════════

-- ─── Household Parents (FK parents for the device/account/channel rows below) ─
-- Minimal stub rows so the FK references below resolve on a fresh bootstrap.
-- Full member metadata is filled in post-bootstrap by scripts/seed_data.py.
INSERT OR IGNORE INTO common_members (id, display_name, role) VALUES
    ('m-james', 'James', 'parent'),
    ('m-laura', 'Laura', 'parent');

-- ─── Devices ──────────────────────────────────────────────────

INSERT INTO comms_devices (id, display_name, device_type, status, location, owner_member_id) VALUES
    ('device-mac-mini', 'Mac Mini (PIB Runtime)', 'mac', 'active', 'Home Office', 'm-james'),
    ('device-skylight', 'Skylight Calendar Display', 'cloud', 'active', 'Kitchen', 'm-james'),
    ('device-james-iphone', 'James iPhone', 'ios', 'active', 'Mobile', 'm-james'),
    ('device-laura-iphone', 'Laura iPhone', 'ios', 'active', 'Mobile', 'm-laura');

-- ─── Accounts ─────────────────────────────────────────────────

INSERT INTO comms_accounts (id, account_type, address, display_name, owner_member_id, provider, auth_status) VALUES
    ('acct-james-gmail', 'email', 'james.stice@gmail.com', 'James Gmail', 'm-james', 'gmail', 'active'),
    ('acct-laura-gmail', 'email', 'laura.sclafani@gmail.com', 'Laura Gmail', 'm-laura', 'gmail', 'active'),
    ('acct-james-phone', 'phone', '+14048495800', 'James Cell', 'm-james', 'att', 'active'),
    ('acct-laura-phone', 'phone', '+14049876543', 'Laura Cell', 'm-laura', 'verizon', 'active');

-- ─── Channels ─────────────────────────────────────────────────

INSERT INTO comms_channels (id, display_name, icon, category, adapter_id, enabled, setup_complete, privacy_level, content_storage, outbound_requires_approval, reply_channel_default, sort_order) VALUES
    -- WhatsApp channels (conversational, bidirectional)
    ('whatsapp_family', 'WhatsApp Family Group', '👨‍👩‍👦', 'conversational', 'whatsapp_api', 1, 1, 'full', 'full', 0, 1, 10),
    ('whatsapp_james', 'WhatsApp → James', '📱', 'conversational', 'whatsapp_api', 1, 1, 'full', 'full', 0, 1, 20),
    ('whatsapp_laura', 'WhatsApp → Laura', '📱', 'conversational', 'whatsapp_api', 1, 1, 'full', 'full', 0, 0, 30),
    
    -- Gmail channels
    ('gmail_personal', 'James Personal Gmail', '📧', 'conversational', 'gmail_api', 1, 1, 'full', 'full', 1, 0, 40),
    ('gmail_laura', 'Laura Gmail (Read-Only)', '📧', 'conversational', 'gmail_api', 1, 1, 'metadata_only', 'metadata_only', 1, 0, 50),
    
    -- iMessage (via BlueBubbles)
    ('imessage', 'iMessage (Mac Mini)', '💬', 'conversational', 'bluebubbles', 1, 1, 'full', 'full', 0, 1, 5),
    
    -- Capture channels (inbound-only)
    ('siri_shortcuts', 'Siri Shortcuts (Webhook)', '🎤', 'capture', 'webhook_generic', 1, 1, 'full', 'full', 0, 0, 60),
    ('webconsole', 'Web Console (:3333)', '🖥️', 'administrative', 'http_direct', 1, 1, 'full', 'full', 0, 0, 1),
    
    -- Broadcast channels (outbound-only)
    ('skylight_calendar', 'Skylight Calendar Display', '📅', 'broadcast', 'skylight_api', 1, 1, 'none', 'none', 1, 0, 70);

-- ─── Channel Health (initial status) ──────────────────────────

INSERT INTO comms_channel_health (channel_id, status, last_successful_at) VALUES
    ('whatsapp_family', 'active', strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    ('whatsapp_james', 'active', strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    ('whatsapp_laura', 'active', strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    ('gmail_personal', 'active', strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    ('gmail_laura', 'active', strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    ('imessage', 'active', strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    ('siri_shortcuts', 'active', strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    ('webconsole', 'active', strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    ('skylight_calendar', 'active', strftime('%Y-%m-%dT%H:%M:%SZ','now'));

-- ─── Link Channels → Devices ──────────────────────────────────

INSERT INTO comms_channel_devices (id, channel_id, device_id, role) VALUES
    ('cd-imessage-mac', 'imessage', 'device-mac-mini', 'primary'),
    ('cd-webconsole-mac', 'webconsole', 'device-mac-mini', 'primary'),
    ('cd-skylight', 'skylight_calendar', 'device-skylight', 'primary');

-- ─── Link Channels → Accounts ─────────────────────────────────

INSERT INTO comms_channel_accounts (id, channel_id, account_id, role) VALUES
    ('ca-gmail-james', 'gmail_personal', 'acct-james-gmail', 'primary'),
    ('ca-gmail-laura', 'gmail_laura', 'acct-laura-gmail', 'primary'),
    ('ca-whatsapp-james', 'whatsapp_james', 'acct-james-phone', 'primary'),
    ('ca-whatsapp-laura', 'whatsapp_laura', 'acct-laura-phone', 'primary');

-- ─── Member Access (James = admin, Laura = read on her Gmail) ─

INSERT INTO comms_channel_member_access (id, member_id, channel_id, access_level, show_in_inbox, can_approve_drafts, receives_proactive, digest_include, notify_on_urgent, batch_window) VALUES
    -- James: admin access to all channels
    ('ma-james-whatsapp-family', 'm-james', 'whatsapp_family', 'admin', 1, 1, 1, 1, 1, 'morning'),
    ('ma-james-whatsapp-james', 'm-james', 'whatsapp_james', 'admin', 1, 1, 1, 1, 1, 'morning'),
    ('ma-james-whatsapp-laura', 'm-james', 'whatsapp_laura', 'write', 1, 1, 1, 1, 1, 'morning'),
    ('ma-james-gmail', 'm-james', 'gmail_personal', 'admin', 1, 1, 1, 1, 1, 'midday'),
    ('ma-james-gmail-laura', 'm-james', 'gmail_laura', 'read', 1, 0, 0, 1, 1, NULL),
    ('ma-james-imessage', 'm-james', 'imessage', 'admin', 1, 1, 1, 1, 1, 'morning'),
    ('ma-james-siri', 'm-james', 'siri_shortcuts', 'admin', 1, 0, 0, 1, 0, NULL),
    ('ma-james-webconsole', 'm-james', 'webconsole', 'admin', 0, 1, 0, 0, 0, NULL),
    ('ma-james-skylight', 'm-james', 'skylight_calendar', 'admin', 0, 1, 0, 0, 0, NULL),
    
    -- Laura: read on her Gmail (privacy-fenced), write on WhatsApp
    ('ma-laura-whatsapp-family', 'm-laura', 'whatsapp_family', 'write', 1, 0, 1, 1, 1, 'evening'),
    ('ma-laura-whatsapp-laura', 'm-laura', 'whatsapp_laura', 'admin', 1, 1, 1, 1, 1, 'evening'),
    ('ma-laura-gmail', 'm-laura', 'gmail_laura', 'admin', 1, 1, 1, 0, 1, 'evening'),
    ('ma-laura-imessage', 'm-laura', 'imessage', 'write', 1, 0, 1, 1, 1, 'evening');

INSERT INTO meta_schema_version (version, description) VALUES (14, 'Channel seed data');

-- DOWN
DELETE FROM comms_channel_member_access WHERE id LIKE 'ma-%';
DELETE FROM comms_channel_accounts WHERE id LIKE 'ca-%';
DELETE FROM comms_channel_devices WHERE id LIKE 'cd-%';
DELETE FROM comms_channel_health WHERE channel_id IN ('whatsapp_family','whatsapp_james','whatsapp_laura','gmail_personal','gmail_laura','imessage','siri_shortcuts','webconsole','skylight_calendar');
DELETE FROM comms_channels WHERE id IN ('whatsapp_family','whatsapp_james','whatsapp_laura','gmail_personal','gmail_laura','imessage','siri_shortcuts','webconsole','skylight_calendar');
DELETE FROM comms_accounts WHERE id LIKE 'acct-%';
DELETE FROM comms_devices WHERE id LIKE 'device-%';
