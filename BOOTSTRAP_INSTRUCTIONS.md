# PIB v5 Bootstrap — Mac Mini Setup Guide

**Goal:** A running PIB v5 household CoS on a Mac Mini, powered by OpenClaw as L0 infrastructure.

**Time estimate:** 3-4 hours total (1h human setup, 2-3h agent build)

---

## Pre-requisites

- Mac Mini M2 or M4, 16GB RAM, 256GB+ SSD
- Home WiFi network
- Anthropic API key (with active credits)
- Google account credentials (jrstice@gmail.com)
- Apple ID for iMessage (BlueBubbles)
- This repo cloned: `https://github.com/junglecrunch1212/chief-40-vermont.git`

---

## Phase 0: Mac Mini Physical Setup (~30 min) [HUMAN]

### macOS Settings

```bash
# Prevent sleep (this is a server)
sudo pmset -a sleep 0 disksleep 0 displaysleep 0 hibernatemode 0

# Auto-restart after power failure
sudo pmset -a autorestart 1

# Set hostname
sudo scutil --set HostName pib-mini
sudo scutil --set LocalHostName pib-mini
sudo scutil --set ComputerName pib-mini

# Set timezone
sudo systemsetup -settimezone America/New_York
```

**Also do via System Settings UI:**
- General → Login Items → Automatic Login: ON
- Energy → Start up automatically after power failure: ON
- General → Sharing → Remote Login: ON (for SSH)
- Network → Firewall: ON (allow Node.js, Python, BlueBubbles)
- General → Software Update → Automatic Updates: OFF

Note your local IP: `ifconfig en0 | grep inet`

### Install Dependencies

```bash
# Xcode CLI tools
xcode-select --install

# Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# Follow "Add to PATH" instructions it prints

# Node.js 22, Python 3.12, SQLite
brew install node@22 python@3.12 sqlite git

# Verify
node --version    # Should be v22.x
python3 --version # Should be 3.12.x
sqlite3 --version # Should be 3.45+ (has FTS5)
```

---

## Phase 1: OpenClaw Installation (~15 min) [HUMAN]

```bash
# Install OpenClaw
npm install -g openclaw

# Initialize workspace
mkdir -p /opt/pib && cd /opt/pib
openclaw init

# Wire Anthropic API key
openclaw config set anthropic.api_key "sk-ant-..."

# Wire Google auth (follow browser flow)
gog auth login
# Grants: Calendar, Sheets, Gmail, Drive, Contacts
```

---

## Phase 2: Clone & Install PIB (~10 min) [HUMAN]

```bash
cd /opt/pib
git clone https://github.com/junglecrunch1212/chief-40-vermont.git pib

# Create Python virtual environment
python3 -m venv /opt/pib/venv
source /opt/pib/venv/bin/activate

# Install PIB + dev dependencies
cd /opt/pib/pib
pip install -e ".[dev]"

# Verify tests pass
pytest tests/ -v
# Expected: 507+ tests pass
```

---

## Phase 3: Workspace Setup (~5 min) [HUMAN]

Copy the pre-built workspace template files into your OpenClaw workspace:

```bash
# Copy all workspace files
cp /opt/pib/pib/workspace-template/SOUL.md ~/.openclaw/workspace/SOUL.md
cp /opt/pib/pib/workspace-template/AGENTS.md ~/.openclaw/workspace/AGENTS.md
cp /opt/pib/pib/workspace-template/HEARTBEAT.md ~/.openclaw/workspace/HEARTBEAT.md
cp /opt/pib/pib/workspace-template/USER.md ~/.openclaw/workspace/USER.md
cp /opt/pib/pib/workspace-template/TOOLS.md ~/.openclaw/workspace/TOOLS.md
cp /opt/pib/pib/workspace-template/IDENTITY.md ~/.openclaw/workspace/IDENTITY.md
cp /opt/pib/pib/workspace-template/MEMORY.md ~/.openclaw/workspace/MEMORY.md
```

These files tell the OpenClaw agent what it is (PIB), how to route messages (CLI commands), and what rules to follow (privacy, coaching, governance).

---

## Phase 4: Credentials (~10 min) [HUMAN]

```bash
# Create .env from template
mkdir -p /opt/pib/config
cp /opt/pib/pib/config/.env.example /opt/pib/config/.env
chmod 600 /opt/pib/config/.env

# Edit and fill in:
nano /opt/pib/config/.env
```

**Required keys:**
| Key | Where to get it |
|-----|-----------------|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `TWILIO_ACCOUNT_SID` | twilio.com → Console |
| `TWILIO_AUTH_TOKEN` | twilio.com → Console |
| `TWILIO_PHONE_NUMBER` | Your Twilio number |
| `BLUEBUBBLES_SECRET` | Set during Phase 6 |
| `BLUEBUBBLES_URL` | `http://localhost:1234` (default) |
| `SIRI_BEARER_TOKEN` | Generate: `openssl rand -hex 32` |
| `PIB_DB_PATH` | `/opt/pib/data/pib.db` |

---

## Phase 5: Database Bootstrap (~5 min) [AGENT]

The OpenClaw agent runs these. All commands already exist in `src/pib/cli.py`.

```bash
# Set environment
export PIB_DB_PATH=/opt/pib/data/pib.db
export PIB_ENV=prod
export PIB_CALLER_AGENT=dev

# Create data directory
mkdir -p /opt/pib/data /opt/pib/data/backups /opt/pib/logs

# Bootstrap database (applies all migrations + seeds)
source /opt/pib/venv/bin/activate
python -m pib.cli bootstrap $PIB_DB_PATH

# Verify
python -m pib.cli health $PIB_DB_PATH --json
# Expected: {"ready": true, ...}
```

---

## Phase 6: BlueBubbles Setup (~20 min) [HUMAN]

Since this is a single-machine setup (no bridge Minis yet), BlueBubbles runs on the Brain.

1. Download BlueBubbles Server from [bluebubbles.app](https://bluebubbles.app)
2. Install on Mac Mini
3. Sign into iCloud with the Apple ID for iMessage
4. Configure webhook:
   - URL: `http://localhost:3141/webhooks/bluebubbles` (or OpenClaw's channel endpoint)
   - Secret: match `BLUEBUBBLES_SECRET` in `.env`
5. Enable auto-start (Login Items)
6. Test: send an iMessage from your phone, verify webhook fires

**Note:** When Bridge Minis are added later, BlueBubbles moves to dedicated bridge machines. See `PERSONAL_MINI_SETUP.md` for the 3-machine topology.

---

## Phase 7: Agent Builds Integration Layer (~1-2 hours) [AGENT]

The OpenClaw agent creates these files. Reference docs:
- `docs/openclaw-integration.md` — architecture spec
- `docs/pib-api-contract.md` — API endpoint definitions
- `docs/diagrams/pib-console-wired.jsx` — React prototype (1,738 lines)
- `scripts/core/README.md` — expected scripts
- `console/README.md` — expected console files

### Scripts to create:
| File | Purpose |
|------|---------|
| `scripts/core/calendar_sync.mjs` | `gog calendar events --json` → `python -m pib.cli calendar-ingest $PIB_DB_PATH` |
| `scripts/core/context_assembler.mjs` | Calls `python -m pib.cli context $PIB_DB_PATH --member {id}` |
| `scripts/core/what_now.mjs` | Wrapper for `python -m pib.cli what-now $PIB_DB_PATH` |
| `scripts/core/heartbeat_check.mjs` | SQLite health + gog connectivity |
| `console/server.mjs` | Express on port 3333, REST API for dashboard |
| `console/index.html` | Dashboard (scoreboard, stream, schedule, chat) |

### Cron jobs to configure:
See the cron table in `workspace-template/AGENTS.md`.

---

## Phase 8: Launchd Auto-Start (~10 min) [AGENT]

Install plists so everything survives reboot:

```bash
# Template exists at config/com.pib.runtime.plist — update for OpenClaw paths
cp /opt/pib/pib/config/com.pib.runtime.plist ~/Library/LaunchAgents/com.pib.runtime.plist

# Load
launchctl load ~/Library/LaunchAgents/com.pib.runtime.plist
```

Also create plists for:
- OpenClaw gateway daemon
- Console server (port 3333)
- BlueBubbles is handled by Login Items

---

## Phase 9: Verification (~15 min) [AGENT + HUMAN]

```bash
source /opt/pib/venv/bin/activate
export PIB_DB_PATH=/opt/pib/data/pib.db
```

| Probe | Command | Expected |
|-------|---------|----------|
| whatNow works | `python -m pib.cli what-now $PIB_DB_PATH --member m-james --json` | Returns task with micro_script |
| State machine | `python -m pib.cli task-complete $PIB_DB_PATH --json '{"task_id":"tsk-001"}' --member m-james` | Reward tier + streak |
| Custody | `python -m pib.cli custody $PIB_DB_PATH --json` | Parent member_id |
| Calendar syncs | `gog calendar events --json` | Events returned |
| Tests pass | `cd /opt/pib/pib && pytest tests/ -v` | 507+ green |
| Console serves | `curl localhost:3333/api/pulse` | JSON response |
| Health check | `python -m pib.cli health $PIB_DB_PATH --json` | `{"ready": true}` |
| Agent permissions | `PIB_CALLER_AGENT=coach python -m pib.cli task-create $PIB_DB_PATH --json '{"title":"test"}'` | Succeeds |
| Rate limit | 4 rapid writes | 4th returns `{"error":"rate_limited"}` |
| Messaging | Text "what's next?" via iMessage | Gets whatNow() response |

---

## What's Deferred (Phase 2 — Bridge Minis)

These come AFTER the Brain is running and validated:

- **James Bridge Mini** — Dedicated BlueBubbles, Apple Health, FindMy, Siri, HomeKit
- **Laura Bridge Mini** — Same minus HomeKit, privacy-classified sensors
- **Per-member comms DBs** — `comms_james.db` / `comms_laura.db`
- **Signal channel** — Via OpenClaw native support
- **Full proactive engine** — Needs channels wired for outbound
- **Console UI polish** — Role-tailored views per member

See `PERSONAL_MINI_SETUP.md` for the 3-machine topology and sensor webhook contracts.

---

## Quick Reference

| Path | What |
|------|------|
| `/opt/pib/` | PIB home directory |
| `/opt/pib/pib/` | Git repo (chief-40-vermont) |
| `/opt/pib/venv/` | Python virtual environment |
| `/opt/pib/data/pib.db` | SQLite SSOT |
| `/opt/pib/data/backups/` | Hourly backups |
| `/opt/pib/config/.env` | Credentials (chmod 600) |
| `/opt/pib/logs/` | Application logs |
| `~/.openclaw/workspace/` | OpenClaw agent workspace files |
| `config/governance.yaml` | Action permission gates |
| `config/agent_capabilities.yaml` | Agent role definitions |

## Key Commands

```bash
# Activate Python
source /opt/pib/venv/bin/activate

# Check health
python -m pib.cli health $PIB_DB_PATH --json

# What's next for James
python -m pib.cli what-now $PIB_DB_PATH --member m-james --json

# Run tests
cd /opt/pib/pib && pytest tests/ -v

# Start console
node /opt/pib/pib/console/server.mjs

# OpenClaw status
openclaw status
openclaw gateway status
```
