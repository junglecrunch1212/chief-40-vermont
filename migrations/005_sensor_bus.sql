-- Migration 005: Sensor Bus & Environmental Intelligence
-- Adds pib_sensor_config, pib_sensor_readings, pib_sensor_alerts tables
-- for the sensor bus architecture (unidirectional context signals).

-- ═══ SENSOR CONFIGURATION ═══
-- Every possible sensor has a row, whether active or not.
-- This is the "toggles and settings" layer.

CREATE TABLE IF NOT EXISTS pib_sensor_config (
    sensor_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,

    -- Activation
    enabled INTEGER NOT NULL DEFAULT 0,
    enabled_for_members TEXT DEFAULT '[]',
    requires_setup INTEGER DEFAULT 0,
    setup_complete INTEGER DEFAULT 0,
    setup_instructions TEXT,

    -- Polling
    poll_interval_minutes INTEGER NOT NULL DEFAULT 15,
    last_poll_at TEXT,
    next_poll_at TEXT,

    -- Privacy (Gene 2 vocabulary)
    privacy TEXT NOT NULL DEFAULT 'full'
        CHECK (privacy IN ('full', 'privileged', 'redacted')),

    -- Health
    status TEXT DEFAULT 'unconfigured'
        CHECK (status IN ('unconfigured', 'healthy', 'degraded', 'error', 'disabled')),
    consecutive_failures INTEGER DEFAULT 0,
    last_error TEXT,
    last_successful_read TEXT,

    -- Source details
    source_type TEXT,
    source_config TEXT DEFAULT '{}',
    required_permissions TEXT DEFAULT '[]',

    -- Metadata
    layer INTEGER DEFAULT 2,
    phase TEXT,
    description TEXT,

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);


-- ═══ SENSOR READINGS ═══
-- Universal storage for ALL sensor data. Append-only.
-- Consumers query: latest reading per sensor_id where age < TTL.

CREATE TABLE IF NOT EXISTS pib_sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id TEXT NOT NULL REFERENCES pib_sensor_config(sensor_id),
    reading_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,

    -- The actual data (sensor-specific JSON)
    value TEXT NOT NULL,

    -- Context
    member_id TEXT,
    location_id TEXT,

    -- Quality
    confidence TEXT DEFAULT 'high'
        CHECK (confidence IN ('high', 'medium', 'low', 'stale')),
    ttl_minutes INTEGER NOT NULL,
    expires_at TEXT NOT NULL,

    -- Dedup
    idempotency_key TEXT NOT NULL,

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_sensor_latest ON pib_sensor_readings(sensor_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_type ON pib_sensor_readings(reading_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_member ON pib_sensor_readings(member_id, reading_type, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_expires ON pib_sensor_readings(expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sensor_idemp ON pib_sensor_readings(idempotency_key);


-- ═══ SENSOR ALERTS ═══
-- Threshold-based alerts that trigger proactive suggestions.

CREATE TABLE IF NOT EXISTS pib_sensor_alerts (
    id TEXT PRIMARY KEY,
    sensor_id TEXT NOT NULL REFERENCES pib_sensor_config(sensor_id),
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL
        CHECK (severity IN ('info', 'warning', 'critical')),
    title TEXT NOT NULL,
    description TEXT,
    member_ids TEXT DEFAULT '[]',
    reading_id INTEGER REFERENCES pib_sensor_readings(id),

    -- Lifecycle
    status TEXT DEFAULT 'active'
        CHECK (status IN ('active', 'acknowledged', 'resolved', 'expired')),
    acknowledged_by TEXT,
    resolved_at TEXT,
    expires_at TEXT,

    -- Action
    suggested_action TEXT,
    triggered_task_id TEXT,

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_alert_status ON pib_sensor_alerts(status, severity);


-- Record migration
INSERT INTO meta_schema_version (version, description) VALUES (5, 'Sensor bus: config, readings, alerts tables');

-- DOWN
DROP TABLE IF EXISTS pib_sensor_alerts;
DROP TABLE IF EXISTS pib_sensor_readings;
DROP TABLE IF EXISTS pib_sensor_config;
DELETE FROM meta_schema_version WHERE version = 5;
