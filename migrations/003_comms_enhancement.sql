-- Migration 003: Comms Domain Enhancement
-- Date: 2026-03-01
-- Description: Adds batch window, extraction, draft, snooze, and visibility
--   columns to ops_comms for the full Comms Domain (Section 14).
--   Also adds comms config seeds and source classifications.

-- ============================================================================
-- up_sql
-- ============================================================================

-- New columns on ops_comms for Comms Domain
ALTER TABLE ops_comms ADD COLUMN comm_type TEXT;
ALTER TABLE ops_comms ADD COLUMN batch_window TEXT;
ALTER TABLE ops_comms ADD COLUMN batch_date TEXT;
ALTER TABLE ops_comms ADD COLUMN extraction_status TEXT DEFAULT 'none';
ALTER TABLE ops_comms ADD COLUMN extracted_items TEXT;
ALTER TABLE ops_comms ADD COLUMN extraction_confidence REAL;
ALTER TABLE ops_comms ADD COLUMN draft_response TEXT;
ALTER TABLE ops_comms ADD COLUMN draft_status TEXT DEFAULT 'none';
ALTER TABLE ops_comms ADD COLUMN draft_voice_profile_id TEXT;
ALTER TABLE ops_comms ADD COLUMN snoozed_until TEXT;
ALTER TABLE ops_comms ADD COLUMN visibility TEXT DEFAULT 'normal';
ALTER TABLE ops_comms ADD COLUMN source_classification TEXT;

-- Inbox query: non-archived, ordered by urgency + date
CREATE INDEX IF NOT EXISTS idx_comms_inbox
    ON ops_comms(visibility, needs_response, response_urgency, date);

-- Batch queries: find comms for a given batch window on a date
CREATE INDEX IF NOT EXISTS idx_comms_batch
    ON ops_comms(batch_date, batch_window, visibility);

-- Draft management: find pending/sending drafts
CREATE INDEX IF NOT EXISTS idx_comms_drafts
    ON ops_comms(draft_status) WHERE draft_status NOT IN ('none');

-- Extraction pipeline: find comms awaiting extraction
CREATE INDEX IF NOT EXISTS idx_comms_extraction
    ON ops_comms(extraction_status) WHERE extraction_status = 'pending';

-- Source classifications for new comms channels
INSERT OR IGNORE INTO common_source_classifications (id, source_type, source_identifier, display_name, relevance, ownership, privacy, authority)
VALUES
    ('src-whatsapp', 'adapter', 'whatsapp', 'WhatsApp', 'awareness', 'member', 'full', 'hybrid'),
    ('src-outlook-laura', 'adapter', 'outlook_laura_work', 'Outlook (Laura Work)', 'blocks_member', 'member', 'privileged', 'human_managed'),
    ('src-apple-voice', 'adapter', 'apple_voice_notes', 'Apple Voice Notes', 'awareness', 'member', 'full', 'hybrid'),
    ('src-manual-capture', 'adapter', 'manual_capture', 'Manual Capture', 'awareness', 'shared', 'full', 'human_managed');

-- Comms config keys
INSERT OR IGNORE INTO pib_config (key, value, description)
VALUES
    ('comms_batch_morning_start', '08:00', 'Morning batch window start (HH:MM ET)'),
    ('comms_batch_morning_end', '09:00', 'Morning batch window end'),
    ('comms_batch_midday_start', '12:00', 'Midday batch window start'),
    ('comms_batch_midday_end', '13:00', 'Midday batch window end'),
    ('comms_batch_evening_start', '19:00', 'Evening batch window start'),
    ('comms_batch_evening_end', '20:00', 'Evening batch window end'),
    ('comms_extraction_enabled', '1', 'Enable async extraction of tasks/events from comms'),
    ('comms_extraction_min_confidence', '0.7', 'Minimum confidence for extraction proposals'),
    ('comms_drafting_enabled', '0', 'Enable CoS draft generation (off until voice profile matures)'),
    ('comms_urgent_bypass_batch', '1', 'Urgent comms bypass batch windows'),
    ('voice_profile_rebuild_day', 'sunday', 'Day of week to rebuild voice profiles'),
    ('voice_profile_min_samples', '15', 'Minimum samples before profile is usable'),
    ('voice_profile_min_person', '5', 'Minimum samples for a per-person profile'),
    ('voice_notes_transcription_engine', 'whisper_api', 'whisper_api or whisper_local');

-- Register migration
INSERT OR IGNORE INTO meta_migrations (version, name, up_sql, down_sql, applied_at, checksum)
VALUES (3, '003_comms_enhancement', 'migrations/003_comms_enhancement.sql', 'See down_sql section in file', strftime('%Y-%m-%dT%H:%M:%SZ','now'), 'pending');

-- ============================================================================
-- down_sql (SQLite table rebuild pattern for column removal)
-- ============================================================================

-- To roll back: rebuild ops_comms without the new columns
-- DROP INDEX IF EXISTS idx_comms_inbox;
-- DROP INDEX IF EXISTS idx_comms_batch;
-- DROP INDEX IF EXISTS idx_comms_drafts;
-- DROP INDEX IF EXISTS idx_comms_extraction;
--
-- CREATE TABLE ops_comms_backup AS SELECT
--     id, date, channel, direction, from_addr, to_addr, participants,
--     member_id, item_ref, task_ref, thread_id, subject,
--     summary, body_snippet, needs_response, response_urgency,
--     suggested_action, auto_handled, has_attachment, sent_as,
--     responded_at, outcome, followup_date, followup_action,
--     created_by, created_at
-- FROM ops_comms;
--
-- DROP TABLE ops_comms;
-- ALTER TABLE ops_comms_backup RENAME TO ops_comms;
-- (then recreate original indexes)
--
-- DELETE FROM common_source_classifications WHERE source IN ('whatsapp','outlook_laura_work','apple_voice_notes','manual_capture');
-- DELETE FROM pib_config WHERE key LIKE 'comms_%' OR key LIKE 'voice_%';
-- DELETE FROM meta_migrations WHERE id = 3;
