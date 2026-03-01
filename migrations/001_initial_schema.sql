-- PIB v5 Initial Schema
-- All tables for the household Chief-of-Staff system
-- SQLite 3.45+ with WAL mode, FTS5 enabled

-- ═══════════════════════════════════════════════════════════════
-- meta_* — System metadata, migrations, discovery
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS meta_schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    description TEXT
);

CREATE TABLE IF NOT EXISTS meta_discovery_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    discovered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    raw_report TEXT NOT NULL,
    proposed_config TEXT,
    confirmed INTEGER DEFAULT 0,
    confirmed_by TEXT,
    confirmed_at TEXT,
    applied INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    up_sql TEXT NOT NULL,
    down_sql TEXT NOT NULL,
    applied_at TEXT,
    rolled_back_at TEXT,
    checksum TEXT NOT NULL
);

-- ═══════════════════════════════════════════════════════════════
-- pib_config — Runtime config: model IDs, thresholds, feature flags
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS pib_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_by TEXT DEFAULT 'seed'
);

-- ═══════════════════════════════════════════════════════════════
-- common_* — Shared infrastructure
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS common_members (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('parent','child','coparent','grandparent','nanny','babysitter','other')),
    is_household_member INTEGER NOT NULL DEFAULT 1,
    is_adult INTEGER NOT NULL DEFAULT 1,
    can_be_assigned_tasks INTEGER DEFAULT 0,
    can_receive_messages INTEGER DEFAULT 0,
    phone TEXT, email TEXT, imessage_handle TEXT,
    preferred_channel TEXT CHECK (preferred_channel IS NULL OR preferred_channel IN ('imessage','sms','email','phone')),
    view_mode TEXT DEFAULT 'standard' CHECK (view_mode IN ('carousel','compressed','standard','child','entity')),
    digest_mode TEXT DEFAULT 'full' CHECK (digest_mode IN ('full','compressed','none')),
    energy_markers TEXT DEFAULT '{}',
    medication_config TEXT DEFAULT '{}',
    velocity_cap INTEGER DEFAULT 20,
    capabilities TEXT DEFAULT '{}',
    school TEXT, age INTEGER,
    date_of_birth TEXT CHECK (date_of_birth IS NULL OR date(date_of_birth) IS NOT NULL),
    expected_arrival TEXT CHECK (expected_arrival IS NULL OR date(expected_arrival) IS NOT NULL),
    schedule_profile TEXT DEFAULT '{}',
    household_duties TEXT DEFAULT '{}',
    notes TEXT, active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS common_source_classifications (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_identifier TEXT NOT NULL,
    display_name TEXT,
    relevance TEXT NOT NULL CHECK (relevance IN (
        'blocks_member','blocks_household','blocks_assignee',
        'custody_state','asset_availability','awareness','awareness_external')),
    ownership TEXT NOT NULL CHECK (ownership IN ('member','shared','external')),
    privacy TEXT NOT NULL CHECK (privacy IN ('full','privileged','redacted')),
    authority TEXT NOT NULL CHECK (authority IN ('system_managed','human_managed','hybrid')),
    for_member_id TEXT REFERENCES common_members(id),
    discovered_at TEXT, proposed_at TEXT, confirmed_at TEXT, confirmed_by TEXT,
    active INTEGER DEFAULT 1,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS common_locations (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, address TEXT,
    lat REAL, lng REAL, travel_times TEXT DEFAULT '{}', metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS common_custody_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id TEXT NOT NULL REFERENCES common_members(id),
    schedule_type TEXT NOT NULL CHECK (schedule_type IN (
        'alternating_weeks','alternating_weekends_midweek',
        'every_other_weekend','primary_with_visitation','custom')),
    anchor_date TEXT NOT NULL CHECK (date(anchor_date) IS NOT NULL),
    anchor_parent TEXT NOT NULL REFERENCES common_members(id),
    other_parent TEXT NOT NULL REFERENCES common_members(id),
    transition_day TEXT, transition_time TEXT,
    transition_location_id TEXT REFERENCES common_locations(id),
    midweek_visit_enabled INTEGER DEFAULT 0,
    midweek_visit_day TEXT, midweek_visit_start TEXT, midweek_visit_end TEXT,
    midweek_visit_parent TEXT REFERENCES common_members(id),
    holiday_overrides TEXT DEFAULT '[]',
    active INTEGER DEFAULT 1,
    effective_from TEXT NOT NULL CHECK (date(effective_from) IS NOT NULL),
    effective_until TEXT CHECK (effective_until IS NULL OR date(effective_until) IS NOT NULL),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_custody_active ON common_custody_configs(child_id) WHERE active = 1;

CREATE TABLE IF NOT EXISTS common_life_phases (
    id TEXT PRIMARY KEY, name TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('active','pending','completed')),
    start_date TEXT CHECK (start_date IS NULL OR date(start_date) IS NOT NULL),
    end_date TEXT CHECK (end_date IS NULL OR date(end_date) IS NOT NULL),
    description TEXT, overrides TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS common_household_config (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    config TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS common_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
    entity_id TEXT, old_values TEXT, new_values TEXT,
    actor TEXT NOT NULL DEFAULT 'system',
    source TEXT DEFAULT 'unknown', metadata TEXT DEFAULT '{}'
);
CREATE INDEX idx_audit_ts ON common_audit_log(ts);
CREATE INDEX idx_audit_entity ON common_audit_log(table_name, entity_id);

CREATE TABLE IF NOT EXISTS common_idempotency_keys (
    key_hash TEXT PRIMARY KEY, source TEXT NOT NULL, original_id TEXT,
    processed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    result_summary TEXT
);

CREATE TABLE IF NOT EXISTS common_id_sequences (
    prefix TEXT PRIMARY KEY,
    next_val INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS common_dead_letter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    failed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    operation TEXT NOT NULL, error_message TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0, max_retries INTEGER DEFAULT 3,
    next_retry_at TEXT, resolved INTEGER DEFAULT 0,
    resolved_at TEXT, resolved_by TEXT
);
CREATE INDEX idx_dead_letter_pending ON common_dead_letter(next_retry_at) WHERE resolved = 0;

CREATE TABLE IF NOT EXISTS common_undo_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT,
    operation TEXT NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
    table_name TEXT NOT NULL, entity_id TEXT NOT NULL,
    restore_data TEXT, actor TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    undone INTEGER DEFAULT 0, undone_at TEXT,
    expires_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now', '+24 hours'))
);
CREATE INDEX idx_undo_recent ON common_undo_log(created_at DESC)
    WHERE undone = 0 AND expires_at > strftime('%Y-%m-%dT%H:%M:%SZ','now');

-- ═══════════════════════════════════════════════════════════════
-- ops_* — Operations: tasks, goals, items, recurring, comms, lists
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ops_tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'inbox'
        CHECK (status IN ('inbox','next','in_progress','waiting_on','deferred','done','dismissed')),
    assignee TEXT NOT NULL REFERENCES common_members(id),
    domain TEXT NOT NULL DEFAULT 'tasks',
    item_type TEXT DEFAULT 'task'
        CHECK (item_type IN ('task','purchase','appointment','research','decision',
               'chore','maintenance','goal_milestone')),
    due_date TEXT CHECK (due_date IS NULL OR date(due_date) IS NOT NULL),
    scheduled_date TEXT CHECK (scheduled_date IS NULL OR date(scheduled_date) IS NOT NULL),
    scheduled_time TEXT,
    energy TEXT CHECK (energy IS NULL OR energy IN ('low','medium','high')),
    effort TEXT CHECK (effort IS NULL OR effort IN ('tiny','small','medium','large')),
    micro_script TEXT NOT NULL DEFAULT '',
    item_ref TEXT REFERENCES ops_items(id),
    recurring_ref TEXT REFERENCES ops_recurring(id),
    goal_ref TEXT REFERENCES ops_goals(id),
    life_event TEXT,
    requires TEXT,
    location_id TEXT REFERENCES common_locations(id),
    location_text TEXT,
    waiting_on TEXT, waiting_since TEXT,
    decision_options TEXT,
    decision_deadline TEXT CHECK (decision_deadline IS NULL OR date(decision_deadline) IS NOT NULL),
    decision_maker TEXT REFERENCES common_members(id),
    created_by TEXT NOT NULL DEFAULT 'system',
    source_system TEXT DEFAULT 'manual',
    confidence REAL DEFAULT 1.0,
    source_event_id TEXT,
    points INTEGER DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    completed_at TEXT, completed_by TEXT
);
CREATE INDEX idx_tasks_active ON ops_tasks(status, assignee) WHERE status NOT IN ('done','dismissed');
CREATE INDEX idx_tasks_due ON ops_tasks(due_date) WHERE due_date IS NOT NULL AND status NOT IN ('done','dismissed');
CREATE INDEX idx_tasks_overdue ON ops_tasks(due_date) WHERE due_date IS NOT NULL AND status NOT IN ('done','dismissed','deferred');

CREATE TABLE IF NOT EXISTS ops_goals (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, domain TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active','on_track','at_risk','behind','completed','abandoned')),
    owner TEXT REFERENCES common_members(id),
    target_date TEXT CHECK (target_date IS NULL OR date(target_date) IS NOT NULL),
    progress_metric TEXT, progress_current TEXT, progress_target TEXT,
    life_phase TEXT, notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS ops_items (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
    category TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','archived')),
    domain TEXT,
    phone TEXT, phone_alt TEXT, email TEXT, email_alt TEXT,
    imessage_handle TEXT, preferred_channel TEXT,
    contact_group TEXT, relationship_tier TEXT, our_relationship TEXT,
    desired_contact_freq TEXT,
    last_meaningful_contact TEXT CHECK (last_meaningful_contact IS NULL OR date(last_meaningful_contact) IS NOT NULL),
    last_hosted_us TEXT, last_we_hosted TEXT, hosting_balance INTEGER DEFAULT 0,
    gift_prefs TEXT, last_gift_given TEXT, last_gift_received TEXT,
    cos_can_contact INTEGER DEFAULT 0,
    outbound_identity TEXT DEFAULT 'ask', outbound_channel TEXT DEFAULT 'ask',
    reliability TEXT,
    brand TEXT, model TEXT, serial_number TEXT,
    purchase_date TEXT, warranty_exp TEXT,
    monthly_cost REAL, annual_cost REAL,
    location_id TEXT REFERENCES common_locations(id), address TEXT,
    metadata TEXT DEFAULT '{}', notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_items_type ON ops_items(type);
CREATE INDEX idx_items_email ON ops_items(email) WHERE email IS NOT NULL;
CREATE INDEX idx_items_phone ON ops_items(phone) WHERE phone IS NOT NULL;

CREATE TABLE IF NOT EXISTS ops_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blocked_task_id TEXT NOT NULL REFERENCES ops_tasks(id) ON DELETE CASCADE,
    blocking_task_id TEXT NOT NULL REFERENCES ops_tasks(id) ON DELETE CASCADE,
    dependency_type TEXT DEFAULT 'blocks' CHECK (dependency_type IN ('blocks','informs','requires')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(blocked_task_id, blocking_task_id)
);

CREATE TABLE IF NOT EXISTS ops_recurring (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, type TEXT NOT NULL,
    frequency TEXT NOT NULL, days TEXT,
    assignee TEXT NOT NULL REFERENCES common_members(id),
    for_member TEXT REFERENCES common_members(id),
    domain TEXT NOT NULL,
    next_due TEXT NOT NULL CHECK (date(next_due) IS NOT NULL),
    lead_days INTEGER DEFAULT 0, last_spawned TEXT,
    item_ref TEXT REFERENCES ops_items(id),
    goal_ref TEXT REFERENCES ops_goals(id),
    amount REAL, auto_pay INTEGER DEFAULT 0,
    effort TEXT DEFAULT 'small', energy TEXT DEFAULT 'low',
    micro_script_template TEXT NOT NULL DEFAULT '',
    points INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1, notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS ops_comms (
    id TEXT PRIMARY KEY, date TEXT NOT NULL,
    channel TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('inbound','outbound')),
    from_addr TEXT, to_addr TEXT, participants TEXT,
    member_id TEXT REFERENCES common_members(id),
    item_ref TEXT REFERENCES ops_items(id),
    task_ref TEXT REFERENCES ops_tasks(id),
    thread_id TEXT, subject TEXT,
    summary TEXT NOT NULL, body_snippet TEXT,
    needs_response INTEGER DEFAULT 0, response_urgency TEXT,
    suggested_action TEXT, auto_handled INTEGER DEFAULT 0,
    has_attachment INTEGER DEFAULT 0, sent_as TEXT,
    responded_at TEXT, outcome TEXT DEFAULT 'pending',
    followup_date TEXT, followup_action TEXT,
    created_by TEXT DEFAULT 'pib_agent',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_comms_date ON ops_comms(date);
CREATE INDEX idx_comms_pending ON ops_comms(needs_response) WHERE needs_response = 1;

CREATE TABLE IF NOT EXISTS ops_lists (
    id TEXT PRIMARY KEY, list_name TEXT NOT NULL, item_text TEXT NOT NULL,
    quantity REAL, unit TEXT, category TEXT,
    checked INTEGER DEFAULT 0,
    added_by TEXT REFERENCES common_members(id),
    added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    checked_at TEXT
);
CREATE INDEX idx_lists_active ON ops_lists(list_name, checked) WHERE checked = 0;

CREATE TABLE IF NOT EXISTS ops_gmail_whitelist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_type TEXT NOT NULL CHECK (match_type IN ('items_email','domain','explicit_address')),
    pattern TEXT NOT NULL, notes TEXT, active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS ops_gmail_triage_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    match_field TEXT DEFAULT 'subject' CHECK (match_field IN ('subject','from','body')),
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ops_streaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL REFERENCES common_members(id),
    streak_type TEXT NOT NULL DEFAULT 'daily_completion',
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    last_completion_date TEXT,
    grace_days_used INTEGER DEFAULT 0,
    max_grace_days INTEGER DEFAULT 1,
    custody_pause_enabled INTEGER DEFAULT 0,
    paused_since TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(member_id, streak_type)
);

-- ═══════════════════════════════════════════════════════════════
-- cal_* — Calendar intelligence
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS cal_sources (
    id TEXT PRIMARY KEY,
    google_calendar_id TEXT NOT NULL UNIQUE,
    summary TEXT, purpose TEXT,
    for_member_ids TEXT DEFAULT '[]',
    classification_id TEXT REFERENCES common_source_classifications(id),
    sync_token TEXT, last_synced TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS cal_raw_events (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES cal_sources(id),
    google_event_id TEXT NOT NULL,
    summary TEXT, description TEXT, location TEXT,
    start_time TEXT, end_time TEXT, all_day INTEGER DEFAULT 0,
    recurrence_rule TEXT, attendees TEXT, status TEXT,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(source_id, google_event_id)
);
CREATE INDEX idx_raw_start ON cal_raw_events(start_time);

CREATE TABLE IF NOT EXISTS cal_classified_events (
    id TEXT PRIMARY KEY,
    raw_event_id TEXT REFERENCES cal_raw_events(id),
    source_type TEXT DEFAULT 'calendar', source_id TEXT,
    event_date TEXT NOT NULL CHECK (date(event_date) IS NOT NULL),
    start_time TEXT, end_time TEXT, all_day INTEGER DEFAULT 0,
    title TEXT,
    title_redacted TEXT,
    event_type TEXT, category TEXT,
    for_member_ids TEXT DEFAULT '[]',
    scheduling_impact TEXT CHECK (scheduling_impact IS NULL OR scheduling_impact IN
        ('HARD_BLOCK','SOFT_BLOCK','REQUIRES_TRANSPORT','FYI')),
    privacy TEXT DEFAULT 'full' CHECK (privacy IN ('full','privileged','redacted')),
    location_id TEXT REFERENCES common_locations(id),
    prep_minutes INTEGER DEFAULT 0, wind_down_minutes INTEGER DEFAULT 0,
    travel_minutes_to INTEGER, travel_minutes_from INTEGER,
    is_primary INTEGER DEFAULT 1, dedup_group_id TEXT,
    confidence TEXT DEFAULT 'high' CHECK (confidence IN ('high','medium','low')),
    needs_human_review INTEGER DEFAULT 0, classification_rule TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_class_date ON cal_classified_events(event_date);
CREATE INDEX idx_class_impact ON cal_classified_events(scheduling_impact, event_date);

CREATE TABLE IF NOT EXISTS cal_daily_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state_date TEXT NOT NULL CHECK (date(state_date) IS NOT NULL),
    version INTEGER NOT NULL DEFAULT 1,
    custody_states TEXT NOT NULL, member_states TEXT NOT NULL,
    transportation TEXT, coverage_status TEXT,
    activity_schedule TEXT, meal_logistics TEXT,
    complexity_score REAL NOT NULL,
    task_load TEXT, budget_snapshot TEXT, life_phase TEXT,
    computed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(state_date, version)
);
CREATE INDEX idx_daily_date ON cal_daily_states(state_date, version DESC);

CREATE TABLE IF NOT EXISTS cal_conflicts (
    id TEXT PRIMARY KEY,
    conflict_date TEXT NOT NULL CHECK (date(conflict_date) IS NOT NULL),
    conflict_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('critical','high','medium','low')),
    title TEXT, description TEXT,
    affected_member_ids TEXT, affected_event_ids TEXT,
    possible_resolutions TEXT,
    status TEXT DEFAULT 'unresolved' CHECK (status IN ('unresolved','resolved','auto_resolved','expired')),
    resolved_by TEXT, resolution_notes TEXT, resolution_task_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_conflicts_open ON cal_conflicts(status, conflict_date) WHERE status = 'unresolved';

CREATE TABLE IF NOT EXISTS cal_disambiguation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL, match_field TEXT NOT NULL,
    resolved_type TEXT NOT NULL, resolved_member_ids TEXT,
    resolved_impact TEXT,
    resolved_prep_minutes INTEGER DEFAULT 0,
    resolved_wind_down_minutes INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 100,
    created_by TEXT DEFAULT 'onboarding',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ═══════════════════════════════════════════════════════════════
-- fin_* — Finance: transactions, budgets, merchants, bills
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS fin_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_date TEXT NOT NULL CHECK (date(transaction_date) IS NOT NULL),
    posted_date TEXT CHECK (posted_date IS NULL OR date(posted_date) IS NOT NULL),
    merchant_raw TEXT NOT NULL, merchant_normalized TEXT,
    amount REAL NOT NULL,
    category TEXT NOT NULL DEFAULT 'Uncategorized', subcategory TEXT,
    account TEXT,
    is_recurring INTEGER DEFAULT 0, is_excluded INTEGER DEFAULT 0, is_income INTEGER DEFAULT 0,
    item_ref TEXT, capital_expense_ref TEXT,
    categorization_rule TEXT, categorization_confidence REAL DEFAULT 1.0,
    needs_review INTEGER DEFAULT 0, notes TEXT, raw_data TEXT,
    import_source TEXT, import_batch TEXT, external_id TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_txn_date ON fin_transactions(transaction_date);
CREATE INDEX idx_txn_category ON fin_transactions(category);
CREATE INDEX idx_txn_review ON fin_transactions(needs_review) WHERE needs_review = 1;

CREATE TABLE IF NOT EXISTS fin_budget_config (
    category TEXT PRIMARY KEY, monthly_target REAL NOT NULL,
    is_fixed INTEGER DEFAULT 0, is_discretionary INTEGER DEFAULT 1,
    alert_threshold REAL DEFAULT 0.90, notes TEXT
);

CREATE TABLE IF NOT EXISTS fin_merchant_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    match_type TEXT DEFAULT 'contains' CHECK (match_type IN ('contains','exact','regex','starts_with')),
    category TEXT NOT NULL, subcategory TEXT, normalized_name TEXT,
    priority INTEGER DEFAULT 100, active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS fin_capital_expenses (
    id TEXT PRIMARY KEY, title TEXT NOT NULL,
    target_amount REAL NOT NULL, target_date TEXT,
    monthly_contribution REAL, accumulated REAL DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK (status IN ('active','funded','completed','cancelled')),
    domain TEXT, task_ref TEXT, notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS fin_recurring_bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, amount REAL NOT NULL, category TEXT NOT NULL,
    due_day INTEGER, frequency TEXT NOT NULL,
    auto_pay INTEGER DEFAULT 0, account TEXT, item_ref TEXT,
    next_due TEXT NOT NULL CHECK (date(next_due) IS NOT NULL),
    last_paid TEXT, active INTEGER DEFAULT 1, notes TEXT
);

CREATE TABLE IF NOT EXISTS fin_budget_snapshot (
    category TEXT PRIMARY KEY, monthly_target REAL,
    is_fixed INTEGER, is_discretionary INTEGER, alert_threshold REAL,
    spent_this_month REAL DEFAULT 0, remaining REAL DEFAULT 0,
    pct_used REAL DEFAULT 0, over_threshold INTEGER DEFAULT 0,
    computed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ═══════════════════════════════════════════════════════════════
-- mem_* — Memory, sessions, AI conversations
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS mem_sessions (
    id TEXT PRIMARY KEY,
    member_id TEXT REFERENCES common_members(id),
    channel TEXT,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    last_message_at TEXT, message_count INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1, metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS mem_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES mem_sessions(id),
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool_use','tool_result')),
    content TEXT NOT NULL,
    tool_calls TEXT, tool_results TEXT, context_assembled TEXT,
    tokens_in INTEGER, tokens_out INTEGER, model TEXT,
    actions_taken TEXT DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_msg_session ON mem_messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS mem_session_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES mem_sessions(id),
    fact_type TEXT NOT NULL CHECK (fact_type IN ('decision','preference','correction','observation','commitment')),
    content TEXT NOT NULL, domain TEXT,
    member_id TEXT REFERENCES common_members(id),
    auto_promoted INTEGER DEFAULT 0,
    expires_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now', '+72 hours')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS mem_long_term (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL, content TEXT NOT NULL, domain TEXT,
    member_id TEXT REFERENCES common_members(id),
    item_ref TEXT REFERENCES ops_items(id),
    source_session TEXT, source_description TEXT,
    source TEXT DEFAULT 'user_stated' CHECK (source IN ('user_stated','inferred','observed','auto_promoted')),
    confidence REAL DEFAULT 1.0, is_permanent INTEGER DEFAULT 0,
    reinforcement_count INTEGER DEFAULT 1,
    last_reinforced_at TEXT, last_referenced_at TEXT,
    superseded_by INTEGER REFERENCES mem_long_term(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS mem_long_term_fts USING fts5(
    content, category, domain,
    content='mem_long_term', content_rowid='id'
);

CREATE TABLE IF NOT EXISTS mem_precomputed_digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    digest_type TEXT NOT NULL,
    for_member TEXT NOT NULL REFERENCES common_members(id),
    digest_date TEXT NOT NULL CHECK (date(digest_date) IS NOT NULL),
    structured_data TEXT NOT NULL, composed_text TEXT, composed_at TEXT,
    delivered INTEGER DEFAULT 0, delivered_at TEXT, delivered_via TEXT,
    UNIQUE(digest_type, for_member, digest_date)
);

CREATE TABLE IF NOT EXISTS mem_approval_queue (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT,
    payload TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    requested_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','expired')),
    decided_by TEXT, decided_at TEXT,
    auto_expire_at TEXT,
    expiry_notification_sent INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS mem_cos_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,
    description TEXT NOT NULL,
    entity_type TEXT, entity_id TEXT,
    confidence REAL DEFAULT 1.0,
    undo_id INTEGER REFERENCES common_undo_log(id),
    actor TEXT NOT NULL DEFAULT 'pib',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ═══════════════════════════════════════════════════════════════
-- pib_* — Behavioral: rewards, energy, coaching
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS pib_reward_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL REFERENCES common_members(id),
    task_id TEXT REFERENCES ops_tasks(id),
    reward_tier TEXT NOT NULL CHECK (reward_tier IN ('simple','warm','delight','jackpot')),
    reward_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS pib_energy_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL REFERENCES common_members(id),
    state_date TEXT NOT NULL CHECK (date(state_date) IS NOT NULL),
    energy_level TEXT DEFAULT 'medium' CHECK (energy_level IN ('high','medium','low','crashed')),
    sleep_quality TEXT CHECK (sleep_quality IS NULL OR sleep_quality IN ('great','okay','rough')),
    meds_taken INTEGER DEFAULT 0,
    meds_taken_at TEXT,
    focus_mode INTEGER DEFAULT 0,
    completions_today INTEGER DEFAULT 0,
    last_completion_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(member_id, state_date)
);

CREATE TABLE IF NOT EXISTS pib_coach_protocols (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    behavior TEXT NOT NULL,
    examples TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ═══════════════════════════════════════════════════════════════
-- FTS5 indexes for full-text search
-- ═══════════════════════════════════════════════════════════════

CREATE VIRTUAL TABLE IF NOT EXISTS ops_tasks_fts USING fts5(
    title, notes, micro_script,
    content='ops_tasks', content_rowid='rowid'
);

CREATE VIRTUAL TABLE IF NOT EXISTS ops_items_fts USING fts5(
    name, notes, category, type,
    content='ops_items', content_rowid='rowid'
);

-- ═══════════════════════════════════════════════════════════════
-- Initial seed: schema version
-- ═══════════════════════════════════════════════════════════════

INSERT INTO meta_schema_version (version, description) VALUES (1, 'Initial PIB v5 schema');
