-- Migration 016: Sensor Readings Table
-- Stores inbound sensor data from personal Mac Minis (health, location, focus, battery, homekit)
-- Auto-classification: m-laura data is marked privileged, privacy fence enforces read isolation

CREATE TABLE IF NOT EXISTS pib_sensor_readings (
    id TEXT PRIMARY KEY,
    sensor_id TEXT NOT NULL,           -- Source identifier (e.g., 'apple_health_sleep', 'location', 'homekit')
    reading_type TEXT NOT NULL,        -- Reading type for querying (sleep, steps, location, focus, etc.)
    member_id TEXT NOT NULL,           -- Which household member owns this data
    timestamp TEXT NOT NULL,           -- When the reading was captured (ISO 8601)
    value TEXT,                        -- JSON blob of the actual sensor data
    classification TEXT DEFAULT 'normal',  -- 'normal' or 'privileged' (auto-set for m-laura)
    confidence REAL DEFAULT 1.0,       -- Confidence score (0.0-1.0)
    idempotency_key TEXT UNIQUE,       -- Prevents duplicate ingestion
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Query patterns:
-- 1. Get recent readings for a member (dashboard, context)
-- 2. Get readings by type (sleep quality over time)
-- 3. Privacy fence: exclude privileged unless member matches

CREATE INDEX IF NOT EXISTS idx_sensor_readings_member_time
    ON pib_sensor_readings(member_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_type_time
    ON pib_sensor_readings(reading_type, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_idempotency
    ON pib_sensor_readings(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- Privacy fence index: efficient filtering for classification
CREATE INDEX IF NOT EXISTS idx_sensor_readings_classification
    ON pib_sensor_readings(classification, member_id);
