-- Migration 007: FTS5 sync triggers for ops_tasks_fts, ops_items_fts, mem_long_term_fts
-- Pattern: content-sync protocol (INSERT new, DELETE old via 'delete' command)
-- Copied from working cap_captures_fts triggers in 006_capture_domain.sql

-- ═══════════════════════════════════════════════════════════════
-- ops_tasks_fts triggers (title, notes, micro_script)
-- ═══════════════════════════════════════════════════════════════

CREATE TRIGGER IF NOT EXISTS ops_tasks_fts_insert AFTER INSERT ON ops_tasks BEGIN
    INSERT INTO ops_tasks_fts(rowid, title, notes, micro_script)
    VALUES (NEW.rowid, NEW.title, NEW.notes, NEW.micro_script);
END;

CREATE TRIGGER IF NOT EXISTS ops_tasks_fts_update AFTER UPDATE ON ops_tasks BEGIN
    INSERT INTO ops_tasks_fts(ops_tasks_fts, rowid, title, notes, micro_script)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.notes, OLD.micro_script);
    INSERT INTO ops_tasks_fts(rowid, title, notes, micro_script)
    VALUES (NEW.rowid, NEW.title, NEW.notes, NEW.micro_script);
END;

CREATE TRIGGER IF NOT EXISTS ops_tasks_fts_delete AFTER DELETE ON ops_tasks BEGIN
    INSERT INTO ops_tasks_fts(ops_tasks_fts, rowid, title, notes, micro_script)
    VALUES ('delete', OLD.rowid, OLD.title, OLD.notes, OLD.micro_script);
END;

-- ═══════════════════════════════════════════════════════════════
-- ops_items_fts triggers (name, notes, category, type)
-- ═══════════════════════════════════════════════════════════════

CREATE TRIGGER IF NOT EXISTS ops_items_fts_insert AFTER INSERT ON ops_items BEGIN
    INSERT INTO ops_items_fts(rowid, name, notes, category, type)
    VALUES (NEW.rowid, NEW.name, NEW.notes, NEW.category, NEW.type);
END;

CREATE TRIGGER IF NOT EXISTS ops_items_fts_update AFTER UPDATE ON ops_items BEGIN
    INSERT INTO ops_items_fts(ops_items_fts, rowid, name, notes, category, type)
    VALUES ('delete', OLD.rowid, OLD.name, OLD.notes, OLD.category, OLD.type);
    INSERT INTO ops_items_fts(rowid, name, notes, category, type)
    VALUES (NEW.rowid, NEW.name, NEW.notes, NEW.category, NEW.type);
END;

CREATE TRIGGER IF NOT EXISTS ops_items_fts_delete AFTER DELETE ON ops_items BEGIN
    INSERT INTO ops_items_fts(ops_items_fts, rowid, name, notes, category, type)
    VALUES ('delete', OLD.rowid, OLD.name, OLD.notes, OLD.category, OLD.type);
END;

-- ═══════════════════════════════════════════════════════════════
-- mem_long_term_fts triggers (content, category, domain)
-- ═══════════════════════════════════════════════════════════════

CREATE TRIGGER IF NOT EXISTS mem_long_term_fts_insert AFTER INSERT ON mem_long_term BEGIN
    INSERT INTO mem_long_term_fts(rowid, content, category, domain)
    VALUES (NEW.id, NEW.content, NEW.category, NEW.domain);
END;

CREATE TRIGGER IF NOT EXISTS mem_long_term_fts_update AFTER UPDATE ON mem_long_term BEGIN
    INSERT INTO mem_long_term_fts(mem_long_term_fts, rowid, content, category, domain)
    VALUES ('delete', OLD.id, OLD.content, OLD.category, OLD.domain);
    INSERT INTO mem_long_term_fts(rowid, content, category, domain)
    VALUES (NEW.id, NEW.content, NEW.category, NEW.domain);
END;

CREATE TRIGGER IF NOT EXISTS mem_long_term_fts_delete AFTER DELETE ON mem_long_term BEGIN
    INSERT INTO mem_long_term_fts(mem_long_term_fts, rowid, content, category, domain)
    VALUES ('delete', OLD.id, OLD.content, OLD.category, OLD.domain);
END;

-- DOWN
DROP TRIGGER IF EXISTS ops_tasks_fts_insert;
DROP TRIGGER IF EXISTS ops_tasks_fts_update;
DROP TRIGGER IF EXISTS ops_tasks_fts_delete;
DROP TRIGGER IF EXISTS ops_items_fts_insert;
DROP TRIGGER IF EXISTS ops_items_fts_update;
DROP TRIGGER IF EXISTS ops_items_fts_delete;
DROP TRIGGER IF EXISTS mem_long_term_fts_insert;
DROP TRIGGER IF EXISTS mem_long_term_fts_update;
DROP TRIGGER IF EXISTS mem_long_term_fts_delete;
