#!/usr/bin/env node
/**
 * heartbeat_check.mjs — System health check for PIB runtime.
 *
 * Checks: CLI health, gog auth, disk space, DB exists, backup age.
 *
 * Usage:
 *   node scripts/core/heartbeat_check.mjs [--json] [--help]
 *
 * Env:
 *   PIB_DB_PATH          (default: /opt/pib/data/pib.db)
 *   PIB_HOME             (default: /opt/pib)
 *   PIB_CALLER_AGENT     (set automatically when called by OpenClaw)
 */

import { execSync, execFileSync } from "node:child_process";
import { existsSync, statSync, readdirSync } from "node:fs";
import { parseArgs } from "node:util";
import { join } from "node:path";

const { values: args } = parseArgs({
  options: {
    json: { type: "boolean", default: false },
    help: { type: "boolean", default: false },
  },
  strict: false,
});

if (args.help) {
  console.log(`heartbeat_check.mjs — System health check for PIB runtime.

Usage: node scripts/core/heartbeat_check.mjs [options]

Options:
  --json    Output structured JSON
  --help    Show this help

Checks performed:
  - PIB CLI health command
  - gog auth status (Google OAuth)
  - Disk space (warns < 2GB)
  - Database file exists and is non-empty
  - Backup age (warns if > 24h)

Env vars:
  PIB_DB_PATH          Path to PIB database (default: /opt/pib/data/pib.db)
  PIB_HOME             PIB home directory (default: /opt/pib)
  PIB_CALLER_AGENT     Caller agent identifier`);
  process.exit(0);
}

const DB_PATH = process.env.PIB_DB_PATH || "/opt/pib/data/pib.db";
const PIB_HOME = process.env.PIB_HOME || "/opt/pib";
const CALLER = process.env.PIB_CALLER_AGENT || "openclaw";
const jsonOut = args.json;
const BACKUP_DIR = join(PIB_HOME, "data", "backups");

const checks = [];
let worstStatus = "ok";

function addCheck(name, status, detail = "") {
  checks.push({ name, status, detail });
  if (status === "error") worstStatus = "error";
  else if (status === "warn" && worstStatus !== "error") worstStatus = "warn";
}

function tryExec(file, args, timeout = 10_000) {
  try {
    return execFileSync(file, args, {
      encoding: "utf-8",
      timeout,
      env: { ...process.env, PIB_CALLER_AGENT: CALLER },
      stdio: ["pipe", "pipe", "pipe"],
    }).trim();
  } catch (e) {
    return null;
  }
}

// 1. DB file exists
if (existsSync(DB_PATH)) {
  const sz = statSync(DB_PATH).size;
  addCheck("db_exists", sz > 0 ? "ok" : "error", sz > 0 ? `${(sz / 1024).toFixed(0)} KB` : "empty file");
} else {
  addCheck("db_exists", "error", `Not found: ${DB_PATH}`);
}

// 2. PIB CLI health
const PYTHON_CMD = process.env.PIB_PYTHON || "python3";
const healthRaw = tryExec(PYTHON_CMD, ["-m", "pib.cli", "health", DB_PATH, "--json"]);
if (healthRaw) {
  try {
    const h = JSON.parse(healthRaw);
    addCheck("cli_health", h.status === "ok" || h.healthy ? "ok" : "warn", healthRaw.slice(0, 200));
  } catch {
    addCheck("cli_health", "ok", "returned non-JSON (assumed ok)");
  }
} else {
  addCheck("cli_health", "warn", "CLI health command failed or not wired");
}

// 3. gog auth status
const gogAuth = tryExec("gog", ["auth", "status"]);
if (gogAuth !== null) {
  const authed = /authenticated|logged in|valid/i.test(gogAuth);
  addCheck("gog_auth", authed ? "ok" : "warn", gogAuth.slice(0, 200));
} else {
  addCheck("gog_auth", "warn", "gog CLI not available");
}

// 4. Disk space
try {
  const dfOut = execSync("df -Pk /", { encoding: "utf-8" });
  const freeKb = parseInt(dfOut.split("\n")[1].split(/\s+/)[3], 10);
  const freeGb = (freeKb / 1048576).toFixed(1);
  addCheck("disk_space", freeKb < 2097152 ? "warn" : "ok", `${freeGb} GB free`);
} catch {
  addCheck("disk_space", "warn", "Could not check disk space");
}

// 5. Backup age
try {
  if (existsSync(BACKUP_DIR)) {
    const files = readdirSync(BACKUP_DIR).filter((f) => f.endsWith(".db") || f.endsWith(".gz"));
    if (files.length > 0) {
      const newest = files
        .map((f) => ({ f, mt: statSync(join(BACKUP_DIR, f)).mtimeMs }))
        .sort((a, b) => b.mt - a.mt)[0];
      const ageH = (Date.now() - newest.mt) / 3600_000;
      addCheck("backup_age", ageH > 24 ? "warn" : "ok", `${ageH.toFixed(1)}h (${newest.f})`);
    } else {
      addCheck("backup_age", "warn", "No backups found");
    }
  } else {
    addCheck("backup_age", "warn", `Backup dir not found: ${BACKUP_DIR}`);
  }
} catch {
  addCheck("backup_age", "warn", "Could not check backups");
}

// Output
const result = { status: worstStatus, checks };
if (jsonOut) {
  console.log(JSON.stringify(result, null, 2));
} else {
  console.log(`Heartbeat: ${worstStatus.toUpperCase()}`);
  for (const c of checks) {
    const icon = c.status === "ok" ? "✓" : c.status === "warn" ? "⚠" : "✗";
    console.log(`  ${icon} ${c.name}: ${c.detail}`);
  }
}

if (worstStatus === "error") process.exit(1);
