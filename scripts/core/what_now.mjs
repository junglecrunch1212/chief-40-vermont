#!/usr/bin/env node
/**
 * what_now.mjs — Get the single next task for a household member.
 *
 * Usage:
 *   node scripts/core/what_now.mjs --member <id> [--json] [--help]
 *
 * Env:
 *   PIB_DB_PATH          (default: /opt/pib/data/pib.db)
 *   PIB_HOME             (default: /opt/pib)
 *   PIB_CALLER_AGENT     (set automatically when called by OpenClaw)
 */

import { execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { parseArgs } from "node:util";

const { values: args } = parseArgs({
  options: {
    member: { type: "string" },
    json: { type: "boolean", default: false },
    help: { type: "boolean", default: false },
  },
  strict: false,
});

if (args.help) {
  console.log(`what_now.mjs — Get the single next task for a household member.

Usage: node scripts/core/what_now.mjs --member <id> [options]

Options:
  --member <id>   Member ID (required)
  --json          Output structured JSON
  --help          Show this help

Env vars:
  PIB_DB_PATH          Path to PIB database (default: /opt/pib/data/pib.db)
  PIB_HOME             PIB home directory (default: /opt/pib)
  PIB_CALLER_AGENT     Caller agent identifier`);
  process.exit(0);
}

const DB_PATH = process.env.PIB_DB_PATH || "/opt/pib/data/pib.db";
const CALLER = process.env.PIB_CALLER_AGENT || "openclaw";
const jsonOut = args.json;

function output(obj) {
  if (jsonOut) {
    console.log(JSON.stringify(obj, null, 2));
  } else {
    if (obj.error) {
      console.error(`Error: ${obj.error}`);
    } else if (obj.task) {
      console.log(`Next: ${obj.task.title ?? obj.task.summary ?? JSON.stringify(obj.task)}`);
    } else {
      console.log("No pending tasks.");
    }
  }
}

try {
  if (!args.member) {
    throw new Error("--member <id> is required");
  }
  if (!existsSync(DB_PATH)) {
    throw new Error(`Database not found: ${DB_PATH}`);
  }

  const cmd = `python -m pib.cli what-now "${DB_PATH}" --member ${args.member} --json`;
  const raw = execSync(cmd, {
    encoding: "utf-8",
    timeout: 15_000,
    env: { ...process.env, PIB_CALLER_AGENT: CALLER },
  }).trim();

  let result;
  try {
    result = JSON.parse(raw);
  } catch {
    result = { raw };
  }

  output({ status: "ok", ...result });
} catch (err) {
  output({ status: "error", error: err.message });
  process.exit(1);
}
