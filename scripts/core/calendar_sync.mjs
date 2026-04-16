#!/usr/bin/env node
/**
 * calendar_sync.mjs — Sync Google Calendar events into PIB database.
 *
 * Modes:
 *   --incremental  Last 24h (default)
 *   --full         Last 90 days
 *
 * Usage:
 *   node scripts/core/calendar_sync.mjs [--incremental|--full] [--cal-id <id>] [--json] [--help]
 *
 * Env:
 *   PIB_DB_PATH          (default: /opt/pib/data/pib.db)
 *   PIB_HOME             (default: /opt/pib)
 *   PIB_CALLER_AGENT     (set automatically when called by OpenClaw)
 */

import { execSync, execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({
  options: {
    full: { type: "boolean", default: false },
    incremental: { type: "boolean", default: false },
    "cal-id": { type: "string" },
    json: { type: "boolean", default: false },
    help: { type: "boolean", default: false },
  },
  strict: false,
});

if (args.help) {
  console.log(`calendar_sync.mjs — Sync Google Calendar events into PIB database.

Usage: node scripts/core/calendar_sync.mjs [options]

Options:
  --incremental   Sync last 24 hours (default)
  --full          Sync last 90 days
  --cal-id <id>   Calendar ID to sync (default: all configured)
  --json          Output structured JSON
  --help          Show this help

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

const mode = args.full ? "full" : "incremental";
const now = new Date();
const fromDate = new Date(now);
if (mode === "full") {
  fromDate.setDate(fromDate.getDate() - 90);
} else {
  fromDate.setDate(fromDate.getDate() - 1);
}
const toDate = new Date(now);
toDate.setDate(toDate.getDate() + 1);

const fmt = (d) => d.toISOString().split("T")[0];

function run(file, args, opts = {}) {
  return execFileSync(file, args, {
    encoding: "utf-8",
    timeout: 120_000,
    env: { ...process.env, PIB_CALLER_AGENT: CALLER },
    ...opts,
  }).trim();
}

function output(obj) {
  if (jsonOut) {
    console.log(JSON.stringify(obj, null, 2));
  } else {
    if (obj.error) {
      console.error(`Error: ${obj.error}`);
    } else {
      console.log(`Calendar sync (${mode}): ${obj.events_fetched ?? 0} events fetched, ${obj.events_ingested ?? 0} ingested.`);
    }
  }
}

try {
  if (!existsSync(DB_PATH)) {
    throw new Error(`Database not found: ${DB_PATH}`);
  }

  // Step 1: Fetch events from Google Calendar via gog CLI
  const gogArgs = ["calendar", "events"];
  if (args["cal-id"]) {
    gogArgs.push(args["cal-id"]);
  } else {
    gogArgs.push("--all");
  }
  gogArgs.push("--from", fmt(fromDate), "--to", fmt(toDate), "--json");
  let eventsRaw;
  try {
    eventsRaw = run("gog", gogArgs);
  } catch (e) {
    throw new Error(`gog calendar fetch failed: ${e.message}`);
  }

  // Step 2: Ingest into PIB database
  let ingestRaw;
  try {
    const PYTHON_CMD = process.env.PIB_PYTHON || "python3";
    ingestRaw = run(PYTHON_CMD, ["-m", "pib.cli", "calendar-ingest", DB_PATH, "--json", eventsRaw]);
  } catch (e) {
    throw new Error(`calendar-ingest failed: ${e.message}`);
  }

  let result;
  try {
    result = JSON.parse(ingestRaw);
  } catch {
    result = { raw: ingestRaw };
  }

  output({
    status: "ok",
    mode,
    from: fmt(fromDate),
    to: fmt(toDate),
    events_fetched: JSON.parse(eventsRaw)?.length ?? null,
    events_ingested: result.ingested ?? result.count ?? null,
    ...result,
  });
} catch (err) {
  output({ status: "error", error: err.message });
  process.exit(1);
}
