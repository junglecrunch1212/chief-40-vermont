-- ═══════════════════════════════════════════════════════════════
-- Migration 007: Project Domain
-- Autonomous project planning & execution engine
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS proj_projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    brief TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planning'
        CHECK (status IN ('planning','pending_approval','approved','active','paused','blocked','completed','dismissed')),
    requested_by TEXT NOT NULL REFERENCES common_members(id),
    approved_by TEXT REFERENCES common_members(id),
    approved_at TEXT,
    risk_financial TEXT NOT NULL DEFAULT 'low' CHECK (risk_financial IN ('none','low','medium','high')),
    risk_reputational TEXT NOT NULL DEFAULT 'low' CHECK (risk_reputational IN ('none','low','medium','high')),
    risk_technical TEXT NOT NULL DEFAULT 'none' CHECK (risk_technical IN ('none','low','medium','high')),
    budget_limit_cents INTEGER,
    budget_spent_cents INTEGER DEFAULT 0,
    budget_per_action_limit_cents INTEGER DEFAULT 5000,
    can_email_strangers INTEGER DEFAULT 0,
    can_sms_strangers INTEGER DEFAULT 0,
    can_call_strangers INTEGER DEFAULT 0,
    can_create_accounts INTEGER DEFAULT 0,
    can_share_address INTEGER DEFAULT 0,
    can_share_phone INTEGER DEFAULT 0,
    can_spend INTEGER DEFAULT 0,
    visible_to TEXT DEFAULT 'all',
    depends_on_project TEXT REFERENCES proj_projects(id),
    estimated_duration_days INTEGER,
    goal_ref TEXT REFERENCES ops_goals(id),
    life_phase TEXT,
    notes TEXT,
    plan_json TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_proj_active ON proj_projects(status) WHERE status IN ('active','blocked','paused');

CREATE TABLE IF NOT EXISTS proj_phases (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES proj_projects(id),
    phase_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','completed','skipped')),
    started_at TEXT,
    completed_at TEXT,
    UNIQUE(project_id, phase_number)
);
CREATE INDEX IF NOT EXISTS idx_phase_project ON proj_phases(project_id);

CREATE TABLE IF NOT EXISTS proj_steps (
    id TEXT PRIMARY KEY,
    phase_id TEXT NOT NULL REFERENCES proj_phases(id),
    project_id TEXT NOT NULL REFERENCES proj_projects(id),
    step_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    step_type TEXT NOT NULL DEFAULT 'auto' CHECK (step_type IN ('auto','draft','gate','human','wait')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','ready','active','waiting','completed','skipped','failed')),
    executor TEXT NOT NULL DEFAULT 'pib' CHECK (executor IN ('pib','james','laura','external')),
    tool_hint TEXT,
    depends_on TEXT,
    task_ref TEXT REFERENCES ops_tasks(id),
    comms_ref TEXT,
    item_ref TEXT REFERENCES ops_items(id),
    result_summary TEXT,
    result_data TEXT,
    estimated_minutes INTEGER,
    started_at TEXT,
    completed_at TEXT,
    due_date TEXT CHECK (due_date IS NULL OR date(due_date) IS NOT NULL),
    UNIQUE(phase_id, step_number)
);
CREATE INDEX IF NOT EXISTS idx_step_project ON proj_steps(project_id);
CREATE INDEX IF NOT EXISTS idx_step_active ON proj_steps(status) WHERE status IN ('ready','active','waiting');

CREATE TABLE IF NOT EXISTS proj_gates (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES proj_projects(id),
    after_phase_id TEXT REFERENCES proj_phases(id),
    after_step_id TEXT REFERENCES proj_steps(id),
    behavior TEXT NOT NULL DEFAULT 'confirm' CHECK (behavior IN ('none','inform','confirm','approve')),
    gate_type TEXT NOT NULL DEFAULT 'approval' CHECK (gate_type IN ('approval','decision','budget','permission','final')),
    title TEXT NOT NULL,
    description TEXT,
    options_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','waiting','approved','rejected','expired')),
    decided_by TEXT REFERENCES common_members(id),
    decided_at TEXT,
    decision_notes TEXT,
    decision_choice TEXT,
    auto_expire_hours INTEGER DEFAULT 168,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_gate_pending ON proj_gates(status) WHERE status IN ('pending','waiting');

CREATE TABLE IF NOT EXISTS proj_research (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES proj_projects(id),
    step_id TEXT REFERENCES proj_steps(id),
    research_type TEXT NOT NULL CHECK (research_type IN ('web_result','comparison','quote','document','contact','note')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_url TEXT,
    source_name TEXT,
    relevance_score REAL DEFAULT 1.0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_research_project ON proj_research(project_id);

CREATE VIRTUAL TABLE IF NOT EXISTS proj_research_fts USING fts5(
    title, content, source_name, content=proj_research, content_rowid=rowid
);
CREATE TRIGGER IF NOT EXISTS proj_research_ai AFTER INSERT ON proj_research BEGIN
    INSERT INTO proj_research_fts(rowid, title, content, source_name) VALUES (new.rowid, new.title, new.content, new.source_name);
END;
CREATE TRIGGER IF NOT EXISTS proj_research_ad AFTER DELETE ON proj_research BEGIN
    INSERT INTO proj_research_fts(proj_research_fts, rowid, title, content, source_name) VALUES ('delete', old.rowid, old.title, old.content, old.source_name);
END;
CREATE TRIGGER IF NOT EXISTS proj_research_au AFTER UPDATE ON proj_research BEGIN
    INSERT INTO proj_research_fts(proj_research_fts, rowid, title, content, source_name) VALUES ('delete', old.rowid, old.title, old.content, old.source_name);
    INSERT INTO proj_research_fts(rowid, title, content, source_name) VALUES (new.rowid, new.title, new.content, new.source_name);
END;

-- ═══════════════════════════════════════════════════════════════
-- ALTER TABLE: add project references to ops_tasks
-- ═══════════════════════════════════════════════════════════════

ALTER TABLE ops_tasks ADD COLUMN project_ref TEXT REFERENCES proj_projects(id);
ALTER TABLE ops_tasks ADD COLUMN project_step_ref TEXT REFERENCES proj_steps(id);

-- ═══════════════════════════════════════════════════════════════
-- Config seeds
-- ═══════════════════════════════════════════════════════════════

INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('project_engine_enabled', '1', 'Enable project execution engine');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('project_advance_interval_minutes', '5', 'Minutes between project advancement cycles');
INSERT OR IGNORE INTO pib_config (key, value, description) VALUES
    ('project_max_active', '5', 'Maximum concurrent active projects');

INSERT INTO meta_schema_version (version, description) VALUES (7, 'Project domain');

-- DOWN
DROP TRIGGER IF EXISTS proj_research_au;
DROP TRIGGER IF EXISTS proj_research_ad;
DROP TRIGGER IF EXISTS proj_research_ai;
DROP TABLE IF EXISTS proj_research_fts;
DROP TABLE IF EXISTS proj_research;
DROP TABLE IF EXISTS proj_gates;
DROP TABLE IF EXISTS proj_steps;
DROP TABLE IF EXISTS proj_phases;
DROP TABLE IF EXISTS proj_projects;
-- ALTER TABLE cannot drop columns in SQLite; project_ref/project_step_ref are nullable so harmless
