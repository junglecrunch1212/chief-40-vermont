-- Migration 011: FTS5 index for ops_comms
-- Full-text search on comms text, sender, summary fields

CREATE VIRTUAL TABLE IF NOT EXISTS comms_fts USING fts5(
    summary, body_snippet, subject, from_addr,
    content='ops_comms', content_rowid='rowid'
);

-- FTS5 sync triggers
CREATE TRIGGER IF NOT EXISTS comms_fts_insert AFTER INSERT ON ops_comms BEGIN
    INSERT INTO comms_fts(rowid, summary, body_snippet, subject, from_addr)
    VALUES (NEW.rowid, NEW.summary, NEW.body_snippet, NEW.subject, NEW.from_addr);
END;

CREATE TRIGGER IF NOT EXISTS comms_fts_update AFTER UPDATE ON ops_comms BEGIN
    INSERT INTO comms_fts(comms_fts, rowid, summary, body_snippet, subject, from_addr)
    VALUES ('delete', OLD.rowid, OLD.summary, OLD.body_snippet, OLD.subject, OLD.from_addr);
    INSERT INTO comms_fts(rowid, summary, body_snippet, subject, from_addr)
    VALUES (NEW.rowid, NEW.summary, NEW.body_snippet, NEW.subject, NEW.from_addr);
END;

CREATE TRIGGER IF NOT EXISTS comms_fts_delete AFTER DELETE ON ops_comms BEGIN
    INSERT INTO comms_fts(comms_fts, rowid, summary, body_snippet, subject, from_addr)
    VALUES ('delete', OLD.rowid, OLD.summary, OLD.body_snippet, OLD.subject, OLD.from_addr);
END;

-- DOWN
DROP TRIGGER IF EXISTS comms_fts_insert;
DROP TRIGGER IF EXISTS comms_fts_update;
DROP TRIGGER IF EXISTS comms_fts_delete;
DROP TABLE IF EXISTS comms_fts;
