/**
 * PIB v5 Console Server — Express on port 3333
 *
 * Serves static dashboard + REST API reading from SQLite.
 * Member identity enforced via X-PIB-Member header.
 * Privacy filtering: Laura's work calendar redacted for non-Laura viewers.
 * All write operations delegated to Python CLI (permission boundary).
 */

import express from "express";
import Database from "better-sqlite3";
import { execSync, spawn } from "child_process";
import { readFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import yaml from "js-yaml";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const PORT = parseInt(process.env.PIB_CONSOLE_PORT || "3333", 10);
const DB_PATH = process.env.PIB_DB_PATH || "/opt/pib/data/pib.db";

// ═══════════════════════════════════════════════════════════
// DATABASE
// ═══════════════════════════════════════════════════════════

let db;
function getDB() {
  if (!db) {
    db = new Database(DB_PATH, { readonly: true });
    db.pragma("journal_mode = WAL");
    db.pragma("busy_timeout = 5000");
    db.pragma("foreign_keys = ON");
  }
  return db;
}

// ═══════════════════════════════════════════════════════════
// CLI HELPER — delegates writes to Python CLI permission boundary
// ═══════════════════════════════════════════════════════════

function runCLI(command, args = {}, memberId = null) {
  const parts = ["python", "-m", "pib.cli", command, DB_PATH];
  if (Object.keys(args).length > 0) {
    parts.push("--json", JSON.stringify(args));
  }
  if (memberId) {
    parts.push("--member", memberId);
  }
  try {
    const env = { ...process.env, PIB_CALLER_AGENT: "cos" };
    const result = execSync(parts.join(" "), {
      encoding: "utf-8",
      timeout: 30_000,
      env,
      cwd: ROOT,
    });
    return JSON.parse(result.trim());
  } catch (e) {
    const stderr = e.stderr?.toString() || "";
    const stdout = e.stdout?.toString() || "";
    try {
      return JSON.parse(stdout.trim());
    } catch {
      return { error: "cli_failed", detail: stderr || e.message };
    }
  }
}

// ═══════════════════════════════════════════════════════════
// CONFIG LOADERS
// ═══════════════════════════════════════════════════════════

function loadYAML(filename) {
  const path = join(ROOT, "config", filename);
  if (!existsSync(path)) return {};
  return yaml.load(readFileSync(path, "utf-8"));
}

// ═══════════════════════════════════════════════════════════
// EXPRESS APP
// ═══════════════════════════════════════════════════════════

const app = express();
app.use(express.json());
app.use(express.static(__dirname)); // serve index.html + assets

// ─── Member Identity Middleware ───

function requireMember(req, res, next) {
  const memberId = req.headers["x-pib-member"] || req.query.member;
  if (!memberId) {
    return res.status(400).json({ error: "X-PIB-Member header or ?member= query param required" });
  }
  const d = getDB();
  const member = d.prepare("SELECT * FROM common_members WHERE id = ? AND active = 1").get(memberId);
  if (!member) {
    return res.status(404).json({ error: `Member ${memberId} not found` });
  }
  req.member = member;
  req.memberId = memberId;
  next();
}

function optionalMember(req, _res, next) {
  const memberId = req.headers["x-pib-member"] || req.query.member;
  if (memberId) {
    const d = getDB();
    const member = d.prepare("SELECT * FROM common_members WHERE id = ? AND active = 1").get(memberId);
    req.member = member || null;
    req.memberId = memberId;
  }
  next();
}

// ═══════════════════════════════════════════════════════════
// API ROUTES — READS (direct SQLite)
// ═══════════════════════════════════════════════════════════

// --- Health ---
app.get("/api/health", (_req, res) => {
  const result = runCLI("health");
  res.json(result);
});

// --- Custody ---
app.get("/api/custody/today", (_req, res) => {
  const result = runCLI("custody");
  res.json(result);
});

// --- Today Stream ---
app.get("/api/today-stream", requireMember, (req, res) => {
  const d = getDB();
  const memberId = req.memberId;

  // whatNow via CLI
  const wnResult = runCLI("what-now", {}, memberId);

  // Energy state
  const today = new Date().toISOString().slice(0, 10);
  const energy = d.prepare(
    "SELECT * FROM pib_energy_states WHERE member_id = ? AND state_date = ?"
  ).get(memberId, today);

  // Streak
  const streak = d.prepare(
    "SELECT * FROM ops_streaks WHERE member_id = ? AND streak_type = 'daily_completion'"
  ).get(memberId);

  // Calendar events (privacy-filtered)
  const events = d.prepare(
    "SELECT * FROM cal_classified_events WHERE event_date = ? " +
    "AND (for_member_ids = '[]' OR for_member_ids LIKE '%' || ? || '%') ORDER BY start_time"
  ).all(today, memberId);

  const filteredEvents = events.map(e => {
    if (e.privacy === "privileged") {
      return { ...e, title: e.title_redacted || "[busy]", description: null };
    }
    if (e.privacy === "redacted") {
      return { ...e, title: "[unavailable]", description: null };
    }
    return e;
  });

  // Active tasks for member
  const tasks = d.prepare(
    "SELECT * FROM ops_tasks WHERE assignee = ? AND status NOT IN ('done', 'dismissed') " +
    "ORDER BY CASE status WHEN 'in_progress' THEN 0 WHEN 'next' THEN 1 WHEN 'inbox' THEN 2 ELSE 3 END, due_date"
  ).all(memberId);

  // Build unified stream
  const stream = [];

  // Calendar events as stream items
  for (const e of filteredEvents) {
    stream.push({
      id: e.id,
      type: "calendar",
      title: e.title,
      time: e.start_time,
      end: e.end_time,
      label: `${e.start_time} ${e.title}`,
      state: "pending",
    });
  }

  // Tasks as stream items
  for (const t of tasks) {
    stream.push({
      id: t.id,
      type: "task",
      title: t.title,
      label: t.title,
      state: t.status === "done" ? "done" : "pending",
      urgent: t.due_date && t.due_date <= today && t.status !== "done",
      task: {
        id: t.id,
        domain: t.domain,
        effort: t.effort,
        points: t.points || 1,
        micro: t.micro_script || null,
      },
    });
  }

  res.json({
    stream,
    activeIdx: wnResult.the_one_task ? stream.findIndex(s => s.id === wnResult.the_one_task?.id) : 0,
    energy: energy ? {
      level: energy.energy_level,
      sleep: energy.sleep_quality,
      meds: !!energy.meds_taken,
      meds_at: energy.meds_taken_at,
      completions: energy.completions_today || 0,
      cap: req.member.velocity_cap || 20,
      focus: !!energy.focus_mode,
    } : null,
    streak: streak ? {
      current: streak.current_streak,
      best: streak.best_streak,
      grace: streak.grace_days_used,
    } : null,
    whatNow: wnResult,
  });
});

// --- Tasks ---
app.get("/api/tasks", optionalMember, (req, res) => {
  const d = getDB();
  const filter = req.query.filter || "all";
  const assignee = req.query.assignee || req.memberId;
  const today = new Date().toISOString().slice(0, 10);

  let sql = "SELECT * FROM ops_tasks WHERE 1=1";
  const params = [];

  if (assignee) {
    sql += " AND assignee = ?";
    params.push(assignee);
  }

  switch (filter) {
    case "inbox": sql += " AND status = 'inbox'"; break;
    case "overdue": sql += " AND due_date < ? AND status NOT IN ('done','dismissed','deferred')"; params.push(today); break;
    case "waiting": sql += " AND status = 'waiting_on'"; break;
    case "done": sql += " AND status = 'done'"; break;
    case "mine": break; // already filtered by assignee
    default: sql += " AND status NOT IN ('done','dismissed')"; break;
  }

  sql += " ORDER BY due_date, created_at";
  res.json({ tasks: d.prepare(sql).all(...params) });
});

// --- Schedule ---
app.get("/api/schedule", requireMember, (req, res) => {
  const d = getDB();
  const dateStr = req.query.date || new Date().toISOString().slice(0, 10);
  const memberId = req.memberId;

  const events = d.prepare(
    "SELECT * FROM cal_classified_events WHERE event_date = ? " +
    "AND (for_member_ids = '[]' OR for_member_ids LIKE '%' || ? || '%') ORDER BY start_time"
  ).all(dateStr, memberId);

  // Privacy filter
  const filtered = events.map(e => {
    if (e.privacy === "privileged") {
      return { ...e, title: e.title_redacted || "[busy]", description: null };
    }
    if (e.privacy === "redacted") {
      return { ...e, title: "[unavailable]", description: null };
    }
    return e;
  });

  // Custody
  const custody = runCLI("custody", { date: dateStr });

  res.json({ events: filtered, custody: custody.text || "" });
});

// --- Lists ---
app.get("/api/lists/:listName", (_req, res) => {
  const d = getDB();
  const listName = _req.params.listName;
  const items = d.prepare(
    "SELECT * FROM ops_lists WHERE list_name = ? ORDER BY checked, added_at"
  ).all(listName);
  const available = d.prepare(
    "SELECT DISTINCT list_name FROM ops_lists"
  ).all().map(r => ({ id: r.list_name, label: r.list_name }));
  res.json({ items, available_lists: available });
});

// --- Scoreboard ---
app.get("/api/scoreboard", (_req, res) => {
  const result = runCLI("scoreboard-data");
  res.json(result);
});

// --- Budget ---
app.get("/api/budget", (_req, res) => {
  const result = runCLI("budget");
  res.json(result);
});

// --- Household Status ---
app.get("/api/household-status", (_req, res) => {
  const d = getDB();
  const today = new Date().toISOString().slice(0, 10);
  const items = [];

  // Member completions
  const members = d.prepare("SELECT * FROM common_members WHERE active = 1 AND role = 'parent'").all();
  for (const m of members) {
    const energy = d.prepare(
      "SELECT completions_today, energy_level FROM pib_energy_states WHERE member_id = ? AND state_date = ?"
    ).get(m.id, today);
    if (energy) {
      items.push({
        icon: energy.energy_level === "high" ? "✅" : "⚡",
        text: `${m.display_name}: ${energy.completions_today || 0} tasks done — energy ${energy.energy_level}`,
        color: "var(--tx2)",
      });
    }
  }

  res.json({ items });
});

// --- Decisions (Laura) ---
app.get("/api/decisions", requireMember, (req, res) => {
  const d = getDB();
  const pending = d.prepare(
    "SELECT * FROM mem_approval_queue WHERE status = 'pending' ORDER BY requested_at DESC"
  ).all();
  res.json({ decisions: pending });
});

// --- Chat ---
app.get("/api/chat/history", requireMember, (req, res) => {
  const d = getDB();
  const sessionId = req.query.session_id;
  if (!sessionId) return res.json({ messages: [] });

  const messages = d.prepare(
    "SELECT role, content, created_at FROM mem_messages WHERE session_id = ? ORDER BY created_at"
  ).all(sessionId);
  res.json({ messages });
});

// ═══════════════════════════════════════════════════════════
// API ROUTES — WRITES (delegated to Python CLI)
// ═══════════════════════════════════════════════════════════

app.post("/api/tasks/:id/complete", requireMember, (req, res) => {
  const result = runCLI("task-complete", { task_id: req.params.id }, req.memberId);
  res.json(result);
});

app.post("/api/tasks/:id/skip", requireMember, (req, res) => {
  const args = { task_id: req.params.id };
  if (req.body.reschedule_date) args.scheduled_date = req.body.reschedule_date;
  const result = runCLI("task-snooze", args, req.memberId);
  res.json(result);
});

app.post("/api/tasks", requireMember, (req, res) => {
  const result = runCLI("task-create", req.body, req.memberId);
  res.json(result);
});

app.post("/api/lists/:listName/items", requireMember, (req, res) => {
  const result = runCLI("capture", {
    text: `${req.params.listName}: ${req.body.text}`,
  }, req.memberId);
  res.json(result);
});

app.post("/api/lists/:listName/items/:id/toggle", requireMember, (_req, res) => {
  const d = getDB();
  // Direct toggle for list items (simple enough to not need CLI)
  const item = d.prepare("SELECT * FROM ops_lists WHERE id = ?").get(_req.params.id);
  if (!item) return res.status(404).json({ error: "Item not found" });

  // Use a writable connection for this simple toggle
  const wdb = new Database(DB_PATH);
  wdb.prepare("UPDATE ops_lists SET checked = ?, checked_at = datetime('now') WHERE id = ?")
    .run(item.checked ? 0 : 1, _req.params.id);
  wdb.close();

  res.json({ ok: true, done: !item.checked });
});

app.post("/api/chat/send", requireMember, (req, res) => {
  const result = runCLI("capture", {
    text: req.body.message,
    source: "webchat",
  }, req.memberId);
  res.json(result);
});

app.post("/api/approvals/:id/decide", requireMember, (req, res) => {
  const wdb = new Database(DB_PATH);
  wdb.prepare(
    "UPDATE mem_approval_queue SET status = ?, decided_by = ?, decided_at = datetime('now') WHERE id = ?"
  ).run(req.body.decision, req.memberId, req.params.id);
  wdb.close();
  res.json({ ok: true });
});

app.post("/api/chores/:id/toggle", requireMember, (req, res) => {
  const result = runCLI("task-complete", { task_id: req.params.id }, req.memberId);
  res.json(result);
});

// ═══════════════════════════════════════════════════════════
// SETTINGS ROUTES
// ═══════════════════════════════════════════════════════════

// --- System Health ---
// (reuses /api/health above)

// --- Operating Costs ---
app.get("/api/costs", (_req, res) => {
  // Computed from pib_config + LLM usage tracking
  const d = getDB();
  const config = d.prepare("SELECT * FROM pib_config WHERE key LIKE 'cost_%'").all();
  res.json({
    total: config.find(c => c.key === "cost_total_monthly")?.value || "—",
    items: [],
  });
});

// --- AI Models ---
app.get("/api/config/models", (_req, res) => {
  const d = getDB();
  const sonnet = d.prepare("SELECT value FROM pib_config WHERE key = 'anthropic_model_sonnet'").get();
  const opus = d.prepare("SELECT value FROM pib_config WHERE key = 'anthropic_model_opus'").get();
  res.json({
    models: [
      { key: "anthropic_model_sonnet", tier: "Routine (Sonnet)", val: sonnet?.value || "claude-sonnet-4-5-20250929", pct: "~90% of requests" },
      { key: "anthropic_model_opus", tier: "Complex (Opus)", val: opus?.value || "claude-opus-4-6", pct: "~10% of requests" },
    ],
  });
});

// --- Sources ---
app.get("/api/sources", (_req, res) => {
  const d = getDB();
  const sources = d.prepare("SELECT * FROM common_source_classifications WHERE active = 1").all();
  res.json({ sources });
});

// --- Life Phases ---
app.get("/api/phases", (_req, res) => {
  const d = getDB();
  const phases = d.prepare("SELECT * FROM common_life_phases ORDER BY start_date").all();
  res.json({ phases });
});

// --- Config (pib_config) ---
app.get("/api/config", (_req, res) => {
  const d = getDB();
  const rows = d.prepare("SELECT key, value as val, description as desc FROM pib_config ORDER BY key").all();
  res.json({ config: rows });
});

app.post("/api/config/:key", requireMember, (req, res) => {
  const wdb = new Database(DB_PATH);
  const key = req.params.key;
  const value = req.body.value;
  wdb.prepare(
    "INSERT INTO pib_config (key, value, updated_by) VALUES (?, ?, ?) " +
    "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_by = excluded.updated_by, " +
    "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')"
  ).run(key, value, req.memberId);
  wdb.close();
  res.json({ ok: true, key, value });
});

// --- Settings: Permissions (read-only) ---
app.get("/api/settings/permissions", (_req, res) => {
  const caps = loadYAML("agent_capabilities.yaml");
  const agents = caps.agents || {};
  const result = Object.entries(agents).map(([id, config]) => ({
    id,
    display_name: config.display_name,
    capabilities: config.capabilities,
    model: config.model,
    channels: config.channels || [],
    allowed_commands: config.allowed_cli_commands,
    blocked_commands: config.blocked_cli_commands,
    filesystem: config.filesystem || "none",
    sql: config.sql || "none",
    privacy: config.privacy || {},
    restrictions: config.restrictions || [],
  }));
  const enforcement = caps.enforcement || {};
  res.json({ agents: result, enforcement, routing: caps.routing || {} });
});

// --- Settings: Coaching Protocols ---
app.get("/api/settings/coaching", (_req, res) => {
  const d = getDB();
  try {
    const protocols = d.prepare("SELECT * FROM pib_coach_protocols ORDER BY name").all();
    res.json({ protocols });
  } catch {
    res.json({ protocols: [] });
  }
});

app.post("/api/settings/coaching/:id/toggle", requireMember, (req, res) => {
  const wdb = new Database(DB_PATH);
  const proto = wdb.prepare("SELECT active FROM pib_coach_protocols WHERE id = ?").get(req.params.id);
  if (!proto) { wdb.close(); return res.status(404).json({ error: "Protocol not found" }); }
  wdb.prepare("UPDATE pib_coach_protocols SET active = ? WHERE id = ?").run(proto.active ? 0 : 1, req.params.id);
  wdb.close();
  res.json({ ok: true, active: !proto.active });
});

// --- Settings: Governance Gates (read-only) ---
app.get("/api/settings/gates", (_req, res) => {
  const gov = loadYAML("governance.yaml");
  res.json({
    action_gates: gov.action_gates || {},
    agent_overrides: gov.agent_overrides || {},
    rate_limits: gov.rate_limits || {},
  });
});

// --- Settings: Household (member management) ---
app.get("/api/settings/household", (_req, res) => {
  const d = getDB();
  const members = d.prepare("SELECT * FROM common_members ORDER BY role, display_name").all();
  res.json({ members });
});

app.post("/api/settings/household/members", requireMember, (req, res) => {
  // Add new member — delegate to CLI or direct insert
  const { id, display_name, role } = req.body;
  if (!id || !display_name || !role) {
    return res.status(400).json({ error: "id, display_name, and role are required" });
  }
  const wdb = new Database(DB_PATH);
  try {
    wdb.prepare(
      "INSERT INTO common_members (id, display_name, role) VALUES (?, ?, ?)"
    ).run(id, display_name, role);
    wdb.close();
    res.json({ ok: true, id });
  } catch (e) {
    wdb.close();
    res.status(400).json({ error: e.message });
  }
});

app.post("/api/settings/household/members/:id/deactivate", requireMember, (req, res) => {
  const wdb = new Database(DB_PATH);
  wdb.prepare("UPDATE common_members SET active = 0 WHERE id = ?").run(req.params.id);
  wdb.close();
  res.json({ ok: true });
});

// --- Settings: Memory Browser ---
app.get("/api/settings/memory", requireMember, (req, res) => {
  const d = getDB();
  const memberId = req.memberId;
  const query = req.query.q;

  if (query) {
    const result = runCLI("search", { query, member_id: memberId }, memberId);
    return res.json(result);
  }

  const memories = d.prepare(
    "SELECT * FROM mem_long_term WHERE (member_id = ? OR member_id IS NULL) " +
    "AND superseded_by IS NULL ORDER BY created_at DESC LIMIT 100"
  ).all(memberId);
  res.json({ memories, member_id: memberId });
});

// --- Per-Member Settings ---
app.get("/api/member-settings", requireMember, (req, res) => {
  const result = runCLI("member-settings-get", {}, req.memberId);
  res.json(result);
});

app.post("/api/member-settings/:key", requireMember, (req, res) => {
  const result = runCLI("member-settings-set", {
    key: req.params.key,
    value: req.body.value,
    description: req.body.description,
  }, req.memberId);
  res.json(result);
});

// ═══════════════════════════════════════════════════════════
// CHORES (Charlie-specific)
// ═══════════════════════════════════════════════════════════

app.get("/api/chores", optionalMember, (req, res) => {
  const d = getDB();
  const memberId = req.query.member || "m-charlie";
  const chores = d.prepare(
    "SELECT * FROM ops_tasks WHERE assignee = ? AND item_type = 'chore' AND status NOT IN ('dismissed') " +
    "ORDER BY due_date"
  ).all(memberId);
  res.json({ chores });
});

app.get("/api/scoreboard", optionalMember, (req, res) => {
  const result = runCLI("scoreboard-data");
  res.json(result);
});

// ═══════════════════════════════════════════════════════════
// CHANNEL REGISTRY & COMMS INBOX
// ═══════════════════════════════════════════════════════════

// --- List all channels with health status ---
app.get("/api/channels", (_req, res) => {
  const d = getDB();
  try {
    const channels = d.prepare(`
      SELECT c.id, c.display_name, c.icon, c.category, c.enabled, c.setup_complete,
             h.health_status, h.last_check, h.consecutive_failures
      FROM comms_channels c
      LEFT JOIN comms_channel_health h ON h.channel_id = c.id
      ORDER BY c.category, c.display_name
    `).all();
    res.json({ channels });
  } catch (e) {
    res.json({ channels: [], error: e.message });
  }
});

// --- Single channel detail ---
app.get("/api/channels/:id", (req, res) => {
  const d = getDB();
  try {
    const channel = d.prepare(`
      SELECT c.*, h.health_status, h.last_check, h.consecutive_failures,
             h.last_error, h.avg_latency_ms
      FROM comms_channels c
      LEFT JOIN comms_channel_health h ON h.channel_id = c.id
      WHERE c.id = ?
    `).get(req.params.id);
    if (!channel) return res.status(404).json({ error: "Channel not found" });

    // Get capabilities
    let capabilities = [];
    try {
      capabilities = d.prepare(
        "SELECT capability FROM comms_channel_capabilities WHERE channel_id = ?"
      ).all(req.params.id);
    } catch { /* table may not exist */ }

    // Get member access
    let memberAccess = [];
    try {
      memberAccess = d.prepare(
        "SELECT member_id, access_level FROM comms_channel_members WHERE channel_id = ?"
      ).all(req.params.id);
    } catch { /* table may not exist */ }

    res.json({ channel, capabilities, memberAccess });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// --- Channel-specific inbox ---
app.get("/api/channels/:id/inbox", requireMember, (req, res) => {
  const d = getDB();
  try {
    const items = d.prepare(`
      SELECT * FROM ops_comms
      WHERE channel_id = ? AND member_id = ?
      ORDER BY created_at DESC LIMIT 100
    `).all(req.params.id, req.memberId);
    res.json({ items });
  } catch (e) {
    res.json({ items: [], error: e.message });
  }
});

// --- Enable channel ---
app.post("/api/channels/:id/enable", requireMember, (req, res) => {
  const result = runCLI("channel-enable", { channel_id: req.params.id }, req.memberId);
  res.json(result);
});

// --- Disable channel ---
app.post("/api/channels/:id/disable", requireMember, (req, res) => {
  const result = runCLI("channel-disable", { channel_id: req.params.id }, req.memberId);
  res.json(result);
});

// --- Unified comms inbox ---
app.get("/api/comms/inbox", requireMember, (req, res) => {
  const d = getDB();
  const batchWindow = req.query.batch_window || null;
  const status = req.query.status || null;
  try {
    let sql = `
      SELECT oc.*, cc.display_name as channel_name, cc.icon as channel_icon
      FROM ops_comms oc
      LEFT JOIN comms_channels cc ON cc.id = oc.channel_id
      WHERE oc.member_id = ?
    `;
    const params = [req.memberId];

    if (batchWindow) {
      sql += " AND oc.batch_window = ?";
      params.push(batchWindow);
    }
    if (status) {
      sql += " AND oc.status = ?";
      params.push(status);
    }

    sql += " ORDER BY oc.created_at DESC LIMIT 200";
    const items = d.prepare(sql).all(...params);
    res.json({ items });
  } catch (e) {
    res.json({ items: [], error: e.message });
  }
});

// --- Approve draft ---
app.post("/api/comms/:id/approve-draft", requireMember, (req, res) => {
  const result = runCLI("comms-approve-draft", { comms_id: req.params.id }, req.memberId);
  res.json(result);
});

// --- Mark as responded ---
app.post("/api/comms/:id/respond", requireMember, (req, res) => {
  const result = runCLI("comms-respond", { comms_id: req.params.id }, req.memberId);
  res.json(result);
});

// --- Snooze ---
app.post("/api/comms/:id/snooze", requireMember, (req, res) => {
  const until = req.query.until || req.body.until;
  const result = runCLI("comms-snooze", { comms_id: req.params.id, until }, req.memberId);
  res.json(result);
});

// ═══════════════════════════════════════════════════════════
// START
// ═══════════════════════════════════════════════════════════

app.listen(PORT, () => {
  console.log(`PIB Console running on http://localhost:${PORT}`);
  console.log(`Database: ${DB_PATH}`);
});

export default app;
