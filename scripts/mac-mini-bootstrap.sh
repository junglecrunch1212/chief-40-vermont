#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# PIB v5 — Mac Mini One-Shot Bootstrap
# ═══════════════════════════════════════════════════════════════════════════════
#
# WHAT THIS DOES:
#   Step 1: Installs Homebrew, python@3.12, node@22, git, sqlite, age
#   Step 2: Clones chief-40-vermont, creates /opt/pib, runs bootstrap.sh --dev
#   Step 3: Installs OpenClaw, sets up agent workspaces, starts gateway
#
# PREREQUISITES:
#   - Fresh Mac Mini with macOS Sequoia 15+
#   - Xcode Command Line Tools (script will prompt if missing)
#   - Internet connection
#   - Your Anthropic API key ready to paste
#   - SSH key added to GitHub (for private repo clone)
#
# USAGE:
#   curl -fsSL <url> | bash        # or just paste into Terminal
#   bash mac-mini-bootstrap.sh      # if saved locally
#
# TIME: ~20 minutes (mostly waiting for brew/npm installs)
# ROLLBACK: rm -rf /opt/pib ~/.openclaw && brew uninstall --force python@3.12 node@22
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

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

# ─── Config ───
PIB_HOME="/opt/pib"
PIB_REPO="$PIB_HOME/repo"
PIB_DB="$PIB_HOME/data/pib.db"
GITHUB_REPO="git@github.com:junglecrunch1212/chief-40-vermont.git"
OPENCLAW_BASE="$HOME/.openclaw"

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          PIB v5 — Mac Mini One-Shot Bootstrap               ║"
echo "║          Stice-Sclafani Household Chief-of-Staff            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "This script will:"
echo "  1. Install system dependencies (Homebrew, Python, Node, etc.)"
echo "  2. Clone repo, create DB, install Python + Node packages"
echo "  3. Set up OpenClaw gateway with 3 agent workspaces"
echo ""
echo "Estimated time: ~20 minutes"
echo "Requires: sudo (once, for /opt/pib), GitHub SSH access"
echo ""
read -p "Press Enter to start (Ctrl+C to abort)..."

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: SYSTEM DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════════════

step "STEP 1/3: System Dependencies"

# 1a. Xcode Command Line Tools
if ! xcode-select -p &>/dev/null; then
  echo "  Installing Xcode Command Line Tools..."
  xcode-select --install
  echo ""
  ask "  >>> Click 'Install' in the popup, then press Enter here when done..."
  read -r
else
  ok "Xcode CLI tools already installed"
fi

# 1b. Homebrew
if ! command -v brew &>/dev/null; then
  echo "  Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  
  # Add to PATH for this session + future shells
  if [[ -f /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
  fi
  ok "Homebrew installed"
else
  ok "Homebrew already installed"
fi

# 1c. Core packages
echo "  Installing packages (python@3.12, node@22, sqlite, git, age)..."
brew install python@3.12 node@22 sqlite git age 2>/dev/null || true

# Verify
for cmd in python3.12 node npm sqlite3 git age; do
  if command -v "$cmd" &>/dev/null; then
    ok "$cmd: $($cmd --version 2>&1 | head -1)"
  else
    fail "$cmd not found after brew install"
  fi
done

# 1d. OpenClaw
if ! command -v openclaw &>/dev/null; then
  echo "  Installing OpenClaw CLI..."
  npm install -g @openclaw/cli
  ok "OpenClaw: $(openclaw --version 2>/dev/null || echo 'installed')"
else
  ok "OpenClaw already installed: $(openclaw --version 2>/dev/null || echo 'present')"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: CLONE + BOOTSTRAP
# ═══════════════════════════════════════════════════════════════════════════════

step "STEP 2/3: Repository + Database + Packages"

# 2a. Create /opt/pib
if [ ! -d "$PIB_HOME" ]; then
  echo "  Creating $PIB_HOME (requires sudo)..."
  sudo mkdir -p "$PIB_HOME"/{data,logs,config,data/backups}
  sudo chown -R "$(whoami):staff" "$PIB_HOME"
  chmod 700 "$PIB_HOME" "$PIB_HOME/config"
  ok "Directory structure created"
else
  ok "$PIB_HOME already exists"
fi

# 2b. SSH key check
if [ ! -f "$HOME/.ssh/id_ed25519" ] && [ ! -f "$HOME/.ssh/id_rsa" ]; then
  warn "No SSH key found. Generating one for GitHub..."
  ssh-keygen -t ed25519 -C "pib-mini@stice" -f "$HOME/.ssh/id_ed25519" -N ""
  echo ""
  ask "  >>> Add this key to GitHub (Settings → SSH Keys):"
  echo ""
  cat "$HOME/.ssh/id_ed25519.pub"
  echo ""
  ask "  >>> Then press Enter to continue..."
  read -r
fi

# 2c. Clone repo
if [ ! -d "$PIB_REPO" ]; then
  echo "  Cloning chief-40-vermont..."
  # Test SSH access first
  if ! ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    warn "GitHub SSH auth failed. Trying HTTPS instead..."
    GITHUB_REPO="https://github.com/junglecrunch1212/chief-40-vermont.git"
  fi
  git clone "$GITHUB_REPO" "$PIB_REPO"
  ok "Repository cloned to $PIB_REPO"
else
  ok "Repository already exists at $PIB_REPO"
  cd "$PIB_REPO" && git pull --ff-only 2>/dev/null || warn "git pull failed (not critical)"
fi

# 2d. Python venv + deps
echo "  Setting up Python virtual environment..."
if [ ! -d "$PIB_HOME/venv" ]; then
  python3.12 -m venv "$PIB_HOME/venv"
fi
source "$PIB_HOME/venv/bin/activate"
pip install --upgrade pip -q
pip install -e "$PIB_REPO[dev]" -q
ok "Python venv + PIB package installed"

# 2e. .env file
ENV_FILE="$PIB_HOME/config/.env"
if [ ! -f "$ENV_FILE" ]; then
  cp "$PIB_REPO/config/.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  
  # Prompt for Anthropic key now (the one thing we need immediately)
  echo ""
  ask "  >>> Paste your Anthropic API key (sk-ant-...):"
  read -r ANTHROPIC_KEY
  if [[ -n "$ANTHROPIC_KEY" ]]; then
    sed -i '' "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$ANTHROPIC_KEY|" "$ENV_FILE"
    ok "Anthropic key saved to .env"
  else
    warn "No key entered — you'll need to edit $ENV_FILE later"
  fi
  
  # Set timezone + dev mode
  sed -i '' "s|^PIB_ENV=.*|PIB_ENV=dev|" "$ENV_FILE"
  sed -i '' "s|^PIB_STRICT_STARTUP=.*|PIB_STRICT_STARTUP=0|" "$ENV_FILE"
  ok ".env created at $ENV_FILE"
else
  ok ".env already exists"
fi

# 2f. Seed database
echo "  Creating + seeding database..."
if [ -f "$PIB_REPO/scripts/seed_data.py" ]; then
  PIB_DB_PATH="$PIB_DB" python "$PIB_REPO/scripts/seed_data.py" "$PIB_DB" 2>&1 | tail -5
  chmod 600 "$PIB_DB" 2>/dev/null || true
  ok "Database: $PIB_DB"
  
  # Quick integrity check
  TABLES=$(sqlite3 "$PIB_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "?")
  MEMBERS=$(sqlite3 "$PIB_DB" "SELECT COUNT(*) FROM common_members WHERE active=1;" 2>/dev/null || echo "?")
  ok "  $TABLES tables, $MEMBERS active members"
else
  warn "seed_data.py not found — running bootstrap.sh instead"
  cd "$PIB_REPO" && bash scripts/bootstrap.sh --dev --noninteractive 2>&1 | tail -10
fi

# 2g. Console node_modules
if [ -d "$PIB_REPO/console" ] && [ -f "$PIB_REPO/console/package.json" ]; then
  echo "  Installing console dependencies..."
  cd "$PIB_REPO/console" && npm install -q 2>/dev/null
  ok "Console node_modules installed"
fi

# 2h. Quick smoke test
echo "  Running smoke test..."
if python -m pib.cli health "$PIB_DB" --json 2>/dev/null | grep -q '"status"'; then
  ok "PIB CLI health check passed"
else
  warn "PIB CLI health check returned non-standard output (may be fine in dev mode)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: OPENCLAW GATEWAY + AGENT WORKSPACES
# ═══════════════════════════════════════════════════════════════════════════════

step "STEP 3/3: OpenClaw Gateway + Agent Workspaces"

# 3a. Create agent workspaces from templates
for agent in cos coach dev; do
  WS_DIR="$OPENCLAW_BASE/workspace-$agent"
  TMPL_DIR="$PIB_REPO/workspace-template/$agent"
  
  mkdir -p "$WS_DIR"
  
  # Copy .md files from agent-specific template
  if [ -d "$TMPL_DIR" ]; then
    cp "$TMPL_DIR/"*.md "$WS_DIR/" 2>/dev/null || true
    ok "workspace-$agent: template files copied"
  fi
  
  # Copy shared scripts if they exist
  if [ -d "$PIB_REPO/workspace-template/shared" ]; then
    cp -r "$PIB_REPO/workspace-template/shared/scripts" "$WS_DIR/" 2>/dev/null || true
  fi
done

# 3b. Google OAuth
echo ""
echo "  Google Calendar/Sheets access requires OAuth login."
echo "  This opens a browser — sign in with jrstice@gmail.com"
echo ""
ask "  >>> Run 'gog auth login' now? (y/n)"
read -r DO_GOG
if [[ "$DO_GOG" =~ ^[Yy] ]]; then
  if command -v gog &>/dev/null; then
    gog auth login
    
    # Verify
    if gog calendar list 2>/dev/null | grep -q "calendar"; then
      ok "Google OAuth working — calendars accessible"
    else
      warn "OAuth completed but calendar list failed — may need retry"
    fi
  else
    warn "gog CLI not found — install with: npm install -g @openclaw/gog"
  fi
else
  warn "Skipped Google OAuth — run 'gog auth login' before calendar features work"
fi

# 3c. Configure OpenClaw with Anthropic key
echo "  Configuring OpenClaw..."
ANTHROPIC_KEY_FROM_ENV=$(grep '^ANTHROPIC_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)
if [[ -n "$ANTHROPIC_KEY_FROM_ENV" && "$ANTHROPIC_KEY_FROM_ENV" != "sk-ant-..." ]]; then
  # Set the key in OpenClaw's config too
  openclaw config set anthropic_api_key "$ANTHROPIC_KEY_FROM_ENV" 2>/dev/null || true
  ok "Anthropic key configured in OpenClaw"
fi

# 3d. Start gateway
echo "  Starting OpenClaw gateway..."
openclaw gateway stop 2>/dev/null || true
sleep 1
openclaw gateway start 2>/dev/null && ok "Gateway started" || warn "Gateway start failed — may need manual config first"

# 3e. Start console server
echo "  Starting console server..."
cd "$PIB_REPO/console"
PIB_DB_PATH="$PIB_DB" PIB_ENV=dev PORT=3333 nohup node server.mjs > "$PIB_HOME/logs/console.log" 2>&1 &
CONSOLE_PID=$!
sleep 2

if kill -0 "$CONSOLE_PID" 2>/dev/null; then
  ok "Console running on http://localhost:3333 (PID: $CONSOLE_PID)"
else
  warn "Console failed to start — check $PIB_HOME/logs/console.log"
fi

# 3f. Install launchd service (auto-start on boot)
PLIST_SRC="$PIB_REPO/config/com.pib.runtime.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.pib.runtime.plist"
if [ -f "$PLIST_SRC" ]; then
  mkdir -p "$HOME/Library/LaunchAgents"
  cp "$PLIST_SRC" "$PLIST_DST"
  ok "Launchd plist installed (load with: launchctl load $PLIST_DST)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                    BOOTSTRAP COMPLETE                        ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Status checks
echo -e "${BOLD}Status:${NC}"
[ -f "$PIB_DB" ]                       && ok "Database: $PIB_DB" || warn "Database: MISSING"
curl -s http://localhost:3333/api/health 2>/dev/null | grep -q status \
                                        && ok "Console: http://localhost:3333" || warn "Console: not responding"
openclaw gateway status 2>/dev/null | grep -qi "running" \
                                        && ok "Gateway: running" || warn "Gateway: check 'openclaw gateway status'"
gog calendar list 2>/dev/null | grep -q "calendar" \
                                        && ok "Google OAuth: working" || warn "Google OAuth: run 'gog auth login'"

echo ""
echo -e "${BOLD}Paths:${NC}"
echo "  Repo:      $PIB_REPO"
echo "  Database:  $PIB_DB"
echo "  Config:    $ENV_FILE"
echo "  Logs:      $PIB_HOME/logs/"
echo "  Workspaces:"
echo "    CoS:     $OPENCLAW_BASE/workspace-cos/"
echo "    Coach:   $OPENCLAW_BASE/workspace-coach/"
echo "    Dev:     $OPENCLAW_BASE/workspace-dev/"

echo ""
echo -e "${BOLD}Next steps:${NC}"
echo "  1. Open http://localhost:3333 in browser — verify console loads"
echo "  2. If Google OAuth skipped: gog auth login"
echo "  3. Edit $ENV_FILE for optional integrations (Twilio, BlueBubbles)"
echo "  4. Test: source $PIB_HOME/venv/bin/activate && python -m pib.cli what-now $PIB_DB --member m-james --json"
echo "  5. Auto-start on boot: launchctl load ~/Library/LaunchAgents/com.pib.runtime.plist"
echo ""
echo -e "${BOLD}Useful commands:${NC}"
echo "  openclaw gateway status          # Check gateway"
echo "  openclaw gateway restart         # Restart gateway"
echo "  tail -f $PIB_HOME/logs/*.log     # Watch logs"
echo "  sqlite3 $PIB_DB '.tables'        # Inspect database"
echo "  pytest $PIB_REPO/tests/ -v       # Run test suite"
echo ""
echo -e "${GREEN}${BOLD}Done! Open http://localhost:3333 and send 'what's next?' in chat.${NC}"
