#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# PIB v5 — CoS Mac Mini One-Shot Bootstrap
# ═══════════════════════════════════════════════════════════════════════════════
#
# WHAT THIS DOES:
#   Step 1: Hardens macOS for 24/7 server use (sleep, hostname, timezone, SSH)
#   Step 2: Installs Homebrew, python@3.12, node@22, git, sqlite, age
#   Step 3: Clones chief-40-vermont, creates /opt/pib, installs Python + Node deps
#   Step 4: Installs OpenClaw, creates 3 agent workspaces, writes multi-agent config
#   Step 5: Seeds database, starts services, runs verification
#
# SCOPE: CoS hub only (pib-mini). Bridge Minis (james-mini, laura-mini) are
#         separate machines — see the Bootstrap Wizard app or PERSONAL_MINI_SETUP.md.
#
# PREREQUISITES:
#   - Mac Mini M2 or M4, 16GB RAM, macOS Sequoia 15+
#   - Internet connection
#   - Anthropic API key ready to paste
#   - SSH key added to GitHub (for private repo clone)
#
# USAGE:
#   bash mac-mini-bootstrap.sh              # interactive (recommended first time)
#   bash mac-mini-bootstrap.sh --dry-run    # print what would run, change nothing
#
# TIME: ~25 minutes (mostly waiting for brew/npm installs)
#
# ROLLBACK:
#   launchctl unload ~/Library/LaunchAgents/com.pib.*.plist 2>/dev/null
#   rm -rf /opt/pib ~/.openclaw
#   npm uninstall -g openclaw
#   brew uninstall --force python@3.12 node@22
#
# TOPOLOGY (for reference):
#   ┌─────────────────────────┐
#   │    CoS Mac Mini (Hub)   │  ← THIS SCRIPT SETS UP THIS MACHINE
#   │   pib-mini.local :3333  │
#   │  OpenClaw + PIB brain   │
#   └────────┬───────┬────────┘
#            │       │
#       LAN  │       │  LAN
#            ▼       ▼
#   ┌──────────────┐  ┌──────────────┐
#   │ James's Mini │  │ Laura's Mini │   ← NOT covered by this script
#   │ BlueBubbles  │  │ BlueBubbles  │
#   │ Shortcuts    │  │ Shortcuts    │
#   │ HomeKit      │  │              │
#   └──────────────┘  └──────────────┘
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Options ───
DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) head -45 "$0" | tail -40; exit 0 ;;
    *) echo "Unknown arg: $1. Use --dry-run or --help."; exit 1 ;;
  esac
done

# ─── Colors ───
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

step()  { echo -e "\n${CYAN}${BOLD}═══ $1 ═══${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; exit 1; }
ask()   { echo -e "${YELLOW}$1${NC}"; }

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo -e "  ${YELLOW}[DRY RUN]${NC} $*"
  else
    "$@"
  fi
}

# ─── Config ───
PIB_HOME="/opt/pib"
PIB_REPO="$PIB_HOME/pib"               # matches BOOTSTRAP_INSTRUCTIONS.md
PIB_DB="$PIB_HOME/data/pib.db"
GITHUB_REPO="git@github.com:junglecrunch1212/chief-40-vermont.git"
GITHUB_HTTPS="https://github.com/junglecrunch1212/chief-40-vermont.git"
OPENCLAW_BASE="$HOME/.openclaw"
VENV_DIR="$PIB_HOME/venv"
ENV_FILE="$PIB_HOME/config/.env"

# Detect architecture once (affects Homebrew path)
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then
  BREW_PREFIX="/opt/homebrew"
else
  BREW_PREFIX="/usr/local"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo -e "${YELLOW}${BOLD}═══ DRY RUN — no changes will be made ═══${NC}"
  echo ""
fi

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         PIB v5 — CoS Mac Mini One-Shot Bootstrap           ║"
echo "║         Stice-Sclafani Household Chief-of-Staff             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "Architecture: $ARCH (Homebrew prefix: $BREW_PREFIX)"
echo ""
echo "This script sets up the CoS hub (pib-mini) with:"
echo "  1. macOS server hardening (sleep, hostname, timezone, SSH)"
echo "  2. System dependencies (Homebrew, Python 3.12, Node 22, SQLite)"
echo "  3. PIB codebase (clone, venv, npm install, tests)"
echo "  4. OpenClaw gateway + 3 agent workspaces (CoS, Coach, Dev)"
echo "  5. Database seed, service start, verification"
echo ""
echo "Estimated time: ~25 minutes"
echo "Requires: sudo (twice — pmset + /opt/pib), GitHub SSH access"
echo ""
echo "NOTE: Bridge Minis (james-mini, laura-mini) are separate machines."
echo "      Use the Bootstrap Wizard or PERSONAL_MINI_SETUP.md for those."
echo ""
read -p "Press Enter to start (Ctrl+C to abort)..."


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: macOS SERVER HARDENING
# ═══════════════════════════════════════════════════════════════════════════════

step "STEP 1/5: macOS Server Hardening"

# 1a. Prevent sleep — this is a 24/7 server
echo "  Configuring power management (requires sudo)..."
run sudo pmset -a sleep 0 disksleep 0 displaysleep 0 hibernatemode 0 powernap 0
run sudo pmset -a autorestart 1
ok "Sleep disabled, auto-restart on power failure enabled"

# 1b. Set hostname + timezone
echo "  Setting hostname to pib-mini..."
run sudo scutil --set HostName pib-mini
run sudo scutil --set LocalHostName pib-mini
run sudo scutil --set ComputerName "PIB Mini"
run sudo systemsetup -settimezone America/New_York 2>/dev/null || true
ok "Hostname: pib-mini, Timezone: America/New_York"

# 1c. Note local IP for bridge configuration
LOCAL_IP=$(ifconfig en0 2>/dev/null | grep 'inet ' | awk '{print $2}' || echo "unknown")
ok "Local IP: $LOCAL_IP (bridges use pib-mini.local or this IP)"

echo ""
echo "  Manual steps (System Settings UI):"
echo "    • General → Sharing → Remote Login: ON"
echo "    • Network → Firewall: ON (allow Node.js, Python)"
echo "    • General → Software Update → Automatic Updates: OFF"
echo "    • General → Login Items → Automatic Login: ON"


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: SYSTEM DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════════════

step "STEP 2/5: System Dependencies"

# 2a. Xcode Command Line Tools
if ! xcode-select -p &>/dev/null; then
  echo "  Installing Xcode Command Line Tools..."
  run xcode-select --install
  echo ""
  ask "  >>> Click 'Install' in the popup, then press Enter here when done..."
  read -r
else
  ok "Xcode CLI tools already installed"
fi

# 2b. Homebrew
if ! command -v brew &>/dev/null; then
  echo "  Installing Homebrew..."
  run /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  # Add to PATH for this session + future shells
  if [[ -f "$BREW_PREFIX/bin/brew" ]]; then
    eval "$("$BREW_PREFIX/bin/brew" shellenv)"
    echo "eval \"\$($BREW_PREFIX/bin/brew shellenv)\"" >> "$HOME/.zprofile"
  fi
  ok "Homebrew installed"
else
  ok "Homebrew already installed ($(brew --prefix))"
fi

# 2c. Core packages
echo "  Installing packages (python@3.12, node@22, sqlite, git, age, jq)..."
run brew install python@3.12 node@22 sqlite git age jq 2>/dev/null || true

# 2d. Verify — use python3 (not python3.12) since brew symlink varies
echo "  Verifying installations..."
for cmd in python3 node npm sqlite3 git age; do
  if command -v "$cmd" &>/dev/null; then
    ok "$cmd: $($cmd --version 2>&1 | head -1)"
  else
    fail "$cmd not found after brew install"
  fi
done

# Verify Python is Homebrew's, not macOS system
PYTHON_PATH=$(which python3)
if [[ "$PYTHON_PATH" == "/usr/bin/python3" ]]; then
  warn "python3 resolves to macOS system Python ($PYTHON_PATH)"
  warn "Homebrew Python should be at $BREW_PREFIX/bin/python3"
  warn "Run: brew link python@3.12 --force"
else
  ok "Python path: $PYTHON_PATH (not system)"
fi

# Verify Python version is 3.12+
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "unknown")
if [[ "$PY_VERSION" == "3.12" || "$PY_VERSION" > "3.12" ]]; then
  ok "Python version: $PY_VERSION"
else
  warn "Expected Python 3.12+, got $PY_VERSION"
fi

# Verify SQLite has FTS5
if sqlite3 ':memory:' "CREATE VIRTUAL TABLE _fts_test USING fts5(x); DROP TABLE _fts_test; SELECT 1;" 2>/dev/null | grep -q "1"; then
  ok "SQLite FTS5: working"
else
  warn "SQLite FTS5 not available — run: brew install sqlite && brew link sqlite --force"
fi


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: CLONE + INSTALL PIB
# ═══════════════════════════════════════════════════════════════════════════════

step "STEP 3/5: Repository + Python + Console"

# 3a. Create /opt/pib directory structure
if [ ! -d "$PIB_HOME" ]; then
  echo "  Creating $PIB_HOME (requires sudo)..."
  run sudo mkdir -p "$PIB_HOME"/{data,logs,config,data/backups}
  run sudo chown -R "$(whoami):staff" "$PIB_HOME"
  run chmod 700 "$PIB_HOME" "$PIB_HOME/config"
  run chmod 755 "$PIB_HOME/data" "$PIB_HOME/logs"
  ok "Directory structure created"
else
  ok "$PIB_HOME already exists"
fi

# 3b. SSH key check
if [ ! -f "$HOME/.ssh/id_ed25519" ] && [ ! -f "$HOME/.ssh/id_rsa" ]; then
  warn "No SSH key found. Generating one for GitHub..."
  run ssh-keygen -t ed25519 -C "pib-mini@stice" -f "$HOME/.ssh/id_ed25519" -N ""
  echo ""
  ask "  >>> Add this public key to GitHub (Settings → SSH Keys):"
  echo ""
  cat "$HOME/.ssh/id_ed25519.pub"
  echo ""
  ask "  >>> Then press Enter to continue..."
  read -r
fi

# 3c. Clone repo (to /opt/pib/pib — matches BOOTSTRAP_INSTRUCTIONS.md)
if [ ! -d "$PIB_REPO" ]; then
  echo "  Cloning chief-40-vermont..."
  # Test SSH access first
  if ssh -T git@github.com 2>&1 | grep -qi "successfully authenticated"; then
    run git clone "$GITHUB_REPO" "$PIB_REPO"
    ok "Repository cloned via SSH to $PIB_REPO"
  else
    warn "GitHub SSH auth not confirmed. Trying HTTPS..."
    run git clone "$GITHUB_HTTPS" "$PIB_REPO"
    ok "Repository cloned via HTTPS to $PIB_REPO"
  fi
else
  ok "Repository already exists at $PIB_REPO"
  cd "$PIB_REPO" && git pull --ff-only 2>/dev/null && ok "git pull: updated" || warn "git pull failed (not critical)"
fi

# 3d. Python venv + install PIB package
echo "  Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
  run python3 -m venv "$VENV_DIR"
  ok "Created venv at $VENV_DIR"
else
  ok "Venv already exists"
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  source "$VENV_DIR/bin/activate"
  pip install --upgrade pip -q
  pip install -e "$PIB_REPO[dev]" -q
  ok "Python venv activated + PIB package installed"
else
  echo "  [DRY RUN] Would activate venv and pip install"
fi

# 3e. .env file
if [ ! -f "$ENV_FILE" ]; then
  run cp "$PIB_REPO/config/.env.example" "$ENV_FILE"
  run chmod 600 "$ENV_FILE"

  # Prompt for Anthropic key (the one thing we need immediately)
  echo ""
  ask "  >>> Paste your Anthropic API key (sk-ant-...):"
  read -r ANTHROPIC_KEY
  if [[ -n "$ANTHROPIC_KEY" && "$ANTHROPIC_KEY" != "sk-ant-..." ]]; then
    if [[ "$DRY_RUN" -eq 0 ]]; then
      sed -i '' "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$ANTHROPIC_KEY|" "$ENV_FILE"
    fi
    ok "Anthropic key saved to .env"
  else
    warn "No key entered — edit $ENV_FILE later"
  fi

  # Generate SIRI_BEARER_TOKEN (needed for bridge Shortcuts later)
  SIRI_TOKEN=$(openssl rand -hex 32)
  if [[ "$DRY_RUN" -eq 0 ]]; then
    sed -i '' "s|^SIRI_BEARER_TOKEN=.*|SIRI_BEARER_TOKEN=$SIRI_TOKEN|" "$ENV_FILE"
  fi
  ok "SIRI_BEARER_TOKEN generated (copy to bridges later)"

  # Set dev mode defaults
  if [[ "$DRY_RUN" -eq 0 ]]; then
    sed -i '' "s|^PIB_ENV=.*|PIB_ENV=dev|" "$ENV_FILE"
    sed -i '' "s|^PIB_STRICT_STARTUP=.*|PIB_STRICT_STARTUP=0|" "$ENV_FILE"
  fi
  ok ".env created at $ENV_FILE"
else
  ok ".env already exists"
fi

# 3f. Console node_modules
if [ -d "$PIB_REPO/console" ] && [ -f "$PIB_REPO/console/package.json" ]; then
  echo "  Installing console dependencies..."
  cd "$PIB_REPO/console" && run npm install --silent 2>/dev/null
  ok "Console node_modules installed"
fi

# 3g. Run test suite
echo "  Running test suite..."
if [[ "$DRY_RUN" -eq 0 ]]; then
  cd "$PIB_REPO"
  RESULT=$(pytest tests/ --tb=short -q 2>&1 | tail -1)
  if echo "$RESULT" | grep -q "passed"; then
    ok "Tests: $RESULT"
  else
    warn "Tests: $RESULT"
    warn "Some tests may fail without full env — continuing"
  fi
else
  echo "  [DRY RUN] Would run pytest tests/ -v"
fi


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: OPENCLAW + MULTI-AGENT WORKSPACES
# ═══════════════════════════════════════════════════════════════════════════════

step "STEP 4/5: OpenClaw Gateway + Agent Workspaces"

# 4a. Install OpenClaw
if ! command -v openclaw &>/dev/null; then
  echo "  Installing OpenClaw CLI..."
  run npm install -g openclaw@latest
  ok "OpenClaw: $(openclaw --version 2>/dev/null || echo 'installed')"
else
  ok "OpenClaw already installed: $(openclaw --version 2>/dev/null || echo 'present')"
fi

# 4b. Run onboarding (creates ~/.openclaw/, auth token, workspace, optional daemon)
if [ ! -d "$OPENCLAW_BASE" ]; then
  echo "  Running OpenClaw onboarding..."
  echo ""
  echo "  The onboard wizard will prompt for:"
  echo "    • Workspace path (accept default)"
  echo "    • Model provider (choose Anthropic)"
  echo "    • API key (paste same key as above)"
  echo "    • Install as daemon (say YES)"
  echo ""
  run openclaw onboard --install-daemon
  ok "OpenClaw onboarded"
else
  ok "OpenClaw workspace already exists at $OPENCLAW_BASE"
fi

# 4c. Configure Anthropic key in OpenClaw
ANTHROPIC_KEY_FROM_ENV=$(grep '^ANTHROPIC_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)
if [[ -n "$ANTHROPIC_KEY_FROM_ENV" && "$ANTHROPIC_KEY_FROM_ENV" != "sk-ant-..." ]]; then
  # Set via openclaw config (dotpath format per docs)
  run openclaw config set anthropic.api_key "$ANTHROPIC_KEY_FROM_ENV" 2>/dev/null || true
  ok "Anthropic key configured in OpenClaw"
fi

# 4d. Copy agent workspace templates (per-agent directories)
echo "  Setting up multi-agent workspaces..."
for agent in cos coach dev; do
  WS_DIR="$OPENCLAW_BASE/workspace-$agent"
  TMPL_DIR="$PIB_REPO/workspace-template/$agent"

  run mkdir -p "$WS_DIR"

  if [ -d "$TMPL_DIR" ] && ls "$TMPL_DIR"/*.md 1>/dev/null 2>&1; then
    run cp "$TMPL_DIR/"*.md "$WS_DIR/"
    ok "workspace-$agent: $(ls "$TMPL_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ') template files copied"
  else
    warn "No .md files found in $TMPL_DIR"
  fi
done

# 4e. Write multi-agent config into openclaw.json
echo "  Writing multi-agent configuration..."
OPENCLAW_JSON="$OPENCLAW_BASE/openclaw.json"

if [[ "$DRY_RUN" -eq 0 ]] && [ -f "$OPENCLAW_JSON" ]; then
  # Back up existing config before modifying
  cp "$OPENCLAW_JSON" "$OPENCLAW_JSON.bak.$(date +%s)"
  ok "Backed up existing openclaw.json"

  # Merge multi-agent config using jq (installed in step 2)
  if command -v jq &>/dev/null; then
    AGENTS_CONFIG=$(cat <<'AGENTS_JSON'
{
  "agents": {
    "list": [
      {
        "id": "pib-cos",
        "name": "PIB — Chief of Staff",
        "workspace": "~/.openclaw/workspace-cos",
        "model": "anthropic/claude-sonnet-4-5",
        "default": true
      },
      {
        "id": "pib-coach",
        "name": "PIB — Coach",
        "workspace": "~/.openclaw/workspace-coach",
        "model": "anthropic/claude-sonnet-4-5"
      },
      {
        "id": "pib-dev",
        "name": "Poopsy-Dev",
        "workspace": "~/.openclaw/workspace-dev",
        "model": "anthropic/claude-opus-4-6"
      }
    ]
  },
  "bindings": [
    { "agentId": "pib-cos", "match": { "channel": "imessage" } },
    { "agentId": "pib-cos", "match": { "channel": "signal" } },
    { "agentId": "pib-cos", "match": { "channel": "webchat" } },
    { "agentId": "pib-coach", "match": { "channel": "imessage", "peer": { "kind": "direct", "id": "coach" } } },
    { "agentId": "pib-dev", "match": { "channel": "webchat", "peer": { "kind": "direct", "id": "admin" } } }
  ]
}
AGENTS_JSON
)
    # Merge: existing config + agent config (agent config wins on conflict)
    jq -s '.[0] * .[1]' "$OPENCLAW_JSON" <(echo "$AGENTS_CONFIG") > "$OPENCLAW_JSON.tmp" \
      && mv "$OPENCLAW_JSON.tmp" "$OPENCLAW_JSON"
    ok "Multi-agent config written (3 agents, 5 bindings)"
  else
    warn "jq not available — multi-agent config must be added manually to openclaw.json"
    warn "See config/openclaw-agents.yaml for the agent definitions"
  fi
elif [[ "$DRY_RUN" -eq 1 ]]; then
  echo "  [DRY RUN] Would merge multi-agent config into openclaw.json"
elif [ ! -f "$OPENCLAW_JSON" ]; then
  warn "openclaw.json not found — run 'openclaw onboard' first"
fi

# 4f. Google OAuth
echo ""
echo "  Google Calendar/Sheets access requires OAuth login."
echo "  This opens a browser — sign in with jrstice@gmail.com"
echo ""
ask "  >>> Run 'gog auth login' now? (y/n)"
read -r DO_GOG
if [[ "$DO_GOG" =~ ^[Yy] ]]; then
  if command -v gog &>/dev/null; then
    run gog auth login
    # Verify
    if [[ "$DRY_RUN" -eq 0 ]] && gog calendar list --no-input 2>/dev/null | grep -qi "calendar"; then
      ok "Google OAuth working — calendars accessible"
    else
      warn "OAuth flow completed — verify with: gog calendar list"
    fi
  else
    warn "gog CLI not found — it ships with OpenClaw"
    warn "Try: openclaw --version && which gog"
    warn "Or run Google OAuth later: gog auth login"
  fi
else
  warn "Skipped Google OAuth — run 'gog auth login' before calendar features work"
fi


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: DATABASE + SERVICES + VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

step "STEP 5/5: Database + Services + Verification"

# 5a. Seed database (two-phase: Python schema+config, then Node demo data)
echo "  Creating + seeding database..."
if [[ "$DRY_RUN" -eq 0 ]]; then
  # Export env vars for CLI
  set -a && source "$ENV_FILE" && set +a
  export PIB_DB_PATH="$PIB_DB"
  export PIB_CALLER_AGENT=dev

  # Phase 1: Python — schema, migrations, members, config, calendars, custody
  if [ -f "$PIB_REPO/scripts/seed_data.py" ]; then
    cd "$PIB_REPO"
    python "$PIB_REPO/scripts/seed_data.py" "$PIB_DB" 2>&1 | tail -10
    if [ ! -f "$PIB_DB" ]; then
      fail "seed_data.py ran but no database file created at $PIB_DB"
    fi
    chmod 600 "$PIB_DB" 2>/dev/null || true
    ok "Phase 1 (Python): schema + config seeded"
  else
    warn "seed_data.py not found — running bootstrap.sh instead"
    cd "$PIB_REPO" && bash scripts/bootstrap.sh --dev --noninteractive 2>&1 | tail -10
  fi

  # Verify migrations applied
  TABLES=$(sqlite3 "$PIB_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "0")
  if [ "$TABLES" -lt 10 ]; then
    fail "Only $TABLES tables found — migrations may not have applied. Check seed_data.py output above."
  fi

  # Phase 2: Node — demo tasks, streaks, energy, scoreboard, lists, calendar events
  # This makes the console show real data instead of empty tabs
  if [ -f "$PIB_REPO/console/seed.mjs" ]; then
    echo "  Seeding demo data (tasks, streaks, scoreboard, lists)..."
    cd "$PIB_REPO" && node console/seed.mjs "$PIB_DB" 2>&1 | tail -10
    ok "Phase 2 (Node): demo data seeded"
  else
    warn "console/seed.mjs not found — console tabs will show empty state"
  fi

  # Integrity summary
  MEMBERS=$(sqlite3 "$PIB_DB" "SELECT COUNT(*) FROM common_members WHERE active=1;" 2>/dev/null || echo "?")
  TASKS=$(sqlite3 "$PIB_DB" "SELECT COUNT(*) FROM ops_tasks;" 2>/dev/null || echo "0")
  TRIGGERS=$(sqlite3 "$PIB_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name LIKE '%fts%';" 2>/dev/null || echo "0")
  ok "Database: $PIB_DB ($TABLES tables, $MEMBERS members, $TASKS tasks, $TRIGGERS FTS5 triggers)"
else
  echo "  [DRY RUN] Would seed database at $PIB_DB"
fi

# 5b. CLI smoke test
echo "  Running CLI smoke test..."
if [[ "$DRY_RUN" -eq 0 ]]; then
  if python -m pib.cli health "$PIB_DB" --json 2>/dev/null | grep -q '"status"'; then
    ok "PIB CLI health check passed"
  else
    warn "PIB CLI health check returned non-standard output (may be fine in dev mode)"
  fi
else
  echo "  [DRY RUN] Would run: python -m pib.cli health $PIB_DB --json"
fi

# 5c. Install launchd plists for auto-start
echo "  Installing launchd services..."
mkdir -p "$HOME/Library/LaunchAgents"

# Gateway plist (from repo)
GATEWAY_PLIST_SRC="$PIB_REPO/config/com.pib.runtime.plist"
GATEWAY_PLIST_DST="$HOME/Library/LaunchAgents/com.pib.runtime.plist"
if [ -f "$GATEWAY_PLIST_SRC" ]; then
  run cp "$GATEWAY_PLIST_SRC" "$GATEWAY_PLIST_DST"
  ok "Gateway plist installed"
fi

# Console plist (generated — not in repo template)
CONSOLE_PLIST_DST="$HOME/Library/LaunchAgents/com.pib.console.plist"
if [[ "$DRY_RUN" -eq 0 ]]; then
  cat > "$CONSOLE_PLIST_DST" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pib.console</string>

    <key>ProgramArguments</key>
    <array>
        <string>${BREW_PREFIX}/bin/node</string>
        <string>${PIB_REPO}/console/server.mjs</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PIB_REPO}/console</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PIB_DB_PATH</key>
        <string>${PIB_DB}</string>
        <key>PIB_CONSOLE_PORT</key>
        <string>3333</string>
        <key>PIB_ENV</key>
        <string>dev</string>
        <key>NODE_ENV</key>
        <string>production</string>
        <key>PATH</key>
        <string>${BREW_PREFIX}/bin:/usr/local/bin:${VENV_DIR}/bin:/usr/bin:/bin</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>5</integer>

    <key>StandardOutPath</key>
    <string>${PIB_HOME}/logs/console-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>${PIB_HOME}/logs/console-stderr.log</string>
</dict>
</plist>
PLIST_EOF
  ok "Console plist generated (port 3333)"
else
  echo "  [DRY RUN] Would generate console plist"
fi

# 5d. Start services
echo "  Starting services..."

# Stop anything running first
run openclaw gateway stop 2>/dev/null || true
launchctl unload "$GATEWAY_PLIST_DST" 2>/dev/null || true
launchctl unload "$CONSOLE_PLIST_DST" 2>/dev/null || true
sleep 1

if [[ "$DRY_RUN" -eq 0 ]]; then
  # Start via launchd (survives reboot)
  launchctl load "$GATEWAY_PLIST_DST" 2>/dev/null && ok "Gateway service loaded" || warn "Gateway load failed — try: openclaw gateway start"
  launchctl load "$CONSOLE_PLIST_DST" 2>/dev/null && ok "Console service loaded" || warn "Console load failed"
  sleep 3

  # Verify console is responding
  if curl -sf http://localhost:3333/api/health 2>/dev/null | grep -q "status"; then
    ok "Console responding on http://localhost:3333"
  elif curl -sf http://localhost:3333/api/pulse 2>/dev/null | grep -q "{"; then
    ok "Console responding on http://localhost:3333"
  else
    warn "Console not responding yet — check: tail $PIB_HOME/logs/console-stderr.log"
  fi

  # Verify gateway
  if openclaw gateway status 2>/dev/null | grep -qi "running"; then
    ok "OpenClaw gateway running"
  else
    warn "Gateway status unclear — check: openclaw gateway status"
  fi
else
  echo "  [DRY RUN] Would load launchd plists for gateway + console"
fi

# 5e. Verify governance + agent capabilities
echo "  Verifying config files..."
[ -f "$PIB_REPO/config/governance.yaml" ]          && ok "governance.yaml present" || warn "governance.yaml MISSING"
[ -f "$PIB_REPO/config/agent_capabilities.yaml" ]  && ok "agent_capabilities.yaml present" || warn "agent_capabilities.yaml MISSING"
[ -f "$PIB_REPO/config/bridge_identities.yaml" ]   && ok "bridge_identities.yaml present" || warn "bridge_identities.yaml MISSING"


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                CoS HUB BOOTSTRAP COMPLETE                   ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo -e "${YELLOW}${BOLD}  DRY RUN — nothing was changed. Remove --dry-run to execute.${NC}"
  echo ""
  exit 0
fi

# Status checks
echo -e "${BOLD}Status:${NC}"
[ -f "$PIB_DB" ] && ok "Database: $PIB_DB ($(du -h "$PIB_DB" | cut -f1))" || warn "Database: MISSING"
curl -sf http://localhost:3333/api/health 2>/dev/null | grep -q status \
  && ok "Console: http://localhost:3333" || warn "Console: not responding"
openclaw gateway status 2>/dev/null | grep -qi "running" \
  && ok "Gateway: running (port 18789)" || warn "Gateway: check 'openclaw gateway status'"
gog calendar list --no-input 2>/dev/null | grep -qi "calendar" \
  && ok "Google OAuth: working" || warn "Google OAuth: run 'gog auth login'"

echo ""
echo -e "${BOLD}Paths:${NC}"
echo "  Repo:              $PIB_REPO"
echo "  Database:          $PIB_DB"
echo "  Config:            $ENV_FILE"
echo "  Logs:              $PIB_HOME/logs/"
echo "  Gateway plist:     $GATEWAY_PLIST_DST"
echo "  Console plist:     $CONSOLE_PLIST_DST"
echo "  Workspaces:"
echo "    CoS:             $OPENCLAW_BASE/workspace-cos/"
echo "    Coach:           $OPENCLAW_BASE/workspace-coach/"
echo "    Dev:             $OPENCLAW_BASE/workspace-dev/"

echo ""
echo -e "${BOLD}Agents (in openclaw.json):${NC}"
echo "  pib-cos   → Sonnet 4.5 → iMessage, Signal, webchat (default)"
echo "  pib-coach → Sonnet 4.5 → iMessage (keyword: coach), webchat"
echo "  pib-dev   → Opus 4.6   → webchat only (admin)"

echo ""
echo -e "${BOLD}Next steps:${NC}"
echo "  1. Open http://localhost:3333 — verify console loads"
echo "  2. Test brain:"
echo "     source $VENV_DIR/bin/activate"
echo "     set -a && source $ENV_FILE && set +a"
echo "     python -m pib.cli what-now $PIB_DB --member m-james --json"
echo "  3. Run full verification:"
echo "     python -m pib.cli bootstrap-verify $PIB_DB --json"
echo "  4. If Google OAuth was skipped: gog auth login"
echo "  5. Edit $ENV_FILE for bridge secrets (when setting up bridge Minis):"
echo "     • BLUEBUBBLES_JAMES_SECRET (openssl rand -hex 32)"
echo "     • BLUEBUBBLES_LAURA_SECRET (openssl rand -hex 32)"
echo "     • SIRI_BEARER_TOKEN is already generated — copy it to bridges"
echo ""
echo -e "${BOLD}Bridge Minis (separate machines, separate script):${NC}"
echo "  Use the Bootstrap Wizard or PERSONAL_MINI_SETUP.md to set up:"
echo "  • james-mini.local — BlueBubbles, Shortcuts, Homebridge, HomeKit"
echo "  • laura-mini.local — BlueBubbles, Shortcuts (no HomeKit)"
echo ""
echo -e "${BOLD}Useful commands:${NC}"
echo "  openclaw gateway status          # Check gateway"
echo "  openclaw gateway restart         # Restart gateway"
echo "  launchctl list | grep pib        # Check launchd services"
echo "  tail -f $PIB_HOME/logs/*.log     # Watch logs"
echo "  sqlite3 $PIB_DB '.tables'        # Inspect database"
echo "  pytest $PIB_REPO/tests/ -v       # Run test suite"
echo ""
echo -e "${GREEN}${BOLD}CoS hub is running. Brain works standalone — no bridges needed yet.${NC}"
echo -e "${GREEN}Text commands work via webchat at localhost:3333.${NC}"
echo -e "${GREEN}iMessage requires bridge Minis (james-mini / laura-mini).${NC}"
