-- Migration 010: Seed comms batch window config
-- Provides default batch window times for morning/midday/evening processing

INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('comms_batch_morning_start', '08:00', 'Morning batch window start time');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('comms_batch_morning_end', '09:00', 'Morning batch window end time');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('comms_batch_midday_start', '12:00', 'Midday batch window start time');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('comms_batch_midday_end', '13:00', 'Midday batch window end time');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('comms_batch_evening_start', '18:00', 'Evening batch window start time');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('comms_batch_evening_end', '19:00', 'Evening batch window end time');

-- DOWN
DELETE FROM pib_config WHERE key LIKE 'comms_batch_%';
