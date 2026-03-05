-- Migration 016: Sensor Readings Enhancements
-- Adds classification column and privacy fence index to pib_sensor_readings (created in 005)
-- Auto-classification: m-laura data is marked privileged, privacy fence enforces read isolation

-- Add classification column (not in 005's schema)
ALTER TABLE pib_sensor_readings ADD COLUMN classification TEXT DEFAULT 'normal';

-- Privacy fence index: efficient filtering for classification
CREATE INDEX IF NOT EXISTS idx_sensor_readings_classification
    ON pib_sensor_readings(classification, member_id);
