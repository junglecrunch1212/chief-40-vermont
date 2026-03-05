#!/usr/bin/env node
/**
 * context_assembler.mjs — Assemble LLM system prompt with full context.
 *
 * Usage:
 *   node scripts/core/context_assembler.mjs --member <id> [--message "..."] [--json] [--help]
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
    message: { type: "string", default: "" },
    json: { type: "boolean", default: false },
    help: { type: "boolean", default: false },
  },
  strict: false,
});

if (args.help) {
  console.log(`context_assembler.mjs — Assemble LLM system prompt with full context.

Usage: node scripts/core/context_assembler.mjs --member <id> [options]

Options:
  --member <id>      Member ID (required)
  --message "..."    Current user message for context relevance
  --json             Output structured JSON (includes token estimate)
  --help             Show this help

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
    } else {
      console.log(obj.prompt ?? obj.raw ?? "");
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

  const payload = JSON.stringify({ message: args.message || "" });
  const escaped = payload.replace(/'/g, "'\\''");
  const cmd = `python -m pib.cli context "${DB_PATH}" --json '${escaped}' --member ${args.member}`;

  const raw = execSync(cmd, {
    encoding: "utf-8",
    timeout: 30_000,
    env: { ...process.env, PIB_CALLER_AGENT: CALLER },
  }).trim();

  let result;
  try {
    result = JSON.parse(raw);
  } catch {
    result = { prompt: raw };
  }

  if (jsonOut) {
    // Estimate tokens (~4 chars per token)
    const prompt = result.prompt ?? raw;
    result.token_estimate = Math.ceil(prompt.length / 4);
  }

  output({ status: "ok", ...result });
} catch (err) {
  output({ status: "error", error: err.message });
  process.exit(1);
}
