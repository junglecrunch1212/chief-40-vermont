# Mac Mini Bootstrap Plan — OpenClaw → chief-40-vermont Deployment

**Goal:** A fully prepared Mac Mini running OpenClaw, ready to deploy chief-40-vermont (c40v) with the integration spec. When you tell OpenClaw "deploy c40v," it has everything it needs — credentials, tools, ports, permissions — to succeed without asking you to fix things mid-build.

---

## Phase 0: Mac Mini Hardware & OS

### 0.1 Recommended Hardware
- Mac Mini M2 or M4 (M2 is plenty — c40v is lightweight)
- 16GB RAM minimum (SQLite + Node + Python + BlueBubbles)
- 256GB+ SSD (SQLite DB will stay small; logs and backups grow)

### 0.2 macOS Settings (do these FIRST)

**Prevent sleep (critical — this is a server):**
```bash
# System Settings → Energy → Prevent automatic sleeping when display is off: ON
# Or via CLI:
sudo pmset -a sleep 0
sudo pmset -a disksleep 0
sudo pmset -a displaysleep 0
sudo pmset -a hibernatemode 0
```

**Auto-login after power loss:**
```bash
# System Settings → General → Login Items → Automatic Login: ON (your user)
# System Settings → Energy → Start up automatically after a power failure: ON
sudo pmset -a autorestart 1
```

**Enable Remote Login (SSH):**
```bash
# System Settings → General → Sharing → Remote Login: ON
# Note your local IP: ifconfig en0 | grep inet
```

**Firewall:**
```bash
# System Settings → Network → Firewall: ON
# Allow incoming for: Node.js, Python, BlueBubbles
# Or via CLI:
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
```

**Disable automatic macOS updates (you want to control when a server reboots):**
```
System Settings → General → Software Update → Automatic Updates → OFF
```

**Set hostname:**
```bash
sudo scutil --set HostName pib-mini
sudo scutil --set LocalHostName pib-mini
sudo scutil --set ComputerName pib-mini
```

**Set timezone:**
```bash
sudo systemsetup -settimezone America/New_York
```

---

## Phase 1: Software Dependencies

### 1.1 Xcode Command Line Tools
```bash
xcode-select --install
```

### 1.2 Homebrew
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# Follow the "Add to PATH" instructions it prints
```

### 1.3 Node.js (LTS)
```bash
brew install node@22
# Verify:
node --version   # Should be v22.x
npm --version
```

### 1.4 Python 3.12+
```bash
brew install python@3.12
# Verify:
python3 --version   # Should be 3.12.x
pip3 --version
```

### 1.5 Git
```bash
brew install git
git config --global user.name "PIB"
git config --global user.email "pib@stice-sclafani.local"
```

### 1.6 SQLite (macOS ships with it, but get latest for FTS5)
```bash
brew install sqlite
# Verify FTS5 support:
sqlite3 ':memory:' "CREATE VIRTUAL TABLE t USING fts5(x); SELECT 1;" 
# Should return 1
```

### 1.7 Optional but recommended
```bash
brew install jq              # JSON processing in scripts
brew install htop             # Process monitoring
brew install tmux             # Persistent terminal sessions
```

---

## Phase 2: OpenClaw Install

### 2.1 Install OpenClaw
```bash
npm install -g openclaw
# Verify:
openclaw --version
```

### 2.2 Initialize Workspace
```bash
openclaw init
# This creates ~/.openclaw/ with default workspace
```

### 2.3 Verify Gateway Starts
```bash
openclaw gateway start
openclaw gateway status
# Should show: Running, bound to port
openclaw gateway stop
# We'll start it for real after all config is done
```

### 2.4 Note Workspace Location
```bash
# Default workspace is at:
ls ~/.openclaw/workspace/
# This is where SOUL.md, AGENTS.md, scripts/, etc. will live
```

---

## Phase 3: Credentials & API Keys

### 3.1 GitHub (for cloning c40v)

```bash
# Option A: SSH key (recommended)
ssh-keygen -t ed25519 -C "pib-mini"
cat ~/.ssh/id_ed25519.pub
# Add this key to github.com → Settings → SSH Keys

# Test:
ssh -T git@github.com
# Should say: Hi junglecrunch1212!

# Option B: Personal access token
# github.com → Settings → Developer Settings → Personal Access Tokens → Fine-grained
# Permissions: repo (read/write) on junglecrunch1212/chief-40-vermont
```

### 3.2 Google (Calendar, Sheets, Gmail, Contacts)

```bash
# gog ships with OpenClaw
gog auth login
# This opens a browser → sign in with jrstice@gmail.com
# Grants access to: Calendar, Sheets, Gmail, Drive, Contacts

# Verify:
gog calendar list --no-input
# Should show all calendars

gog sheets list --no-input
# Should show accessible spreadsheets

# If you need Laura's calendar access too:
gog auth login --account lcholland12@gmail.com
```

### 3.3 Anthropic

```bash
# Get API key from: console.anthropic.com → API Keys
# Make sure billing is active and credits are loaded

# Store it (OpenClaw will read from env or config):
openclaw config set ANTHROPIC_API_KEY sk-ant-xxxxxxxxxxxxx
# Or add to ~/.openclaw/openclaw.json
```

### 3.4 Twilio (SMS)

```bash
# Get from: console.twilio.com
# Need: Account SID, Auth Token, Phone Number

# Store:
export TWILIO_ACCOUNT_SID=ACxxxxxxxxxx
export TWILIO_AUTH_TOKEN=xxxxxxxxxx
export TWILIO_PHONE_NUMBER=+1xxxxxxxxxx

# Configure webhook URL (Twilio console → Phone Number → Messaging → Webhook):
# https://your-domain-or-ngrok/webhooks/twilio
# (You'll need a public URL — see Phase 5 for options)
```

### 3.5 BlueBubbles (iMessage)

```bash
# Install BlueBubbles server on the Mac Mini itself:
# Download from: https://bluebubbles.app/downloads/
# Run BlueBubbles.app
# Sign in with your Apple ID
# Enable: Private API (for typing indicators, read receipts, reactions)
# Set server password (you'll need this for the webhook secret)
# Note the local URL (usually http://localhost:1234)

# Configure webhook in BlueBubbles:
# Settings → Webhooks → Add webhook
# URL: http://localhost:{openclaw-port}/webhooks/bluebubbles
# Events: New Message

# Store credentials:
export BLUEBUBBLES_URL=http://localhost:1234
export BLUEBUBBLES_PASSWORD=your-server-password
```

### 3.6 Apple ID (for BlueBubbles)
- Sign in to iMessage on the Mac Mini via Messages.app
- BlueBubbles piggybacks on this — it uses the Mac's native iMessage
- Make sure Messages.app stays logged in (don't sign out)
- Enable: System Settings → Apple ID → iCloud → Messages: ON

### 3.7 Signal (if using Signal channel via OpenClaw)
```bash
# OpenClaw has native Signal support
# Follow OpenClaw docs for Signal channel setup:
openclaw channel add signal
# This will guide you through linking a Signal account
```

### 3.8 WhatsApp (if using WhatsApp channel via OpenClaw)
```bash
openclaw channel add whatsapp
# Follow QR code linking flow
```

---

## Phase 4: OpenClaw Agent Configuration

These files go in the OpenClaw workspace. They are **minimal and clean** — just enough to tell the agent what it is and how to deploy c40v. The agent will expand them during deployment.

### 4.1 SOUL.md (personality + rules)

Create `~/.openclaw/workspace/SOUL.md`:

```markdown
# SOUL.md — PIB (Poopsy-in-a-Box)

You are PIB — the Stice-Sclafani household Chief of Staff.

## Prime Directives
1. Deterministic data layer first. LLM for presentation, never for data classification.
2. Offline-first. If any external API is down, degrade gracefully.
3. Privacy fence. Laura's work calendar content never enters your context.
4. One thing at a time. James has ADHD. Never present lists of 5+.
5. Never guilt, shame, or compare family members.
6. Celebrate completions. Always.

## Your Architecture
- You run on OpenClaw (L0: infrastructure — channels, cron, model routing)
- Your brain is chief-40-vermont (L1: SQLite + deterministic engine, L2: LLM intelligence)
- See docs/openclaw-integration.md for the full integration spec

## Deployment
Your first task is to deploy chief-40-vermont per docs/openclaw-integration.md.
After deployment, your SOUL.md will be expanded with full personality and coaching protocols
from the build spec (pib-v5-build-spec.md §2).
```

### 4.2 AGENTS.md (routing + capabilities)

Create `~/.openclaw/workspace/AGENTS.md`:

```markdown
# AGENTS.md — PIB Deployment Agent

## Mission
Deploy chief-40-vermont on this OpenClaw instance per docs/openclaw-integration.md.

## Phase 1: Deploy
1. Clone chief-40-vermont repo
2. Install Python package (pip install -e ".[dev]")
3. Write pib/src/pib/cli.py (the CLI integration surface)
4. Initialize SQLite (apply migrations, seed data)
5. Write OpenClaw cron jobs (from integration spec §3.3)
6. Write scripts/core/ wrappers (from integration spec §4)
7. Build console server
8. Expand SOUL.md from build spec
9. Write routing tables in this file
10. Run all probes from integration spec §9

## Phase 2: Operate
After deployment, this file will contain message routing tables.
See integration spec §4.2 for the pattern.

## Hard Rules
- Read docs/openclaw-integration.md FIRST before any build work
- Read docs/pib-v5-build-spec.md for domain knowledge
- NEVER put LLM in the data path (Gene 1, Gene 5, Gene 7)
- All writes go through state machine guards
- Test with pytest before declaring done
```

### 4.3 USER.md (family context)

Create `~/.openclaw/workspace/USER.md`:

```markdown
# USER.md — Household

- James (43, stay-at-home dad, ADHD) — jrstice@gmail.com, +14048495800
- Laura (38, family law partner) — lcholland12@gmail.com, +13364080952
- Charlie (6, shared custody with coparent Mike)
- Baby girl arriving May 2026
- Captain (dog, needs exercise 2x/day)
- Location: Atlanta, GA (America/New_York)
- Custody: Thursday evenings Charlie with bio dad Mike
- Laura WFH: Tue/Fri. Office: Mon/Wed/Thu (leaves ~9:30am, home ~6:30pm)
- Charlie school: 8am–5:30pm M-F (aftercare)
```

### 4.4 HEARTBEAT.md

Create `~/.openclaw/workspace/HEARTBEAT.md`:

```markdown
# HEARTBEAT.md

Run: python -m pib.cli health --json

Report any items with status "error" or "warn". If all "ok", reply HEARTBEAT_OK.

Also check:
- gog calendar list --no-input (Google auth still valid?)
- Console server responding on port 3333?
```

### 4.5 MEMORY.md (start empty)

Create `~/.openclaw/workspace/MEMORY.md`:

```markdown
# MEMORY.md

(Fresh instance. Memories will accumulate from operation.)
```

### 4.6 TOOLS.md

Create `~/.openclaw/workspace/TOOLS.md`:

```markdown
# TOOLS.md

## Python CLI (PIB engine)
All PIB domain logic is accessed via: python -m pib.cli <command> --json
See docs/openclaw-integration.md §6 for all subcommands.
Working directory: ~/.openclaw/workspace/pib/
Database: ~/.openclaw/workspace/state/pib.db

## Google Workspace
Use gog CLI (ships with OpenClaw):
- gog calendar [list|events|create] --account jrstice@gmail.com
- gog sheets [get|set] <sheet_id> <range>
- gog gmail [list|read|send]

## Console
Node.js server at ~/.openclaw/workspace/console/server.mjs
Port: 3333
Start: node console/server.mjs
```

---

## Phase 5: Network & Ports

### 5.1 Port Allocation

| Port | Service | Notes |
|------|---------|-------|
| 3141 | PIB Python API (if needed for direct access) | Optional — CLI is primary interface |
| 3333 | Console dashboard | Kitchen TV scoreboard, web UI |
| 18789 | OpenClaw gateway | Internal, don't expose externally |
| 1234 | BlueBubbles server | Local only |

### 5.2 Local Network Access

For the kitchen TV / tablet scoreboard:
```bash
# Find Mac Mini's local IP:
ipconfig getifaddr en0
# e.g., 192.168.1.100

# Scoreboard URL for TV: http://192.168.1.100:3333/scoreboard
# Console URL: http://192.168.1.100:3333/
```

### 5.3 External Access (for Twilio/Siri webhooks)

Options, in order of preference:

**Option A: Cloudflare Tunnel (recommended — free, no port forwarding)**
```bash
brew install cloudflared
cloudflared tunnel login
cloudflared tunnel create pib
cloudflared tunnel route dns pib pib.yourdomain.com
# Then configure as a launchd service for auto-start
```

**Option B: Tailscale (for personal access only)**
```bash
brew install tailscale
# Simple VPN, no public exposure. Good for SSH + console access.
# Not suitable for Twilio webhooks (needs public URL).
```

**Option C: ngrok (quick testing, not production)**
```bash
brew install ngrok
ngrok http 18789
```

### 5.4 Router Settings (if not using Cloudflare Tunnel)
- Reserve a static IP for the Mac Mini (DHCP reservation by MAC address)
- Port forward 3333 if you want console access from outside local network
- Do NOT port forward 18789 (OpenClaw gateway) — use tunnel instead

---

## Phase 6: Auto-Start & Resilience

### 6.1 OpenClaw Gateway (launchd)

Create `~/Library/LaunchAgents/com.openclaw.gateway.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openclaw.gateway</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/openclaw</string>
        <string>gateway</string>
        <string>start</string>
        <string>--foreground</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/openclaw-gateway.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/openclaw-gateway-err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>/Users/james</string>
    </dict>
</dict>
</plist>
```

```bash
# Load it:
launchctl load ~/Library/LaunchAgents/com.openclaw.gateway.plist

# Verify:
launchctl list | grep openclaw
```

### 6.2 Console Server (launchd)

Create `~/Library/LaunchAgents/com.pib.console.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pib.console</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/node</string>
        <string>/Users/james/.openclaw/workspace/console/server.mjs</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/Users/james/.openclaw/workspace</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PORT</key>
        <string>3333</string>
        <key>PIB_DB_PATH</key>
        <string>/Users/james/.openclaw/workspace/state/pib.db</string>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/pib-console.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/pib-console-err.log</string>
</dict>
</plist>
```

### 6.3 BlueBubbles (auto-start)
- BlueBubbles.app → Settings → Start on Login: ON
- Or add to: System Settings → General → Login Items

---

## Phase 7: Pre-Flight Checklist

Run through this BEFORE telling OpenClaw to deploy c40v:

```
HARDWARE & OS
[ ] Mac Mini powered on, connected to network
[ ] Sleep disabled (sudo pmset -a sleep 0)
[ ] Auto-restart after power failure enabled
[ ] SSH enabled (can connect from laptop)
[ ] Timezone set to America/New_York
[ ] Hostname set to pib-mini

SOFTWARE
[ ] Xcode CLT installed
[ ] Homebrew installed
[ ] Node.js 22.x installed
[ ] Python 3.12+ installed
[ ] Git installed
[ ] SQLite with FTS5 verified

OPENCLAW
[ ] openclaw installed globally
[ ] openclaw init completed
[ ] Gateway starts and stops cleanly
[ ] Workspace exists at ~/.openclaw/workspace/

CREDENTIALS
[ ] GitHub SSH key added, ssh -T git@github.com works
[ ] gog auth login completed for jrstice@gmail.com
[ ] gog calendar list returns calendars
[ ] gog sheets list works
[ ] Anthropic API key set, credits loaded
[ ] (Optional) Twilio creds set, webhook URL configured
[ ] (Optional) BlueBubbles installed, logged into iMessage, server running
[ ] (Optional) Signal channel linked
[ ] (Optional) WhatsApp channel linked

AGENT FILES
[ ] SOUL.md written (from §4.1 above)
[ ] AGENTS.md written (from §4.2 above)
[ ] USER.md written (from §4.3 above)
[ ] HEARTBEAT.md written (from §4.4 above)
[ ] MEMORY.md created (empty, from §4.5 above)
[ ] TOOLS.md written (from §4.6 above)

NETWORK
[ ] Local IP noted (for scoreboard URL)
[ ] Port 3333 accessible from local network
[ ] (Optional) Cloudflare tunnel or ngrok for external webhooks

AUTO-START
[ ] OpenClaw gateway launchd plist installed and loaded
[ ] Console server launchd plist ready (will activate after c40v deploy)
[ ] BlueBubbles set to start on login
```

---

## Phase 8: The Deployment Command

Once every checkbox is green, open OpenClaw webchat or your preferred channel and say:

```
Read docs/openclaw-integration.md in the chief-40-vermont repo at 
https://github.com/junglecrunch1212/chief-40-vermont. 

Clone the repo into this workspace. Follow the integration spec to deploy 
PIB v5 on this OpenClaw instance. The spec has everything: what to keep, 
what to replace, file structure, the CLI to write, cron jobs, and success probes.

Start with Phase 1 from AGENTS.md. Run all probes from integration spec §9 
when done.
```

The agent has:
- The integration spec (what to build)
- The build spec (domain knowledge)
- CLAUDE.md (repo orientation)
- All credentials wired
- All tools available (gog, python, node, git)
- Clean workspace with no prior assumptions

It should be able to execute the entire deployment autonomously, stopping only if it hits a gate that needs your approval.

---

## Phase 9: Post-Deploy Verification

After the agent reports deployment complete, verify yourself:

```bash
# 1. Engine works
python -m pib.cli what-now --member m-james --json

# 2. Tests pass
cd ~/.openclaw/workspace/pib && pytest tests/ -v

# 3. Console serves
curl http://localhost:3333/api/household-status

# 4. Scoreboard loads
open http://localhost:3333/scoreboard

# 5. Calendar syncs
gog calendar events --from $(date +%Y-%m-%d) --json | head -5
python -m pib.cli calendar-ingest --json

# 6. Messaging works (send from your phone)
# Text "what's next?" via Signal/WhatsApp/iMessage
# Should get a response with whatNow() result

# 7. Heartbeat
# Wait for next heartbeat cycle, should report HEARTBEAT_OK

# 8. Kitchen TV
# Open http://192.168.1.xxx:3333/scoreboard on the TV browser
```

---

## Appendix: Credential Reference

| Service | Where to get it | What you need |
|---------|----------------|---------------|
| GitHub | github.com → Settings → SSH Keys | SSH public key |
| Google | `gog auth login` (browser flow) | jrstice@gmail.com password + 2FA |
| Anthropic | console.anthropic.com → API Keys | API key + loaded credits |
| Twilio | console.twilio.com | Account SID, Auth Token, Phone Number |
| BlueBubbles | bluebubbles.app | Apple ID signed into iMessage on Mac |
| Signal | OpenClaw channel setup | Signal account to link |
| WhatsApp | OpenClaw channel setup | WhatsApp account to link |

## Appendix: Estimated Time

| Phase | Time |
|-------|------|
| 0: Mac setup | 15 min |
| 1: Software install | 20 min |
| 2: OpenClaw install | 5 min |
| 3: Credentials | 30-45 min (Google auth + Anthropic + optional channels) |
| 4: Agent files | 10 min (copy from this doc) |
| 5: Network | 10-20 min |
| 6: Auto-start | 10 min |
| 7: Checklist | 10 min |
| **Total human effort** | **~2 hours** |
| 8: Agent deploys c40v | 2-4 hours (autonomous) |
| 9: Verification | 15 min |
