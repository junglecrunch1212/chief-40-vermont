import { useState, useCallback } from "react";

const C = {
  bg: "#090c14",
  panel: "#0d1117",
  panelBorder: "#1b2332",
  card: "#121a27",
  cardBorder: "#1e2d42",
  text: "#d4dce8",
  textMid: "#8b9bb5",
  textDim: "#556480",
  accent: "#58a6ff",
  accentDim: "#1a3a5c",
  folder: "#e8b84a",
  folderDim: "#6d5a28",
  python: "#3572a5",
  sql: "#e38c00",
  toml: "#9b4dca",
  ini: "#cb7832",
  yaml: "#cb171e",
  js: "#f1e05a",
  json: "#292929",
  html: "#e34c26",
  md: "#083fa1",
  sh: "#89e051",
  env: "#4ec9b0",
  plist: "#a2aaad",
  generic: "#8b949e",
  green: "#3fb950",
  red: "#f85149",
  amber: "#d29922",
  purple: "#a371f7",
};

function getFileColor(name) {
  if (name.endsWith(".py")) return C.python;
  if (name.endsWith(".sql")) return C.sql;
  if (name.endsWith(".toml")) return C.toml;
  if (name.endsWith(".ini")) return C.ini;
  if (name.endsWith(".yaml") || name.endsWith(".yml")) return C.yaml;
  if (name.endsWith(".js") || name.endsWith(".jsx")) return C.js;
  if (name.endsWith(".json")) return C.accent;
  if (name.endsWith(".html") || name.endsWith(".css")) return C.html;
  if (name.endsWith(".md")) return C.md;
  if (name.endsWith(".sh")) return C.sh;
  if (name.endsWith(".env")) return C.env;
  if (name.endsWith(".plist")) return C.plist;
  if (name.endsWith(".db")) return C.amber;
  if (name.endsWith(".jsonl")) return C.green;
  return C.generic;
}

function getFileIcon(name) {
  if (name.endsWith(".py")) return "🐍";
  if (name.endsWith(".sql")) return "🗃️";
  if (name.endsWith(".toml") || name.endsWith(".ini") || name.endsWith(".yaml")) return "⚙️";
  if (name.endsWith(".js") || name.endsWith(".jsx")) return "📜";
  if (name.endsWith(".json")) return "📋";
  if (name.endsWith(".html")) return "🌐";
  if (name.endsWith(".css")) return "🎨";
  if (name.endsWith(".md")) return "📝";
  if (name.endsWith(".sh")) return "🖥️";
  if (name.endsWith(".env")) return "🔒";
  if (name.endsWith(".plist")) return "🍎";
  if (name.endsWith(".db")) return "💾";
  if (name.endsWith(".jsonl")) return "📊";
  if (name.endsWith(".enc")) return "🔐";
  return "📄";
}

// ─── FILE TREE DATA ───
const TREE = {
  name: "/opt/pib/",
  desc: "Project root — Mac Mini COS-1 (headless, closet, always-on)",
  tags: ["root"],
  children: [
    {
      name: "src/",
      desc: "Source code package — all PIB application logic",
      children: [
        {
          name: "pib/",
          desc: "Main Python package — imported as 'from pib import ...'",
          children: [
            { name: "__init__.py", desc: "Package init. Exports version string, configures logging on import. Entry point for `python -m pib`.", section: "§3.1", layer: 1 },
            { name: "db.py", desc: "Database layer. Contains WriteQueue (batched flush every 100ms/50 items with persistent connection), migration framework (up/down with SHA256 checksums), SQLite PRAGMA config (WAL, busy_timeout, mmap), next_id() generator with VALID_PREFIXES allowlist. Critical rule: never hold a DB transaction across an LLM call.", section: "§3.5–3.7", layer: 1 },
            { name: "engine.py", desc: "The heart of PIB. Contains whatNow() — the ONE deterministic function the entire system exists to answer. Also compute_energy_level(), scoring algorithm (urgency×10 + energy×5 + effort×3 + freshness×2), DBSnapshot dataclass, and WhatNowResult. No LLM, no side effects, same inputs → same output.", section: "§4", layer: 1 },
            { name: "ingest.py", desc: "Unified ingestion pipeline (8 stages): dedup → member resolution → parse to Five Shapes → classify domain/urgency/energy → privacy fence → route+write → cross-domain observations → confirm+emit. Also contains all 8 adapter implementations (Gmail, Google Cal, Apple Reminders, iMessage/BlueBubbles, Twilio SMS, Siri Shortcuts, Bank CSV, Sheets webhook), the Adapter Protocol interface, IngestEvent dataclass, and prefix parser with 20+ regex rules.", section: "§6", layer: 1 },
            { name: "llm.py", desc: "Claude LLM integration. System prompt composition, 15 tool definitions (create_task, what_now, query_schedule, query_transactions, query_budget, save_memory, recall_memory, send_message, etc.), conversation flow with streaming (SSE), 3-layer relevance detection (keywords → entity match → always-on summary), context assembly with token budgets (~51K total), model router (Opus for digests, Sonnet for chat, Haiku for triage), hallucination guard for morning digest, and deterministic fallback when API is down.", section: "§7", layer: 2 },
            { name: "proactive.py", desc: "Proactive engine — trigger-based outbound messaging. PROACTIVE_TRIGGERS array with priority/cooldown/query for: morning digest, paralysis detection (2h silence), post-meeting capture, velocity celebration, overdue nudge, budget alerts, weekly review, bill reminders, approval expiry. GUARDRAILS: 5 msgs/person/day, 2/hour, quiet hours 10pm–7am, respect focus mode. compose_morning_digest() with hallucination guard (structured data → Opus → validate → deliver).", section: "§8", layer: 2 },
            { name: "memory.py", desc: "Long-term memory system. save_memory_deduped() with word-overlap similarity (>60% = duplicate, reinforce; negation detected = supersede). is_negation_of() checks NEGATION_PREFIXES. auto_promote_session_facts() runs every 6h — promotes decisions/preferences/corrections/commitments from session facts to long-term memory based on confidence scoring with keyword boosters. FTS5 search via mem_long_term_fts.", section: "§3.8, mem_*", layer: 1 },
            { name: "sheets.py", desc: "Google Sheets bidirectional sync. DB→Sheets push every 15min (cron). Sheets→DB via Apps Script installable onChange trigger with queue pattern. Bootstrap import for existing Life OS data via The Loop (discover → propose → confirm → config). Conflict rule: most recent write wins with audit log. SHEETS_SYNC_CONFIG maps tabs (TASKS, ITEMS, LISTS, RECURRING, BUDGET) to DB tables.", section: "§9", layer: 3 },
            { name: "custody.py", desc: "Custody date math — DST-aware with 20+ test cases including spring forward and fall back. who_has_child() is pure deterministic given custody_config (alternating weeks, weekends+midweek, holiday overrides). Computes daily states for coverage gaps, transportation needs, activity schedules. Streaks auto-pause on custody-away days.", section: "§2.3, §4", layer: 1 },
            { name: "rewards.py", desc: "ADHD behavioral mechanics — 'dark prosthetics' that hack dopaminergic circuits. Variable-ratio reinforcement: 70% simple, 20% warm, 8% delight, 2% jackpot rewards. select_reward() uses random.random() for slot-machine psychology. complete_task_with_reward() chains: complete → update velocity → update streak → select reward → log → Zeigarnik hook. Streak logic: elastic (1 grace day), custody-aware, celebrates records.", section: "§5", layer: 1 },
            { name: "web.py", desc: "FastAPI application. Routes: /api/* (REST), /webhooks/* (inbound), /dashboard (today view with per-actor views), /scoreboard (kitchen TV — dark bg, large text, auto-refresh 60s), /health (read-only probe for Healthchecks.io), /chat (web chat with SSE streaming). Rate limiter middleware. Cloudflare Access validation. Mounts static files. Entry point: uvicorn pib.web:app.", section: "§3.1, §5.5", layer: 1 },
            { name: "auth.py", desc: "Authentication module. Cloudflare Access JWT validation (Google OAuth for James + Laura). Twilio X-Twilio-Signature HMAC validation. BlueBubbles shared secret header check. Siri Shortcuts Bearer token validation. Google Sheets service account key verification. Per-source rate limiting with configurable windows.", section: "§3.2–3.3", layer: 1 },
            { name: "scheduler.py", desc: "APScheduler AsyncIOScheduler setup — NEVER BlockingScheduler (would freeze FastAPI event loop). Registers all cron jobs: calendar sync (*/15), recurring spawn (6am), budget refresh (7:15am), sheets push (*/15), proactive scan (*/30 7-22), morning digest (6am), memory promote (*/6h), health probe (*/30), backups (hourly), dead letter retry (4am), FTS5 rebuild (weekly), approval expiry (*/15), db size monitor (daily).", section: "§12 Cron", layer: 1 },
            { name: "corrections.py", desc: "Misclassification correction system — Gene 1's feedback loop. handle_correction() processes 'fix:' and 'reclassify:' prefix commands. Updates RULES not just individual records: transaction_category → updates fin_merchant_rules, email_triage → updates ops_gmail_whitelist, task_domain → updates ops_tasks. Pattern: DISCOVER → user CORRECTS → CONFIG updated → future DETERMINISTIC execution uses corrected rule.", section: "§8.4", layer: 1 },
            { name: "backup.py", desc: "Backup and recovery. Hourly SQLite .backup to /opt/pib/data/backups/. backup_verify() restores to /tmp, runs PRAGMA integrity_check, deletes temp. cloud_backup() daily encrypted upload to Google Drive (age encryption). db_size_monitor() warns at 500MB, VACUUMs at 30% fragmentation. fts5_rebuild() weekly to fix silent staleness.", section: "§12", layer: 1 },
            { name: "cost.py", desc: "API cost tracking. track_api_cost() reads x-usage-input-tokens and x-usage-output-tokens response headers, computes per-request cost (Sonnet $3/$15 per M tokens, Opus $15/$75), accumulates in pib_config keyed by month. Surfaces monthly cost in weekly review digest and /dashboard.", section: "§12", layer: 1 },
          ],
        },
      ],
    },
    {
      name: "tests/",
      desc: "Test suite — pytest with asyncio_mode=auto, in-memory SQLite fixtures",
      children: [
        { name: "conftest.py", desc: "Shared fixtures. db() creates in-memory SQLite with full schema + seed data via apply_migrations(). snapshot() creates pre-loaded DBSnapshot for whatNow() tests with standard task set, mock energy/daily states, and SEED_MEMBERS.", section: "§13.3", layer: 1 },
        { name: "test_what_now.py", desc: "whatNow() determinism tests. Verifies same inputs → same output (no randomness in task selection). Tests scoring algorithm, energy matching, overdue prioritization, custody-aware filtering, medication peak/crash behavior.", section: "§4, §13.4", layer: 1 },
        { name: "test_custody.py", desc: "20+ custody date math cases. Parametrized over DST boundaries: day before spring forward, spring forward itself (23h day), day before fall back, fall back (25h day). Tests alternating weeks, holiday overrides, midweek visits.", section: "§13.4", layer: 1 },
        { name: "test_state_machine.py", desc: "Task state machine transitions + guards. Verifies: 'done' requires no extra data (one tap), 'dismissed' requires notes ≥10 chars, 'deferred' requires scheduled_date, 'waiting_on' requires waiting_on field. Tests all valid/invalid transitions.", section: "§5.3", layer: 1 },
        { name: "test_prefix_parser.py", desc: "20+ test cases for prefix command parsing. Covers: grocery:/costco:/target:/hardware: list prefixes, james:/laura: assignment, buy/call action prefixes, meds/sleep state commands, remember memory saves.", section: "§6.4", layer: 1 },
        { name: "test_ingest_pipeline.py", desc: "Full 8-stage pipeline integration tests. Verifies: dedup (same idempotency key → skip), member resolution, Five Shapes parsing, classification, privacy fence filtering, route+write to correct tables, cross-domain observation generation, confirmation emission.", section: "§6.3", layer: 1 },
        { name: "test_memory_dedup.py", desc: "Memory deduplication + negation detection. Tests: word overlap >60% → reinforce (increment count), negation detected → supersede (old.superseded_by = new.id), new fact → insert. Covers NEGATION_PREFIXES ('not', 'no longer', 'doesn\\'t', 'stopped', etc.).", section: "§3.8", layer: 1 },
        { name: "test_rewards.py", desc: "Variable-ratio reinforcement tests. Verifies probability distribution (70/20/8/2), template interpolation ({streak}, {today_count}, {week_count}, {days_old}), complete_task_with_reward() chain, Zeigarnik hook generation.", section: "§5.1", layer: 1 },
        { name: "test_energy.py", desc: "Energy state computation tests. Medication peak/crash windows, sleep quality effects on task selection, focus mode blocking, energy level computation from time-of-day + meds + sleep.", section: "§4, §5", layer: 1 },
        { name: "test_streaks.py", desc: "Streak tracking tests. Elastic streaks (1 grace day), custody-aware pausing, streak break → 'welcome back' recovery messaging, best streak tracking, new record detection.", section: "§5.2", layer: 1 },
        { name: "test_privacy_fence.py", desc: "Invariant 5: privileged data never enters context window. Uses PRIVACY_CANARY='CANARY_XJ7_PRIVILEGED_LEAK_DETECTOR' seeded into privileged events. Tests canary never appears in: calendar context, cross-domain summary, full assembled context, morning digest, tool results. Covers all actors.", section: "§13.4", layer: 1 },
      ],
    },
    {
      name: "migrations/",
      desc: "SQL migration files — UP/DOWN with SHA256 checksums, applied in order",
      children: [
        { name: "001_initial_schema.sql", desc: "Bootstrap — all CREATE TABLE statements for all 7 domain prefixes (common_*, ops_*, cal_*, fin_*, mem_*, pib_*, meta_*). All indexes, CHECK constraints, FTS5 virtual tables. The entire database structure in one file.", section: "§3.8", layer: 1 },
        { name: "002_add_energy_states.sql", desc: "Adds pib_energy_states table (medication tracking, sleep quality, focus mode, completions, velocity cap). Adds default velocity_cap config. DOWN: DROP TABLE + DELETE config.", section: "§3.8", layer: 1 },
        { name: "003_add_pib_config.sql", desc: "Adds pib_config table for runtime configuration (model IDs, thresholds, feature flags). Seeds initial config values. DOWN: DROP TABLE.", section: "§3.8", layer: 1 },
      ],
    },
    {
      name: "config/",
      desc: "Credentials and configuration — chmod 600, owned by pib user",
      children: [
        { name: ".env", desc: "All secrets: ANTHROPIC_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, GOOGLE_SA_KEY_PATH, BLUEBUBBLES_SECRET, CLOUDFLARE_TUNNEL_TOKEN, BACKUP_PUBLIC_KEY (age), PIB_SHEETS_WEBHOOK_TOKEN. Never committed to version control. Key rotation schedule: Anthropic quarterly, Twilio annually, BlueBubbles after macOS updates.", section: "§12", layer: 1 },
        { name: "google-sa-key.json", desc: "Google service account key for server-to-server auth. Used by Calendar API, Sheets API, Gmail API, Drive API (backups). Downloaded from Google Cloud Console. Domain-wide delegation for calendar access.", section: "§12", layer: 3 },
        { name: "cloudflare-tunnel.yaml", desc: "Cloudflare Tunnel configuration. Routes: /api/*, /webhooks/*, /dashboard, /scoreboard, /health → localhost:3141. Ingress rules and access policies.", section: "§3.1", layer: 1 },
      ],
    },
    {
      name: "data/",
      desc: "Persistent data — SQLite database, backups, file watch directory",
      children: [
        { name: "pib.db", desc: "THE DATABASE. SQLite 3.45+ in WAL mode. Single file, ~7 domain prefixes, ~35+ tables, FTS5 indexes. Append-only (Gene 7: no row ever deleted). Hourly backups. Daily encrypted cloud backup. PRAGMA: WAL, busy_timeout=5000, foreign_keys=ON, synchronous=NORMAL, cache_size=-64000, mmap_size=268435456.", section: "§3.1, §3.5", layer: 1 },
        { name: "pib.db-wal", desc: "Write-Ahead Log file. SQLite WAL mode allows concurrent readers during writes. Automatically managed by SQLite. Checkpointed periodically.", section: "§3.5", layer: 1 },
        { name: "pib.db-shm", desc: "Shared memory file for WAL mode. Index into the WAL file for fast lookups. Automatically managed by SQLite.", section: "§3.5", layer: 1 },
        {
          name: "backups/",
          desc: "Hourly SQLite backups — verified via PRAGMA integrity_check",
          children: [
            { name: "pib-YYYYMMDD-HH.db", desc: "Hourly backup via sqlite3 .backup command. Consistent snapshot even during writes. Retained for 7 days. Verified every 30 min: restore to /tmp → integrity_check → delete. If verify fails → critical alert.", section: "§12", layer: 1 },
          ],
        },
        {
          name: "bank-imports/",
          desc: "CSV file watch directory — bank/credit card transaction imports",
          children: [
            { name: "*.csv", desc: "Bank/credit card CSV exports. Watched every 5 min by Bank Import adapter. Parsed with idempotency key SHA256(bank:{acct}:{date}:{amt}:{merchant}). Merchant rules applied for auto-categorization. Plaid integration deferred.", section: "§6.2", layer: 3 },
          ],
        },
      ],
    },
    {
      name: "logs/",
      desc: "Structured JSON logs — rotating 50MB × 5 files",
      children: [
        { name: "pib.jsonl", desc: "Primary log file. JSON format per line: {ts, level, logger, msg, module, func, ...extra}. Rotating: 50MB per file, 5 backups. Also streams to stdout for launchd capture. Usage: log.info('Task completed', extra={'task_id': 't-0042', 'member': 'm-james'}).", section: "§3.4", layer: 1 },
        { name: "pib.jsonl.1", desc: "Rotated log backup 1 (most recent rotation).", section: "§3.4", layer: 1 },
        { name: "pib.jsonl.2", desc: "Rotated log backup 2.", section: "§3.4", layer: 1 },
      ],
    },
    {
      name: "scripts/",
      desc: "Operational scripts — setup, maintenance, recovery",
      children: [
        { name: "setup_google_oauth.py", desc: "Initial OAuth consent flow for Google APIs. Run once to authorize Calendar, Gmail, Sheets, Drive access. Stores refresh token. Referenced in Recovery Matrix: 'Re-run setup_google_oauth.py' when OAuth expires.", section: "§12", layer: 3 },
        { name: "seed_data.py", desc: "Seeds initial household data: 4 members (James, Laura, Charlie, Baby), Captain (pet entity), custody config, coach protocols (8 protocols from §5.4), life phases (Pre-Baby → Newborn → Infant → Toddler), pib_config defaults (model IDs, timezone, emergency contacts, milestones), role visibility matrix.", section: "Appendix", layer: 1 },
        { name: "sheets_import.py", desc: "Bootstrap import of existing Google Sheets data (James's Life OS). Runs The Loop: discover what's in sheets → propose classification → wait for human confirm → config updated → import data into SQLite.", section: "§9.1", layer: 3 },
        { name: "cloud_backup.sh", desc: "Daily encrypted backup to Google Drive. sqlite3 .backup → age encrypt with BACKUP_PUBLIC_KEY → upload via service account → cleanup temp files. Runs at 4am via cron.", section: "§12", layer: 1 },
      ],
    },
    {
      name: "google-apps-script/",
      desc: "Google Apps Script code — deployed to the household Google Sheet",
      children: [
        { name: "Code.gs", desc: "Installable onChange trigger (NOT simple onEdit — those can't make UrlFetchApp calls and silently swallow errors). Diff-on-change pattern: compare current sheet state vs cached snapshot, queue changed rows to hidden _pib_queue sheet, flush to PIB webhook. Functions: onChange(), diffTab(), cacheTabSnapshot(), flushQueue(). Tracked tabs: TASKS, ITEMS, LISTS, RECURRING, BUDGET.", section: "§9.1", layer: 3 },
      ],
    },
    {
      name: "static/",
      desc: "Web frontend assets — served by FastAPI static mount",
      children: [
        { name: "dashboard.html", desc: "Main dashboard page. Per-actor views: James sees carousel (ONE card, micro-script, Done/Skip/Dismiss), Laura sees compressed (decisions [Y/N] + tasks + household status). Fetches /api/what-now, /api/tasks, /api/schedule, /api/budget. JavaScript + CSS inline.", section: "§2.1, §2.2", layer: 1 },
        { name: "scoreboard.html", desc: "Kitchen TV display at /scoreboard. Dark background, large text, readable from 10 feet. Auto-refresh every 60 seconds via fetch(/api/scoreboard-data). Shows: per-member streaks + completions + next task + weekly points, Captain status (walked/fed/next), family total vs target.", section: "§5.5", layer: 1 },
        { name: "chat.html", desc: "Web chat interface. SSE streaming for real-time LLM responses. Supports tool use visualization (up to 5 tool rounds). Message history with sliding window. State commands (meds, sleep) handled before LLM. Prefix commands work without LLM (Layer 1).", section: "§7.6", layer: 1 },
      ],
    },
    {
      name: "launchd/",
      desc: "macOS launchd configuration — auto-start, restart on crash",
      children: [
        { name: "com.pib.runtime.plist", desc: "launchd plist for PIB FastAPI server. RunAtLoad=true, KeepAlive=true (restart on crash). WorkingDirectory=/opt/pib. ProgramArguments: /opt/pib/venv/bin/uvicorn pib.web:app --host 0.0.0.0 --port 3141. StandardOutPath/StandardErrorPath → /opt/pib/logs/. Install: launchctl load com.pib.runtime.plist.", section: "§3.1, §12", layer: 1 },
      ],
    },
    { name: "pyproject.toml", desc: "Python project config. Defines package metadata, dependencies (fastapi, aiosqlite, apscheduler, httpx, anthropic, python-dotenv), dev dependencies (pytest, pytest-asyncio, coverage). Tool configs: [tool.pytest.ini_options] asyncio_mode='auto', [tool.coverage.run] source=['src/pib'].", section: "§13.2", layer: 1 },
    { name: "pytest.ini", desc: "pytest configuration. testpaths=tests, asyncio_mode=auto. Markers: unit (pure functions, no DB), integration (in-memory SQLite), e2e (real adapters).", section: "§13.2", layer: 1 },
    { name: "README.md", desc: "Project documentation. What PIB is (prosthetic prefrontal cortex), the Nine Genes, the Four Actors, setup instructions, build order (4 phases), operational runbook references.", section: "—", layer: 1 },
  ],
};

function countFiles(node) {
  if (!node.children) return 1;
  return node.children.reduce((s, c) => s + countFiles(c), 0);
}

function countFolders(node) {
  if (!node.children) return 0;
  return 1 + node.children.reduce((s, c) => s + countFolders(c), 0);
}

const TOTAL_FILES = countFiles(TREE);
const TOTAL_FOLDERS = countFolders(TREE);

function FileDetail({ file, onClose }) {
  const color = getFileColor(file.name);
  const icon = getFileIcon(file.name);
  const layerColors = { 1: C.green, 2: C.purple, 3: C.accent };
  const layerLabels = { 1: "Layer 1: Core", 2: "Layer 2: Enhanced (LLM)", 3: "Layer 3: Extended (APIs)" };

  return (
    <div style={{
      background: C.card,
      border: `1px solid ${color}40`,
      borderRadius: 8,
      padding: "14px 16px",
      marginTop: 8,
      animation: "fadeIn 0.2s ease",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 18 }}>{icon}</span>
          <span style={{
            fontSize: 13, fontWeight: 700, color,
            fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
          }}>
            {file.name}
          </span>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onClose(); }}
          style={{
            background: "none", border: "none", color: C.textDim,
            cursor: "pointer", fontSize: 16, padding: "0 4px",
            lineHeight: 1,
          }}
        >
          ×
        </button>
      </div>

      <p style={{
        fontSize: 12, color: C.text, lineHeight: 1.65, margin: "10px 0 0",
        maxWidth: 600,
      }}>
        {file.desc}
      </p>

      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
        {file.section && (
          <span style={{
            fontSize: 9.5, padding: "2px 7px", borderRadius: 3,
            background: `${C.accent}18`, border: `1px solid ${C.accent}35`,
            color: C.accent, fontFamily: "monospace",
          }}>
            {file.section}
          </span>
        )}
        {file.layer && (
          <span style={{
            fontSize: 9.5, padding: "2px 7px", borderRadius: 3,
            background: `${layerColors[file.layer]}15`,
            border: `1px solid ${layerColors[file.layer]}35`,
            color: layerColors[file.layer],
            fontFamily: "monospace",
          }}>
            {layerLabels[file.layer]}
          </span>
        )}
      </div>
    </div>
  );
}

function TreeNode({ node, depth = 0, expanded, toggle, selectedFile, setSelectedFile, path = "" }) {
  const isFolder = !!node.children;
  const isOpen = expanded.has(path);
  const isSelected = selectedFile === path;
  const fileColor = isFolder ? C.folder : getFileColor(node.name);

  return (
    <div>
      <div
        onClick={() => {
          if (isFolder) {
            toggle(path);
          } else {
            setSelectedFile(isSelected ? null : path);
          }
        }}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "4px 0",
          paddingLeft: depth * 18,
          cursor: "pointer",
          borderRadius: 4,
          background: isSelected ? `${fileColor}12` : "transparent",
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => {
          if (!isSelected) e.currentTarget.style.background = `${C.text}08`;
        }}
        onMouseLeave={(e) => {
          if (!isSelected) e.currentTarget.style.background = "transparent";
        }}
      >
        {/* Indent guide lines */}
        {depth > 0 && Array.from({ length: depth }).map((_, i) => (
          <span key={i} style={{
            position: "absolute",
            left: i * 18 + 9,
            top: 0,
            bottom: 0,
            width: 1,
            background: `${C.textDim}20`,
          }} />
        ))}

        {/* Folder arrow or file dot */}
        {isFolder ? (
          <span style={{
            fontSize: 10,
            color: C.folder,
            width: 14,
            textAlign: "center",
            transition: "transform 0.15s",
            transform: isOpen ? "rotate(90deg)" : "rotate(0)",
            display: "inline-block",
          }}>
            ▶
          </span>
        ) : (
          <span style={{
            width: 14,
            textAlign: "center",
            display: "inline-flex",
            justifyContent: "center",
          }}>
            <span style={{
              width: 5, height: 5, borderRadius: "50%",
              background: fileColor,
              opacity: 0.7,
            }} />
          </span>
        )}

        {/* Name */}
        <span style={{
          fontSize: 12,
          fontWeight: isFolder ? 600 : 400,
          color: isFolder ? C.folder : (isSelected ? fileColor : C.text),
          fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
          letterSpacing: isFolder ? "0.02em" : 0,
        }}>
          {node.name}
        </span>

        {/* Folder badge with file count */}
        {isFolder && (
          <span style={{
            fontSize: 9,
            color: C.textDim,
            fontFamily: "monospace",
            marginLeft: 4,
          }}>
            {node.children.length}
          </span>
        )}

        {/* Layer indicator dot */}
        {!isFolder && node.layer && (
          <span style={{
            width: 6, height: 6, borderRadius: "50%",
            background: node.layer === 1 ? C.green : node.layer === 2 ? C.purple : C.accent,
            marginLeft: "auto",
            marginRight: 4,
            opacity: 0.6,
            flexShrink: 0,
          }} />
        )}
      </div>

      {/* File detail panel */}
      {!isFolder && isSelected && (
        <div style={{ paddingLeft: depth * 18 + 20 }}>
          <FileDetail file={node} onClose={() => setSelectedFile(null)} />
        </div>
      )}

      {/* Children */}
      {isFolder && isOpen && (
        <div>
          {node.children.map((child, i) => (
            <TreeNode
              key={child.name}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              toggle={toggle}
              selectedFile={selectedFile}
              setSelectedFile={setSelectedFile}
              path={`${path}/${child.name}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function PIBFileExplorer() {
  const [expanded, setExpanded] = useState(new Set([
    "/opt/pib/", "/opt/pib//src/", "/opt/pib//src//pib/", "/opt/pib//tests/"
  ]));
  const [selectedFile, setSelectedFile] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");

  const toggle = useCallback((path) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  }, []);

  const expandAll = () => {
    const allPaths = [];
    const walk = (node, path) => {
      if (node.children) {
        allPaths.push(path);
        node.children.forEach(c => walk(c, `${path}/${c.name}`));
      }
    };
    walk(TREE, "/opt/pib/");
    setExpanded(new Set(allPaths));
  };

  const collapseAll = () => {
    setExpanded(new Set());
    setSelectedFile(null);
  };

  // Flat file list for search
  const allFiles = [];
  const walkFlat = (node, path) => {
    if (!node.children) {
      allFiles.push({ ...node, path: `${path}/${node.name}`, fullPath: path });
    } else {
      node.children.forEach(c => walkFlat(c, `${path}/${node.name}`));
    }
  };
  TREE.children.forEach(c => walkFlat(c, ""));

  const filteredFiles = searchQuery.length > 1
    ? allFiles.filter(f =>
        f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        f.desc.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : null;

  return (
    <div style={{
      background: C.bg,
      minHeight: "100vh",
      padding: "24px 16px",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      color: C.text,
    }}>
      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
        input::placeholder { color: ${C.textDim}; }
      `}</style>

      <div style={{ maxWidth: 780, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 16 }}>
          <h1 style={{
            fontSize: 20, fontWeight: 800, margin: 0, color: C.text,
            fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
            letterSpacing: "-0.02em",
          }}>
            💩 PIB v5 — Project Structure
          </h1>
          <p style={{ fontSize: 11, color: C.textDim, margin: "4px 0 0", lineHeight: 1.4 }}>
            {TOTAL_FILES} files · {TOTAL_FOLDERS} folders · Click files for description · Click folders to expand
          </p>
        </div>

        {/* Controls */}
        <div style={{
          display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap", alignItems: "center",
        }}>
          <input
            type="text"
            placeholder="Search files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              flex: 1, minWidth: 180,
              fontSize: 12, padding: "6px 10px",
              background: C.card, border: `1px solid ${C.cardBorder}`,
              borderRadius: 5, color: C.text, outline: "none",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          />
          <button onClick={expandAll} style={btnStyle}>expand all</button>
          <button onClick={collapseAll} style={btnStyle}>collapse all</button>
        </div>

        {/* Layer legend */}
        <div style={{ display: "flex", gap: 14, marginBottom: 14, flexWrap: "wrap" }}>
          {[
            { label: "L1 Core", color: C.green, desc: "always works" },
            { label: "L2 Enhanced", color: C.purple, desc: "LLM-powered" },
            { label: "L3 Extended", color: C.accent, desc: "external APIs" },
          ].map(l => (
            <span key={l.label} style={{
              display: "flex", alignItems: "center", gap: 5, fontSize: 10, color: C.textMid,
            }}>
              <span style={{
                width: 7, height: 7, borderRadius: "50%", background: l.color, opacity: 0.7,
              }} />
              <span style={{ fontFamily: "monospace", color: l.color, fontWeight: 600 }}>{l.label}</span>
              <span style={{ color: C.textDim }}>{l.desc}</span>
            </span>
          ))}
        </div>

        {/* Search results */}
        {filteredFiles && (
          <div style={{
            background: C.panel,
            border: `1px solid ${C.panelBorder}`,
            borderRadius: 8,
            padding: "12px 14px",
            marginBottom: 14,
          }}>
            <div style={{
              fontSize: 10, fontWeight: 700, color: C.textMid,
              letterSpacing: "0.08em", marginBottom: 8, fontFamily: "monospace",
            }}>
              {filteredFiles.length} RESULT{filteredFiles.length !== 1 ? "S" : ""}
            </div>
            {filteredFiles.length === 0 && (
              <p style={{ fontSize: 12, color: C.textDim, margin: 0 }}>No files match "{searchQuery}"</p>
            )}
            {filteredFiles.map((f, i) => (
              <div
                key={f.path}
                onClick={() => {
                  setSearchQuery("");
                  // expand parent folders and select file
                  const parts = f.path.split("/").filter(Boolean);
                  const newExpanded = new Set(expanded);
                  let accumulated = "/opt/pib/";
                  newExpanded.add(accumulated);
                  for (let j = 0; j < parts.length - 1; j++) {
                    accumulated += `/${parts[j]}`;
                    newExpanded.add(accumulated);
                  }
                  setExpanded(newExpanded);
                  setSelectedFile(f.path);
                }}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "6px 8px", cursor: "pointer", borderRadius: 4,
                  borderBottom: i < filteredFiles.length - 1 ? `1px solid ${C.panelBorder}` : "none",
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = `${C.text}08`}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
              >
                <span style={{ fontSize: 14 }}>{getFileIcon(f.name)}</span>
                <div>
                  <span style={{
                    fontSize: 12, fontWeight: 600, color: getFileColor(f.name),
                    fontFamily: "monospace",
                  }}>
                    {f.name}
                  </span>
                  <span style={{ fontSize: 10.5, color: C.textDim, marginLeft: 8 }}>
                    {f.desc.slice(0, 80)}...
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* File tree */}
        <div style={{
          background: C.panel,
          border: `1px solid ${C.panelBorder}`,
          borderRadius: 8,
          padding: "12px 14px",
          position: "relative",
        }}>
          <TreeNode
            node={TREE}
            depth={0}
            expanded={expanded}
            toggle={toggle}
            selectedFile={selectedFile}
            setSelectedFile={setSelectedFile}
            path="/opt/pib/"
          />
        </div>

        <div style={{
          marginTop: 14,
          fontSize: 9.5,
          color: C.textDim,
          textAlign: "center",
          fontFamily: "monospace",
        }}>
          pib-v5-build-spec.md §13.1 · Layer dots on right edge · Search to find files by name or content
        </div>
      </div>
    </div>
  );
}

const btnStyle = {
  fontSize: 9.5, padding: "5px 10px", borderRadius: 4,
  background: "transparent", border: `1px solid ${C.panelBorder}`,
  color: C.textMid, cursor: "pointer",
  fontFamily: "'JetBrains Mono', monospace",
};
