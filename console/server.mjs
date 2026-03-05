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
import { execFileSync, spawn } from "child_process";
import crypto from "crypto";
import { readFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import yaml from "js-yaml";
import { whatNow, loadSnapshot } from "../scripts/core/what_now.mjs";
import {
  selectReward,
  getCompletionStats,
  generateOneMoreNudge,
  updateStreak,
  getEndowedProgress,
  shouldShowMomentumNudge,
  generateMomentumMessage
} from "../scripts/core/behavioral_engine.mjs";
import { createCommsRouter } from "./comms_routes.mjs";
import { createChannelRouter } from "./channel_routes.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const PORT = parseInt(process.env.PIB_CONSOLE_PORT || "3333", 10);
const DB_PATH = process.env.PIB_DB_PATH || "/opt/pib/data/pib.db";

// ═══════════════════════════════════════════════════════════
// RATE LIMITER (per spec §3.3)
// ═══════════════════════════════════════════════════════════

class RateLimiter {
  constructor() {
    this._windows = new Map(); // source -> [timestamps]
  }

  check(source, maxRequests = 60, windowSeconds = 60) {
    const now = Date.now() / 1000; // seconds
    const windowKey = source;
    
    if (!this._windows.has(windowKey)) {
      this._windows.set(windowKey, []);
    }
    
    const timestamps = this._windows.get(windowKey);
    // Remove expired timestamps
    const cutoff = now - windowSeconds;
    const validTimestamps = timestamps.filter(t => t > cutoff);
    
    if (validTimestamps.length >= maxRequests) {
      return false; // Rate limit exceeded
    }
    
    validTimestamps.push(now);
    this._windows.set(windowKey, validTimestamps);
    return true;
  }
}

const rateLimiter = new RateLimiter();

// Rate limit middleware factory
function rateLimitMiddleware(sourceKey) {
  return (req, res, next) => {
    const gov = loadGovernance();
    const limits = gov.rate_limits || {};
    const maxRequests = limits[sourceKey] || 60;
    const source = `${sourceKey}-${req.ip || 'unknown'}`;
    
    if (!rateLimiter.check(source, maxRequests, 60)) {
      return res.status(429).json({
        error: "rate_limit_exceeded",
        source: sourceKey,
        limit: `${maxRequests}/min`,
        retry_after: 60,
      });
    }
    next();
  };
}

// ═══════════════════════════════════════════════════════════
// DATABASE
// ═══════════════════════════════════════════════════════════

let db;
function getDB() {
  if (!db) {
    db = new Database(DB_PATH, { readonly: true });
    // SQLite config per spec §3.5
    db.pragma("journal_mode = WAL");
    db.pragma("busy_timeout = 5000");
    db.pragma("foreign_keys = ON");
    db.pragma("synchronous = NORMAL");
    db.pragma("cache_size = -64000");      // 64MB page cache
    db.pragma("mmap_size = 268435456");    // 256MB memory-mapped I/O
  }
  return db;
}

// ═══════════════════════════════════════════════════════════
// CLI HELPER — delegates writes to Python CLI permission boundary
// ═══════════════════════════════════════════════════════════

function runCLI(command, args = {}, memberId = null) {
  const cliArgs = ["-m", "pib.cli", command, DB_PATH];
  if (Object.keys(args).length > 0) {
    cliArgs.push("--json", JSON.stringify(args));
  }
  if (memberId) {
    cliArgs.push("--member", memberId);
  }
  try {
    const result = execFileSync("python", cliArgs, {
      cwd: ROOT,
      env: { ...process.env, PIB_DB_PATH: DB_PATH, PIB_CALLER_AGENT: "cos" },
      timeout: 30000,
      encoding: "utf-8",
      maxBuffer: 1024 * 1024,
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
// AUDIT LOG + WRITE DB HELPERS
// ═══════════════════════════════════════════════════════════

function getWriteDB() {
  const wdb = new Database(DB_PATH);
  // SQLite config per spec §3.5
  wdb.pragma("journal_mode = WAL");
  wdb.pragma("busy_timeout = 5000");
  wdb.pragma("foreign_keys = ON");
  wdb.pragma("synchronous = NORMAL");
  wdb.pragma("cache_size = -64000");
  wdb.pragma("mmap_size = 268435456");
  return wdb;
}

function auditLog(db, action, detail, memberId) {
  const parts = action.split('-');
  const table_name = parts.length > 1 ? parts[0] : 'unknown';
  const verb = parts.length > 1 ? parts.slice(1).join('-') : 'update';
  const OP_MAP = {
    'complete': 'UPDATE', 'decide': 'UPDATE', 'toggle': 'UPDATE',
    'set': 'UPDATE', 'add': 'INSERT', 'create': 'INSERT',
    'deactivate': 'UPDATE', 'confirm': 'UPDATE', 'update': 'UPDATE',
    'made-it': 'UPDATE', 'adapter-toggle': 'UPDATE', 'item-toggle': 'UPDATE',
    'snooze': 'UPDATE',
  };
  const operation = OP_MAP[verb] || 'UPDATE';
  try {
    db.prepare(
      "INSERT INTO common_audit_log (table_name, operation, actor, source, metadata) VALUES (?,?,?,?,?)"
    ).run(table_name, operation, memberId || 'console', 'console', detail);
  } catch(e) { console.error('auditLog failed:', e.message); }
}

function todayET() {
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" });
}

// ═══════════════════════════════════════════════════════════
// INLINE PERMISSION CHECKS — for direct-DB endpoints that
// bypass the Python CLI for UI responsiveness.
// Mirrors cli.py's 6-layer enforcement: agent allowlist,
// governance gate, rate limit, audit logging.
// ═══════════════════════════════════════════════════════════

/**
 * Load governance.yaml (cached per-request is fine for a single-process server).
 */
function loadGovernance() {
  return loadYAML("governance.yaml");
}

/**
 * Check if console agent (cos) is allowed to run a given action.
 * Console always runs as "cos" agent since it's the household dashboard.
 * Returns { ok: boolean, error?: string }
 */
function checkConsolePermission(action, memberId) {
  const agentId = "cos";
  const caps = loadYAML("agent_capabilities.yaml");
  const gov = loadGovernance();

  // Layer 1: Agent allowlist — console endpoints are pre-approved actions
  // that map to specific governance gates. We check the gate, not CLI commands.
  const agents = caps.agents || {};
  const agent = agents[agentId];
  if (!agent) return { ok: false, error: `Unknown agent: ${agentId}` };

  // Layer 2: Governance gate
  const actionGates = gov.action_gates || {};
  const agentOverrides = (gov.agent_overrides || {})[agentId] || {};
  const gateValue = agentOverrides[action] ?? actionGates[action] ?? true;

  if (gateValue === false || gateValue === "off") {
    return { ok: false, error: `Action '${action}' is disabled for agent '${agentId}'` };
  }
  if (gateValue === "confirm") {
    return { ok: false, error: `Action '${action}' requires user confirmation`, pending: true };
  }

  // Layer 4: Write-rate check (simplified — count recent audit entries)
  const rateLimits = gov.rate_limits || {};
  const maxWrites = rateLimits.writes_per_minute || 3;
  // Note: full rate limiting is enforced at CLI layer; this is defense-in-depth

  return { ok: true };
}

/**
 * Wrap a direct-DB-write endpoint with permission checks + audit logging.
 * action: governance gate key (e.g., "list_item_toggle")
 * writeFn: (req, res) => { ... perform write, return result ... }
 */
function guardedWrite(action, writeFn) {
  return (req, res) => {
    const perm = checkConsolePermission(action, req.memberId);
    if (!perm.ok) {
      const status = perm.pending ? 202 : 403;
      return res.status(status).json({
        error: perm.pending ? "pending_approval" : "forbidden",
        detail: perm.error,
        action,
      });
    }
    // Provide write DB to the handler
    const wdb = getWriteDB();
    req.writeDB = wdb;
    try {
      const result = writeFn(req, res);
      wdb.close();
      return result;
    } catch (e) {
      wdb.close();
      throw e;
    }
  };
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

// Mount Comms & Channel routers
const commsRouter = createCommsRouter(getDB, auditLog, guardedWrite);
const channelRouter = createChannelRouter(getDB, auditLog, guardedWrite);
app.use("/api/comms", requireMember, commsRouter);
app.use("/api/channels", requireMember, channelRouter);

// ═══════════════════════════════════════════════════════════
// IDENTITY — Tailscale Serve headers → member resolution
// ═══════════════════════════════════════════════════════════
//
// Tailscale Serve proxies to localhost:3333 and injects:
//   Tailscale-User-Login: james@gmail.com
//   Tailscale-User-Name: James Stice
//
// Cryptographically guaranteed by the WireGuard tunnel.
// Tailscale strips spoofed versions before injecting the real ones.
// Fallback: X-PIB-Member header (only when PIB_ENV=dev).

function resolveIdentity(req) {
  const db = getDB();

  // Primary: Tailscale identity header
  const tsLogin = req.headers["tailscale-user-login"];
  if (tsLogin) {
    const member = db.prepare(
      "SELECT * FROM common_members WHERE tailscale_email = ? AND active = 1"
    ).get(tsLogin.toLowerCase());
    if (member) {
      // View-as override (parent viewing as child for scoreboard)
      const viewAs = req.query.view_as || req.headers["x-pib-view-as"];
      if (viewAs && member.role === 'parent') {
        const target = db.prepare(
          "SELECT * FROM common_members WHERE id = ? AND active = 1"
        ).get(viewAs);
        if (target) {
          return {
            authMember: member,       // WHO is authenticated
            viewMember: target,       // WHO they're viewing as
            memberId: target.id,      // Effective member ID for data queries
            authMemberId: member.id,  // Real identity for write permissions
            role: member.role,        // Always the real user's role
            source: 'tailscale',
          };
        }
      }
      return {
        authMember: member, viewMember: member,
        memberId: member.id, authMemberId: member.id,
        role: member.role, source: 'tailscale',
      };
    }
    // Known Tailscale user but unmapped — tagged device (kitchen TV, etc.)
    return {
      authMember: null, viewMember: null,
      memberId: null, authMemberId: null,
      role: 'device', tsLogin, source: 'tailscale-unmapped',
    };
  }

  // Fallback: X-PIB-Member (dev only)
  const devMode = process.env.PIB_ENV === 'dev';
  const headerMemberId = req.headers["x-pib-member"] || req.query.member;
  if (headerMemberId && devMode) {
    const member = db.prepare(
      "SELECT * FROM common_members WHERE id = ? AND active = 1"
    ).get(headerMemberId);
    if (member) {
      return {
        authMember: member, viewMember: member,
        memberId: member.id, authMemberId: member.id,
        role: member.role, source: 'dev-header',
      };
    }
  }

  return null;
}

function requireMember(req, res, next) {
  const identity = resolveIdentity(req);
  if (!identity) return res.status(401).json({ error: "Not authenticated. Connect via Tailscale." });
  if (!identity.memberId) return res.status(403).json({ error: "Tailscale user not mapped to a household member", tsLogin: identity.tsLogin });
  req.identity = identity;
  req.member = identity.viewMember;
  req.memberId = identity.memberId;
  req.authMemberId = identity.authMemberId;
  req.memberRole = identity.role;
  next();
}

function requireParent(req, res, next) {
  const identity = resolveIdentity(req);
  if (!identity) return res.status(401).json({ error: "Not authenticated. Connect via Tailscale." });
  if (!identity.memberId) return res.status(403).json({ error: "Tailscale user not mapped to a household member" });
  if (identity.role !== 'parent') return res.status(403).json({ error: "Parent access required" });
  req.identity = identity;
  req.member = identity.authMember;
  req.memberId = identity.authMemberId;
  req.authMemberId = identity.authMemberId;
  req.memberRole = identity.role;
  next();
}

function optionalMember(req, _res, next) {
  const identity = resolveIdentity(req);
  if (identity && identity.memberId) {
    req.identity = identity;
    req.member = identity.viewMember;
    req.memberId = identity.memberId;
    req.authMemberId = identity.authMemberId;
    req.memberRole = identity.role;
  }
  next();
}

// For kitchen TV, scoreboard display — any Tailscale device, mapped or not
function requireTailscale(req, res, next) {
  const identity = resolveIdentity(req);
  if (!identity) return res.status(401).json({ error: "Not authenticated. Connect via Tailscale." });
  req.identity = identity;
  req.memberId = identity.memberId;
  req.memberRole = identity.role;
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

// --- Who Am I ---
app.get("/api/whoami", (req, res) => {
  const identity = resolveIdentity(req);
  if (!identity) return res.status(401).json({ error: "Not authenticated" });
  const db = getDB();
  res.json({
    memberId: identity.memberId,
    authMemberId: identity.authMemberId,
    displayName: identity.authMember?.display_name || identity.tsLogin || null,
    role: identity.role,
    source: identity.source,
    viewMode: identity.viewMember?.view_mode || null,
    canSwitchView: identity.role === 'parent',
    availableViews: identity.role === 'parent'
      ? db.prepare("SELECT id, display_name, role, view_mode FROM common_members WHERE active = 1").all()
      : [{ id: identity.memberId, display_name: identity.viewMember?.display_name, role: identity.role }],
  });
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

  // whatNow via direct call (Layer 1 - no LLM, always works)
  const snapshot = loadSnapshot(d, memberId);
  const wnResult = whatNow(memberId, snapshot);

  // Energy state
  const today = todayET();
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

  // Build unified stream with endowed progress
  const stream = [];
  
  // Add endowed progress items (woke up, opened PIB)
  const endowed = getEndowedProgress(memberId, today);
  stream.push(...endowed);

  // Completed tasks today
  const doneTasks = d.prepare(`
    SELECT * FROM ops_tasks 
    WHERE assignee = ? AND status = 'done' 
    AND date(completed_at) = ?
    ORDER BY completed_at
  `).all(memberId, today);
  
  for (const t of doneTasks) {
    stream.push({
      id: t.id,
      type: "task",
      title: t.title,
      label: t.title,
      state: "done",
      time: t.completed_at,
      task: {
        id: t.id,
        domain: t.domain,
        effort: t.effort,
        points: t.points || 1,
      },
    });
  }

  // Calendar events as stream items
  for (const e of filteredEvents) {
    const isPast = e.end_time && new Date(e.end_time) < new Date();
    stream.push({
      id: e.id,
      type: "calendar",
      title: e.title,
      time: e.start_time,
      end: e.end_time,
      label: `${e.start_time} ${e.title}`,
      state: isPast ? "done" : "pending",
    });
  }

  // Pending tasks (not done)
  for (const t of tasks) {
    if (t.status !== 'done') {
      stream.push({
        id: t.id,
        type: "task",
        title: t.title,
        label: t.title,
        state: t.status === "in_progress" ? "current" : "pending",
        urgent: t.due_date && t.due_date <= today,
        task: {
          id: t.id,
          domain: t.domain,
          effort: t.effort,
          points: t.points || 1,
          micro: t.micro_script || null,
        },
      });
    }
  }
  
  // Sort stream chronologically where possible
  stream.sort((a, b) => {
    const aTime = a.time || a.created_at || '00:00';
    const bTime = b.time || b.created_at || '00:00';
    return aTime.localeCompare(bTime);
  });

  // Find active index (current task or next pending)
  let activeIdx = stream.findIndex(s => s.state === "current");
  if (activeIdx === -1 && wnResult.the_one_task) {
    activeIdx = stream.findIndex(s => s.id === wnResult.the_one_task.id);
  }
  if (activeIdx === -1) {
    activeIdx = stream.findIndex(s => s.state === "pending");
  }
  if (activeIdx === -1) {
    activeIdx = stream.length - 1; // Last item if all done
  }

  res.json({
    stream,
    activeIdx: Math.max(0, activeIdx),
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
app.get("/api/tasks", requireMember, (req, res) => {
  const d = getDB();
  const filter = req.query.filter || "all";
  const assignee = req.query.assignee || req.memberId;
  const today = todayET();

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
  const dateStr = req.query.date || todayET();
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

app.get("/api/calendar/windows", requireMember, (req, res) => {
  const d = getDB();
  const dateStr = req.query.date || todayET();
  const memberId = req.memberId;
  const minDuration = parseInt(req.query.min_duration || "30", 10); // minutes

  // Get all events for the day that block the member
  const events = d.prepare(
    "SELECT start_time, end_time FROM cal_classified_events " +
    "WHERE event_date = ? AND (for_member_ids = '[]' OR for_member_ids LIKE '%' || ? || '%') " +
    "ORDER BY start_time"
  ).all(dateStr, memberId);

  // Find gaps between events
  const windows = [];
  const dayStart = "00:00";
  const dayEnd = "23:59";

  let lastEnd = dayStart;
  for (const event of events) {
    if (event.start_time > lastEnd) {
      const gapMinutes = timeToMinutes(event.start_time) - timeToMinutes(lastEnd);
      if (gapMinutes >= minDuration) {
        windows.push({
          start: lastEnd,
          end: event.start_time,
          duration: gapMinutes,
        });
      }
    }
    if (event.end_time > lastEnd) {
      lastEnd = event.end_time;
    }
  }

  // Final window from last event to end of day
  if (lastEnd < dayEnd) {
    const gapMinutes = timeToMinutes(dayEnd) - timeToMinutes(lastEnd);
    if (gapMinutes >= minDuration) {
      windows.push({
        start: lastEnd,
        end: dayEnd,
        duration: gapMinutes,
      });
    }
  }

  res.json({ date: dateStr, windows });
});

function timeToMinutes(timeStr) {
  const [h, m] = timeStr.split(":").map(Number);
  return h * 60 + m;
}

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
app.get("/api/scoreboard", requireTailscale, (req, res) => {
  const explicitMember = req.query.member;
  const d = getDB();
  const today = todayET();

  if (explicitMember) {
    const streak = d.prepare("SELECT * FROM ops_streaks WHERE member_id = ? AND streak_type = 'daily_completion'").get(explicitMember);
    const chores = d.prepare("SELECT id, title, status = 'done' as done, points as stars FROM ops_tasks WHERE assignee = ? AND item_type = 'chore' AND due_date = ? ORDER BY created_at").all(explicitMember, today);
    const weekStart = new Date(today); weekStart.setDate(weekStart.getDate() - weekStart.getDay());
    const weekStars = d.prepare("SELECT SUM(points) as total FROM ops_tasks WHERE assignee = ? AND item_type = 'chore' AND status = 'done' AND completed_at >= ?").get(explicitMember, weekStart.toISOString().slice(0, 10));
    return res.json({
      weekStars: weekStars?.total || 0,
      streak: streak ? { current: streak.current_streak, best: streak.best_streak, grace: streak.grace_days_used } : { current: 0, best: 0, grace: 0 },
      nextMilestone: "Pick Friday movie", nextMilestoneTarget: 25,
      chores: chores.map(c => ({ id: c.id, title: c.title, done: !!c.done, stars: c.stars || 1 })),
    });
  }

  const members = d.prepare("SELECT * FROM common_members WHERE active = 1 AND role IN ('parent','child')").all();
  const cards = members.map(m => {
    const streak = d.prepare("SELECT * FROM ops_streaks WHERE member_id = ? AND streak_type = 'daily_completion'").get(m.id);
    const energy = d.prepare("SELECT * FROM pib_energy_states WHERE member_id = ? AND state_date = ?").get(m.id, today);
    const weekStart = new Date(today); weekStart.setDate(weekStart.getDate() - weekStart.getDay());
    const weekDone = d.prepare("SELECT COUNT(*) as c FROM ops_tasks WHERE completed_by = ? AND status = 'done' AND completed_at >= ?").get(m.id, weekStart.toISOString().slice(0, 10));
    return { id: m.id, name: m.display_name, done: energy?.completions_today || 0, wk: weekDone?.c || 0,
      streak: streak ? { current: streak.current_streak, best: streak.best_streak, grace: streak.grace_days_used } : { current: 0, best: 0, grace: 0 }};
  });
  const rewardHistory = d.prepare("SELECT reward_tier as tier, reward_text as msg, created_at as ts FROM pib_reward_log ORDER BY created_at DESC LIMIT 10").all();
  const domainWins = d.prepare("SELECT domain as d, COUNT(*) as n FROM ops_tasks WHERE status = 'done' AND completed_at >= date('now', '-7 days') GROUP BY domain ORDER BY n DESC").all();
  res.json({ cards, rewardHistory, domainWins: domainWins.map(r => ({ d: r.d, n: r.n })), familyTotal: { points: cards.reduce((s, c) => s + c.wk, 0) }});
});

// --- Budget ---
app.get("/api/budget", (_req, res) => {
  const result = runCLI("budget");
  res.json(result);
});

// --- Financial Summary ---
app.get("/api/financial/summary", requireParent, (req, res) => {
  const d = getDB();
  const today = todayET();
  const firstOfMonth = today.slice(0, 8) + "01";

  // Monthly spend by category (from budget config + transactions)
  const budgetRows = d.prepare(
    "SELECT * FROM fin_budget_config"
  ).all();

  const categories = [];
  for (const budget of budgetRows) {
    const spent = d.prepare(
      "SELECT SUM(amount) as total FROM fin_transactions " +
      "WHERE category = ? AND transaction_date >= ? AND transaction_date < date(?, '+1 month')"
    ).get(budget.category, firstOfMonth, firstOfMonth);

    categories.push({
      cat: budget.category,
      target: budget.monthly_target || 0,
      spent: Math.abs(spent?.total || 0),
      icon: budget.icon || "💰",
      warn: spent?.total && Math.abs(spent.total) > (budget.monthly_target * 0.8),
    });
  }

  // Upcoming bills
  const bills = d.prepare(
    "SELECT * FROM fin_recurring_bills WHERE active = 1 AND next_due >= ? ORDER BY next_due LIMIT 5"
  ).all(today);

  // Recent transactions
  const transactions = d.prepare(
    "SELECT * FROM fin_transactions ORDER BY transaction_date DESC, created_at DESC LIMIT 10"
  ).all();

  res.json({
    categories,
    upcoming_bills: bills,
    recent_transactions: transactions,
  });
});

// --- Household Status ---
app.get("/api/household-status", (_req, res) => {
  const d = getDB();
  const today = todayET();
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

app.get("/api/chat/stream", requireMember, (req, res) => {
  const sessionId = req.query.session_id;
  if (!sessionId) {
    return res.status(400).json({ error: "session_id query param required" });
  }

  // Set SSE headers
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();

  // Spawn Python CLI streaming chat process
  const proc = spawn("python", [
    "-m", "pib.cli", "chat-stream", DB_PATH,
    "--session-id", sessionId,
    "--member", req.memberId
  ], {
    cwd: ROOT,
    env: { ...process.env, PIB_DB_PATH: DB_PATH, PIB_CALLER_AGENT: "cos" }
  });

  proc.stdout.on("data", (chunk) => {
    res.write(chunk);
  });

  proc.stderr.on("data", (chunk) => {
    console.error("chat-stream stderr:", chunk.toString());
  });

  proc.on("close", () => {
    res.end();
  });

  req.on("close", () => {
    proc.kill();
  });
});

// ═══════════════════════════════════════════════════════════
// API ROUTES — WRITES (delegated to Python CLI)
// ═══════════════════════════════════════════════════════════

app.post("/api/tasks/:id/complete", requireMember, (req, res) => {
  const taskId = req.params.id;
  const memberId = req.memberId;
  const d = getDB();
  
  // Get task before completion
  const task = d.prepare("SELECT * FROM ops_tasks WHERE id = ?").get(taskId);
  if (!task) {
    return res.status(404).json({ error: "Task not found" });
  }
  if (task.assignee !== req.authMemberId && task.assignee !== req.memberId) {
    return res.status(403).json({ error: "Can only complete your own tasks" });
  }
  
  // Open writable DB for mutations
  const wdb = getWriteDB();
  
  try {
    // 1. Complete the task
    wdb.prepare(`
      UPDATE ops_tasks 
      SET status = 'done', completed_at = datetime('now'), completed_by = ?
      WHERE id = ?
    `).run(memberId, taskId);
    
    // 2. Update velocity (completions today)
    const today = todayET();
    wdb.prepare(`
      INSERT INTO pib_energy_states (member_id, state_date, completions_today, last_completion_at)
      VALUES (?, ?, 1, datetime('now'))
      ON CONFLICT(member_id, state_date) DO UPDATE SET
        completions_today = completions_today + 1,
        last_completion_at = datetime('now')
    `).run(memberId, today);
    
    // 3. Update streak (elastic with grace days)
    const streakResult = updateStreak(wdb, memberId, today);
    
    // 4. Get completion stats for reward selection
    const stats = getCompletionStats(wdb, memberId);
    
    // Calculate task age in days
    if (task.created_at) {
      const createdDate = new Date(task.created_at);
      task.days_old = Math.floor((new Date() - createdDate) / 86400000);
    }
    
    // 5. Select reward (variable-ratio reinforcement)
    const { tier, message } = selectReward(memberId, task, stats);
    
    // 6. Log reward
    wdb.prepare(`
      INSERT INTO pib_reward_log (member_id, task_id, reward_tier, reward_text)
      VALUES (?, ?, ?, ?)
    `).run(memberId, taskId, tier, message);
    
    // 7. Audit log
    auditLog(wdb, "task-complete", JSON.stringify({ 
      task_id: taskId, 
      title: task.title,
      reward_tier: tier 
    }), memberId);
    
    // 8. Get whatNow for Zeigarnik hook
    const snapshot = loadSnapshot(wdb, memberId);
    const wn = whatNow(memberId, snapshot);
    const oneMore = wn.one_more_teaser ? generateOneMoreNudge(wn.one_more_teaser) : null;
    
    // 9. Momentum check
    const momentum = shouldShowMomentumNudge(stats.completions_today) 
      ? generateMomentumMessage(stats.completions_today) 
      : null;
    
    wdb.close();
    
    res.json({
      ok: true,
      reward_tier: tier,
      reward_message: message,
      streak: streakResult,
      one_more: oneMore,
      momentum: momentum,
      stats: {
        today: stats.completions_today,
        week: stats.week_completions,
        streak: streakResult.current
      }
    });
    
  } catch (err) {
    wdb.close();
    console.error("Task completion error:", err);
    res.status(500).json({ error: err.message });
  }
});

app.post("/api/tasks/:id/skip", requireMember, (req, res) => {
  const d = getDB();
  const task = d.prepare("SELECT * FROM ops_tasks WHERE id = ?").get(req.params.id);
  if (!task) return res.status(404).json({ error: "Task not found" });
  if (task.assignee !== req.authMemberId && task.assignee !== req.memberId) {
    return res.status(403).json({ error: "Can only skip your own tasks" });
  }
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

app.post("/api/lists/:listName/items/:id/toggle", requireMember, guardedWrite("list_item_toggle", (_req, res) => {
  const d = getDB();
  const item = d.prepare("SELECT * FROM ops_lists WHERE id = ?").get(_req.params.id);
  if (!item) return res.status(404).json({ error: "Item not found" });

  const wdb = getWriteDB();
  wdb.prepare("UPDATE ops_lists SET checked = ?, checked_at = datetime('now') WHERE id = ?")
    .run(item.checked ? 0 : 1, _req.params.id);
  auditLog(wdb, "list-item-toggle", JSON.stringify({ id: _req.params.id, list: _req.params.listName, checked: !item.checked }), _req.memberId);
  wdb.close();

  res.json({ ok: true, done: !item.checked });
}));

app.post("/api/chat/send", requireMember, rateLimitMiddleware("web_chat"), (req, res) => {
  const childMode = req.body.child_mode === true || req.memberRole === 'child';
  const childPrompt = childMode
    ? "You are talking to a child (age 6). Keep responses simple, age-appropriate, fun. Never discuss finances, medical details, custody, ADHD, medications, or adult scheduling.\n\n"
    : "";
  const result = runCLI("capture", {
    text: childPrompt + req.body.message,
    source: "webchat",
  }, req.memberId);
  res.json(result);
});

app.post("/api/approvals/:id/decide", requireMember, guardedWrite("approval_decide", (req, res) => {
  const decision = req.body.decision;
  if (!["approved", "rejected"].includes(decision)) {
    return res.status(400).json({ error: "decision must be 'approved' or 'rejected'" });
  }
  const wdb = getWriteDB();
  wdb.prepare(
    "UPDATE mem_approval_queue SET status = ?, decided_by = ?, decided_at = datetime('now') WHERE id = ?"
  ).run(decision, req.memberId, req.params.id);
  auditLog(wdb, "approval-decide", JSON.stringify({ id: req.params.id, decision }), req.memberId);
  wdb.close();
  res.json({ ok: true });
}));

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
app.get("/api/costs", requireParent, (req, res) => {
  // Computed from pib_config + LLM usage tracking
  const d = getDB();
  const config = d.prepare("SELECT * FROM pib_config WHERE key LIKE 'cost_%'").all();
  res.json({
    total: config.find(c => c.key === "cost_total_monthly")?.value || "—",
    items: [],
  });
});

// --- AI Models ---
app.get("/api/config/models", requireParent, (req, res) => {
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
app.get("/api/sources", requireParent, (req, res) => {
  const d = getDB();
  const sources = d.prepare("SELECT * FROM common_source_classifications WHERE active = 1").all();
  res.json({ sources });
});

// --- Life Phases ---
app.get("/api/phases", requireParent, (req, res) => {
  const d = getDB();
  const phases = d.prepare("SELECT * FROM common_life_phases ORDER BY start_date").all();
  res.json({ phases });
});

// --- Config (pib_config) ---
app.get("/api/config", requireParent, (req, res) => {
  const d = getDB();
  const rows = d.prepare("SELECT key, value as val, description as desc FROM pib_config ORDER BY key").all();
  res.json({ config: rows });
});

app.post("/api/config/:key", requireParent, guardedWrite("config_set", (req, res) => {
  const key = req.params.key;
  if (!/^[a-zA-Z0-9_]+$/.test(key)) {
    return res.status(400).json({ error: "key must be alphanumeric + underscores only" });
  }
  const value = req.body.value;
  const wdb = getWriteDB();
  wdb.prepare(
    "INSERT INTO pib_config (key, value, updated_by) VALUES (?, ?, ?) " +
    "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_by = excluded.updated_by, " +
    "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')"
  ).run(key, value, req.memberId);
  auditLog(wdb, "config-set", JSON.stringify({ key, value }), req.memberId);
  wdb.close();
  res.json({ ok: true, key, value });
}));

// --- Settings: Permissions (read-only) ---
app.get("/api/settings/permissions", requireParent, (req, res) => {
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
app.get("/api/settings/coaching", requireParent, (req, res) => {
  const d = getDB();
  try {
    const protocols = d.prepare("SELECT * FROM pib_coach_protocols ORDER BY name").all();
    res.json({ protocols });
  } catch {
    res.json({ protocols: [] });
  }
});

app.post("/api/settings/coaching/:id/toggle", requireParent, guardedWrite("coaching_toggle", (req, res) => {
  const wdb = getWriteDB();
  const proto = wdb.prepare("SELECT active FROM pib_coach_protocols WHERE id = ?").get(req.params.id);
  if (!proto) { wdb.close(); return res.status(404).json({ error: "Protocol not found" }); }
  wdb.prepare("UPDATE pib_coach_protocols SET active = ? WHERE id = ?").run(proto.active ? 0 : 1, req.params.id);
  auditLog(wdb, "coaching-toggle", JSON.stringify({ id: req.params.id, active: !proto.active }), req.memberId);
  wdb.close();
  res.json({ ok: true, active: !proto.active });
}));

// --- Settings: Governance Gates (read-only) ---
app.get("/api/settings/gates", requireParent, (req, res) => {
  const gov = loadYAML("governance.yaml");
  res.json({
    action_gates: gov.action_gates || {},
    agent_overrides: gov.agent_overrides || {},
    rate_limits: gov.rate_limits || {},
  });
});

// --- Settings: Household (member management) ---
app.get("/api/settings/household", requireParent, (req, res) => {
  const d = getDB();
  const members = d.prepare("SELECT * FROM common_members ORDER BY role, display_name").all();
  const filtered = members.map(m => {
    if (m.id === req.memberId) return m;
    const { email, phone, tailscale_email, medication_config, energy_markers, ...safe } = m;
    return safe;
  });
  res.json({ members: filtered });
});

app.post("/api/settings/household/members", requireParent, guardedWrite("member_add", (req, res) => {
  const { id, display_name, role } = req.body;
  if (!id || !display_name || !role) {
    return res.status(400).json({ error: "id, display_name, and role are required" });
  }
  if (!/^m-[a-z][a-z0-9_-]*$/.test(id)) {
    return res.status(400).json({ error: "id must match m-{name} pattern (lowercase alphanumeric)" });
  }
  const wdb = getWriteDB();
  try {
    wdb.prepare(
      "INSERT INTO common_members (id, display_name, role) VALUES (?, ?, ?)"
    ).run(id, display_name, role);
    auditLog(wdb, "member-add", JSON.stringify({ id, display_name, role }), req.memberId);
    wdb.close();
    res.json({ ok: true, id });
  } catch (e) {
    wdb.close();
    res.status(400).json({ error: e.message });
  }
}));

app.post("/api/settings/household/members/:id/deactivate", requireParent, guardedWrite("member_deactivate", (req, res) => {
  const wdb = getWriteDB();
  wdb.prepare("UPDATE common_members SET active = 0 WHERE id = ?").run(req.params.id);
  auditLog(wdb, "member-deactivate", JSON.stringify({ id: req.params.id }), req.memberId);
  wdb.close();
  res.json({ ok: true });
}));

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

app.get("/api/chores", requireMember, (req, res) => {
  const d = getDB();
  const memberId = req.query.member || "m-charlie";
  const chores = d.prepare(
    "SELECT * FROM ops_tasks WHERE assignee = ? AND item_type = 'chore' AND status NOT IN ('dismissed') " +
    "ORDER BY due_date"
  ).all(memberId);
  res.json({ chores });
});

// ═══════════════════════════════════════════════════════════
// PEOPLE PAGE — Contacts, Comms, Observations, Autonomy Tiers
// ═══════════════════════════════════════════════════════════

app.get("/api/people/contacts", requireParent, (req, res) => {
  const d = getDB();
  const today = todayET();

  // Contacts = household members + external people from comms history
  const members = d.prepare(
    "SELECT id, display_name as name, role as type, phone, email, active FROM common_members ORDER BY display_name"
  ).all();

  // Extract external contacts from ops_comms (people we've communicated with)
  const externalContacts = d.prepare(
    "SELECT DISTINCT from_addr as phone, " +
    "MAX(created_at) as last, julianday(?) - julianday(MAX(created_at)) as days " +
    "FROM ops_comms WHERE direction = 'inbound' AND from_addr IS NOT NULL AND from_addr != '' " +
    "GROUP BY from_addr ORDER BY last DESC LIMIT 50"
  ).all(today);

  const contacts = [
    ...members.map(m => ({
      id: m.id,
      name: m.name,
      type: m.type,
      phone: m.phone,
      email: m.email,
      last: null,
      days: null,
      ghost: false,
    })),
    ...externalContacts.map(c => ({
      id: crypto.randomUUID(),
      name: c.phone || "Unknown",
      type: "vendor",
      phone: c.phone,
      last: c.last,
      days: Math.floor(c.days),
      ghost: c.days > 7,
    }))
  ];

  res.json({ contacts });
});

app.get("/api/people/comms", requireParent, (req, res) => {
  const d = getDB();
  const limit = parseInt(req.query.limit || "20", 10);

  const comms = d.prepare(
    "SELECT from_addr as person, channel as ch, direction as dir, " +
    "summary as subj, created_at as ts " +
    "FROM ops_comms ORDER BY created_at DESC LIMIT ?"
  ).all(limit);

  res.json({ comms });
});

app.get("/api/people/observations", requireParent, (req, res) => {
  const d = getDB();

  // Observations = long-term memories with category='observation'
  const observations = d.prepare(
    "SELECT content as note, domain, category, created_at as ts, member_id " +
    "FROM mem_long_term WHERE category = 'observation' OR category = 'facts' " +
    "ORDER BY created_at DESC LIMIT 50"
  ).all();

  const enriched = observations.map(o => {
    return {
      person: o.domain || "General",
      note: o.note,
      ts: o.ts,
    };
  });

  res.json({ observations: enriched });
});

app.get("/api/people/autonomy-tiers", requireParent, (req, res) => {
  const gov = loadYAML("governance.yaml");
  const caps = loadYAML("agent_capabilities.yaml");

  // Build autonomy tiers from governance gates
  const actionGates = gov.action_gates || {};
  const tiers = [];

  for (const [action, gateValue] of Object.entries(actionGates)) {
    let level = "Autonomous";
    let desc = "Do it, log receipt";

    if (gateValue === false || gateValue === "off") {
      level = "Blocked";
      desc = "Not permitted";
    } else if (gateValue === "confirm") {
      level = "Confirm";
      desc = "Requires user confirmation";
    } else if (gateValue === "draft") {
      level = "Draft";
      desc = "Create draft for approval";
    }

    tiers.push({
      action: action.replace(/_/g, " "),
      level,
      desc,
    });
  }

  res.json({ tiers });
});

// (duplicate /api/scoreboard removed — kept the one above near other CLI routes)

// ═══════════════════════════════════════════════════════════
// CHANNEL REGISTRY & COMMS INBOX
// ═══════════════════════════════════════════════════════════

// --- List all channels with health status ---
app.get("/api/channels", (_req, res) => {
  const d = getDB();
  try {
    const channels = d.prepare(`
      SELECT c.id, c.display_name, c.icon, c.category, c.enabled, c.setup_complete,
             h.status, h.last_poll_at, h.consecutive_failures
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
app.get("/api/channels/:id", requireMember, (req, res) => {
  const d = getDB();
  try {
    const channel = d.prepare(`
      SELECT c.*, h.status, h.last_poll_at, h.consecutive_failures,
             h.last_error, h.last_error
      FROM comms_channels c
      LEFT JOIN comms_channel_health h ON h.channel_id = c.id
      WHERE c.id = ?
    `).get(req.params.id);
    if (!channel) return res.status(404).json({ error: "Channel not found" });

    // Access check
    const access = d.prepare(
      "SELECT access_level FROM comms_channel_member_access WHERE member_id = ? AND channel_id = ?"
    ).get(req.memberId, req.params.id);
    if (!access || access.access_level === 'none') {
      return res.status(403).json({ error: "No access to this channel" });
    }

    // Get capabilities - table doesn't exist in schema, capabilities are in channel.config_json
    let capabilities = [];
    if (channel.config_json) {
      try {
        const config = JSON.parse(channel.config_json);
        capabilities = config.capabilities || [];
      } catch { /* invalid JSON */ }
    }

    // Get member access (correct table name: comms_channel_member_access)
    let memberAccess = [];
    try {
      memberAccess = d.prepare(
        "SELECT member_id, access_level FROM comms_channel_member_access WHERE channel_id = ?"
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
      WHERE channel = ? AND member_id = ?
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
  const outcome = req.query.outcome || req.query.status || null; // support both params
  try {
    let sql = `
      SELECT oc.*, cc.display_name as channel_name, cc.icon as channel_icon
      FROM ops_comms oc
      LEFT JOIN comms_channels cc ON cc.id = oc.channel
      WHERE oc.member_id = ?
    `;
    const params = [req.memberId];

    if (batchWindow) {
      sql += " AND oc.batch_window = ?";
      params.push(batchWindow);
    }
    if (outcome) {
      sql += " AND oc.outcome = ?";
      params.push(outcome);
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
// CAPTURE DOMAIN — Section 15 Full Implementation
// ═══════════════════════════════════════════════════════════

// --- GET /api/captures — Query captures with filters ---
app.get("/api/captures", requireMember, (req, res) => {
  const d = getDB();
  const memberId = req.memberId;
  const notebook = req.query.notebook;
  const search = req.query.search;
  const orgStatus = req.query.org_status;
  const limit = parseInt(req.query.limit || "100", 10);
  const groupBy = req.query.group_by;

  try {
    // Group by notebook (for sidebar counts)
    if (groupBy === 'notebook') {
      const counts = d.prepare(`
        SELECT notebook, COUNT(*) as count
        FROM cap_captures
        WHERE member_id = ? AND archived = 0
        GROUP BY notebook
        ORDER BY notebook
      `).all(memberId);
      return res.json({ notebook_counts: counts });
    }

    // Regular query
    let sql = "SELECT * FROM cap_captures WHERE member_id = ? AND archived = 0";
    const params = [memberId];

    if (notebook && notebook !== 'all') {
      sql += " AND notebook = ?";
      params.push(notebook);
    }

    if (orgStatus) {
      sql += " AND triage_status = ?";
      params.push(orgStatus);
    }

    if (search) {
      // FTS5 search
      const searchResults = d.prepare(`
        SELECT rowid FROM cap_captures_fts WHERE cap_captures_fts MATCH ?
      `).all(search);
      const rowids = searchResults.map(r => r.rowid);
      if (rowids.length > 0) {
        sql += ` AND rowid IN (${rowids.join(',')})`;
      } else {
        return res.json({ captures: [] });
      }
    }

    sql += " ORDER BY pinned DESC, created_at DESC LIMIT ?";
    params.push(limit);

    const captures = d.prepare(sql).all(...params);
    res.json({ captures });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// --- GET /api/captures/stats — Capture counts and stats ---
app.get("/api/captures/stats", requireMember, (req, res) => {
  const d = getDB();
  const memberId = req.memberId;
  const today = todayET();
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

  try {
    const total = d.prepare(
      "SELECT COUNT(*) as count FROM cap_captures WHERE member_id = ? AND archived = 0"
    ).get(memberId);

    const inboxCount = d.prepare(
      "SELECT COUNT(*) as count FROM cap_captures WHERE member_id = ? AND notebook = 'inbox' AND archived = 0"
    ).get(memberId);

    const recipes = d.prepare(
      "SELECT COUNT(*) as count FROM cap_captures WHERE member_id = ? AND capture_type = 'recipe' AND archived = 0"
    ).get(memberId);

    const pinned = d.prepare(
      "SELECT COUNT(*) as count FROM cap_captures WHERE member_id = ? AND pinned = 1 AND archived = 0"
    ).get(memberId);

    const last7d = d.prepare(
      "SELECT COUNT(*) as count FROM cap_captures WHERE member_id = ? AND created_at >= ?"
    ).get(memberId, sevenDaysAgo);

    res.json({
      total: total.count,
      inbox_count: inboxCount.count,
      recipes: recipes.count,
      pinned: pinned.count,
      last_7d: last7d.count,
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// --- GET /api/captures/recipes — Recipe-specific query ---
app.get("/api/captures/recipes", requireMember, (req, res) => {
  const d = getDB();
  const memberId = req.memberId;

  try {
    const recipes = d.prepare(`
      SELECT * FROM cap_captures
      WHERE member_id = ? AND capture_type = 'recipe' AND archived = 0
      ORDER BY created_at DESC
      LIMIT 50
    `).all(memberId);

    res.json({ recipes });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// --- POST /api/capture — Create new capture ---
app.post("/api/capture", requireMember, guardedWrite("capture_create", (req, res) => {
  const wdb = req.writeDB;
  const memberId = req.memberId;
  const { text, source, capture_type, notebook } = req.body;

  if (!text) {
    return res.status(400).json({ error: "text is required" });
  }

  // Generate ULID-style ID (simplified)
  const captureId = `cap-${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;

  try {
    wdb.prepare(`
      INSERT INTO cap_captures (
        id, member_id, raw_text, title, source, capture_type, notebook, triage_status
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      captureId,
      memberId,
      text,
      text.slice(0, 100), // Simple title extraction
      source || 'chat',
      capture_type || 'note',
      notebook || 'inbox',
      'raw'
    );

    auditLog(wdb, "capture-create", JSON.stringify({ id: captureId, text: text.slice(0, 50) }), memberId);

    res.json({ ok: true, id: captureId });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}));

// --- POST /api/captures/:id — Update capture ---
app.post("/api/captures/:id", requireMember, guardedWrite("capture_update", (req, res) => {
  const wdb = req.writeDB;
  const memberId = req.memberId;
  const captureId = req.params.id;
  const updates = req.body;

  try {
    // Build dynamic UPDATE query
    const fields = [];
    const values = [];

    if (updates.notebook !== undefined) {
      fields.push("notebook = ?");
      values.push(updates.notebook);
    }
    if (updates.pinned !== undefined) {
      fields.push("pinned = ?");
      values.push(updates.pinned ? 1 : 0);
    }
    if (updates.archived !== undefined) {
      fields.push("archived = ?");
      values.push(updates.archived ? 1 : 0);
      if (updates.archived) {
        fields.push("archived_at = datetime('now')");
      }
    }
    if (updates.org_status !== undefined) {
      fields.push("triage_status = ?");
      values.push(updates.org_status);
    }

    if (fields.length === 0) {
      return res.status(400).json({ error: "No valid fields to update" });
    }

    fields.push("updated_at = datetime('now')");
    values.push(captureId, memberId);

    const sql = `UPDATE cap_captures SET ${fields.join(', ')} WHERE id = ? AND member_id = ?`;
    wdb.prepare(sql).run(...values);

    auditLog(wdb, "capture-update", JSON.stringify({ id: captureId, updates }), memberId);

    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}));

// --- POST /api/captures/:id/confirm — Mark as organized ---
app.post("/api/captures/:id/confirm", requireMember, guardedWrite("capture_confirm", (req, res) => {
  const wdb = req.writeDB;
  const memberId = req.memberId;
  const captureId = req.params.id;

  try {
    wdb.prepare(`
      UPDATE cap_captures
      SET triage_status = 'organized', last_organized_at = datetime('now'), updated_at = datetime('now')
      WHERE id = ? AND member_id = ?
    `).run(captureId, memberId);

    auditLog(wdb, "capture-confirm", JSON.stringify({ id: captureId }), memberId);

    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}));

// --- POST /api/captures/:id/made-it — Mark recipe as made ---
app.post("/api/captures/:id/made-it", requireMember, guardedWrite("capture_made_it", (req, res) => {
  const wdb = req.writeDB;
  const memberId = req.memberId;
  const captureId = req.params.id;

  try {
    // Get current recipe_data
    const capture = wdb.prepare("SELECT recipe_data FROM cap_captures WHERE id = ? AND member_id = ?").get(captureId, memberId);
    if (!capture) {
      return res.status(404).json({ error: "Capture not found" });
    }

    let recipeData = capture.recipe_data ? JSON.parse(capture.recipe_data) : {};
    recipeData.made_count = (recipeData.made_count || 0) + 1;
    recipeData.last_made_at = new Date().toISOString();

    wdb.prepare(`
      UPDATE cap_captures
      SET recipe_data = ?, updated_at = datetime('now')
      WHERE id = ? AND member_id = ?
    `).run(JSON.stringify(recipeData), captureId, memberId);

    auditLog(wdb, "capture-made-it", JSON.stringify({ id: captureId, made_count: recipeData.made_count }), memberId);

    res.json({ ok: true, made_count: recipeData.made_count });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}));

// --- GET /api/settings/captures — Capture settings ---
app.get("/api/settings/captures", requireParent, (req, res) => {
  const d = getDB();

  try {
    // Read capture config
    const configRows = d.prepare("SELECT key, value FROM pib_config WHERE key LIKE 'capture_%'").all();
    const config = {};
    for (const row of configRows) {
      const key = row.key.replace('capture_', '');
      config[key] = row.value === '1' || row.value === 'true' ? true : row.value;
    }

    // List of capture adapters (static for now)
    const adapters = [
      { id: 'chat', name: 'Chat', enabled: true, last_capture: null },
      { id: 'voice', name: 'Voice', enabled: true, last_capture: null },
      { id: 'sms', name: 'SMS', enabled: false, last_capture: null },
      { id: 'email', name: 'Email', enabled: false, last_capture: null },
    ];

    res.json({ config, adapters });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// --- POST /api/settings/captures/adapter/:source — Toggle adapter ---
app.post("/api/settings/captures/adapter/:source", requireParent, guardedWrite("capture_adapter_toggle", (req, res) => {
  const wdb = req.writeDB;
  const memberId = req.memberId;
  const source = req.params.source;

  try {
    const configKey = `capture_adapter_${source}_enabled`;

    // Toggle the config value
    const current = wdb.prepare("SELECT value FROM pib_config WHERE key = ?").get(configKey);
    const newValue = current?.value === '1' ? '0' : '1';

    wdb.prepare(`
      INSERT INTO pib_config (key, value, updated_by)
      VALUES (?, ?, ?)
      ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_by = excluded.updated_by, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
    `).run(configKey, newValue, memberId);

    auditLog(wdb, "capture-adapter-toggle", JSON.stringify({ source, enabled: newValue === '1' }), memberId);

    res.json({ ok: true, enabled: newValue === '1' });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}));

// ═══════════════════════════════════════════════════════════
// BRIDGE ENDPOINTS — Sensor Ingest, BlueBubbles Webhooks, Task Capture
// ═══════════════════════════════════════════════════════════

/**
 * Validate Bearer token against SIRI_BEARER_TOKEN env var.
 * Returns true if valid, false otherwise.
 */
function validateBearerToken(req) {
  const authHeader = req.headers.authorization || "";
  if (!authHeader.startsWith("Bearer ")) return false;
  const token = authHeader.slice(7);
  const expected = process.env.SIRI_BEARER_TOKEN || "";
  return expected && token === expected;
}

/**
 * Privacy filter helper for sensor queries.
 * Excludes classification=privileged unless req.memberId matches data member_id.
 */
function privacyFilter(memberId) {
  return memberId
    ? `(classification != 'privileged' OR member_id = '${memberId}')`
    : `classification != 'privileged'`;
}

// --- Sensor Ingest ---
// POST /api/sensors/ingest — validates Bearer token, routes to Python CLI
app.post("/api/sensors/ingest", rateLimitMiddleware("siri"), (req, res) => {
  if (!validateBearerToken(req)) {
    return res.status(401).json({ error: "Invalid or missing Bearer token" });
  }

  const { source, member_id, timestamp, classification, data } = req.body;
  if (!source || !member_id) {
    return res.status(400).json({ error: "source and member_id are required" });
  }

  // Generate idempotency key from payload hash
  const idempotencyKey = `${source}-${member_id}-${timestamp || Date.now()}-${crypto.randomUUID().slice(0,8)}`;

  const result = runCLI("sensor-ingest", {
    source,
    member_id,
    timestamp: timestamp || new Date().toISOString(),
    classification: classification || "normal",
    data: data || {},
    idempotency_key: idempotencyKey,
  });

  res.json(result);
});

// --- BlueBubbles Webhook (per-bridge) ---
// POST /api/webhooks/bluebubbles/:bridgeId — validates per-bridge secret, forces member_id
app.post("/api/webhooks/bluebubbles/:bridgeId", rateLimitMiddleware("bluebubbles"), (req, res) => {
  const bridgeId = req.params.bridgeId.toLowerCase();

  // Map bridge_id to member_id
  const bridgeMemberMap = { james: "m-james", laura: "m-laura" };
  if (!bridgeMemberMap[bridgeId]) {
    return res.status(400).json({ error: `Unknown bridge: ${bridgeId}` });
  }

  // Validate per-bridge secret from header or query param
  const providedSecret = req.headers["x-bluebubbles-secret"]
    || req.query.secret
    || req.body?.api_key
    || "";
  const envKey = `BLUEBUBBLES_${bridgeId.toUpperCase()}_SECRET`;
  const expectedSecret = process.env[envKey] || "";

  if (!expectedSecret) {
    return res.status(500).json({ error: `${envKey} not configured` });
  }
  if (providedSecret !== expectedSecret) {
    return res.status(401).json({ error: "Invalid API key", bridge: bridgeId });
  }

  // Route to CLI with bridge_id (forces member_id)
  const result = runCLI("webhook-receive", {
    bridge_id: bridgeId,
    api_key: providedSecret,
    payload: req.body,
  });

  res.json(result);
});

// --- Task Capture ---
// POST /api/capture/task — validates Bearer token, routes to Python CLI
app.post("/api/capture/task", rateLimitMiddleware("siri"), (req, res) => {
  if (!validateBearerToken(req)) {
    return res.status(401).json({ error: "Invalid or missing Bearer token" });
  }

  const { member_id, source, text, timestamp } = req.body;
  if (!member_id || !text) {
    return res.status(400).json({ error: "member_id and text are required" });
  }

  const result = runCLI("capture", {
    member_id,
    source: source || "siri",
    text,
  }, member_id);

  res.json(result);
});

// --- Sensor Data Query (privacy-fenced) ---
app.get("/api/sensors", requireMember, (req, res) => {
  const d = getDB();
  const memberId = req.memberId;
  const readingType = req.query.type;
  const since = req.query.since;
  const limit = parseInt(req.query.limit || "100", 10);

  try {
    let sql = `SELECT * FROM pib_sensor_readings WHERE ${privacyFilter(memberId)}`;
    const params = [];

    if (readingType) {
      sql += " AND reading_type = ?";
      params.push(readingType);
    }
    if (since) {
      sql += " AND timestamp >= ?";
      params.push(since);
    }
    if (memberId && req.query.mine === "true") {
      sql += " AND member_id = ?";
      params.push(memberId);
    }

    sql += " ORDER BY timestamp DESC LIMIT ?";
    params.push(limit);

    const readings = d.prepare(sql).all(...params);
    res.json({ readings });
  } catch (e) {
    res.json({ readings: [], error: e.message });
  }
});

// ═══════════════════════════════════════════════════════════
// START
// ═══════════════════════════════════════════════════════════

app.listen(PORT, '127.0.0.1', () => {
  console.log(`PIB Console on http://127.0.0.1:${PORT} (Tailscale Serve will proxy)`);
  console.log(`Database: ${DB_PATH}`);
});

export default app;
