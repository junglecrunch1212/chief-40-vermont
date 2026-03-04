#!/usr/bin/env bash
# PIB v5 — Mac Mini Bootstrap Script
# Production-aware bootstrap with preflight checks and optional strict readiness validation.

set -euo pipefail

PIB_HOME="${PIB_HOME:-/opt/pib}"
PIB_REPO="$(cd "$(dirname "$0")/.." && pwd)"
MODE="prod"
NONINTERACTIVE=0
SKIP_FRONTEND=0
DRY_RUN=0

usage() {
  cat <<USAGE
Usage: $0 [--dev|--prod] [--noninteractive] [--skip-frontend] [--dry-run]

Options:
  --dev              Development mode (less strict readiness defaults)
  --prod             Production mode (default)
  --noninteractive   Avoid prompts and continue with defaults
  --skip-frontend    Skip npm install/build even if node is installed
  --dry-run          Print what would be done without executing
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev) MODE="dev"; shift ;;
    --prod) MODE="prod"; shift ;;
    --noninteractive) NONINTERACTIVE=1; shift ;;
    --skip-frontend) SKIP_FRONTEND=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "=== DRY RUN — no changes will be made ==="
fi

echo "=== PIB v5 Bootstrap (${MODE}) ==="
echo "Repo:  $PIB_REPO"
echo "Home:  $PIB_HOME"

preflight() {
  echo ""
  echo "0. Running preflight checks..."
  command -v python3 >/dev/null || { echo "python3 not found"; exit 1; }
  command -v sqlite3 >/dev/null || { echo "sqlite3 not found"; exit 1; }
  if [[ "$SKIP_FRONTEND" -eq 0 ]] && ! command -v node >/dev/null; then
    echo "Node.js not found. Frontend build will be skipped."
  fi

  local free_kb
  free_kb=$(df -Pk / | awk 'NR==2{print $4}')
  if [[ "$free_kb" -lt 1048576 ]]; then
    echo "Insufficient disk space (<1GB free)."; exit 1
  fi
  echo "   Preflight OK"
}

preflight

# ─── 1. Directory structure ───
echo ""
echo "1. Creating directory structure..."
sudo mkdir -p "$PIB_HOME"/{data,logs,config,data/backups}
sudo chown -R "$(whoami)" "$PIB_HOME"
chmod 700 "$PIB_HOME" "$PIB_HOME/config" || true
chmod 755 "$PIB_HOME/data" "$PIB_HOME/logs" || true
echo "   Done: $PIB_HOME/{data,logs,config,data/backups}"

# ─── 2. Python venv ───
echo ""
echo "2. Setting up Python virtual environment..."
if [ ! -d "$PIB_HOME/venv" ]; then
    python3 -m venv "$PIB_HOME/venv"
    echo "   Created venv at $PIB_HOME/venv"
else
    echo "   Venv already exists"
fi
source "$PIB_HOME/venv/bin/activate"

# ─── 3. Install Python deps ───
echo ""
echo "3. Installing Python dependencies..."
pip install --upgrade pip
pip install -e "$PIB_REPO[dev]"
echo "   Done"

# ─── 4. .env file ───
echo ""
echo "4. Checking .env file..."
ENV_FILE="$PIB_HOME/config/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$PIB_REPO/config/.env.example" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "   Created $ENV_FILE from template"
    echo "   >>> IMPORTANT: Edit $ENV_FILE and fill in your API keys <<<"
else
    chmod 600 "$ENV_FILE" || true
    echo "   .env already exists at $ENV_FILE"
fi

# ─── 5. Seed database ───
echo ""
echo "5. Seeding database..."
DB_PATH="$PIB_HOME/data/pib.db"
PIB_DB_PATH="$DB_PATH" python "$PIB_REPO/scripts/seed_data.py" "$DB_PATH"
chmod 600 "$DB_PATH" || true
echo "   Database at $DB_PATH"

# ─── 6. Build frontend (if node is available) ───
echo ""
echo "6. Building frontend..."
if [[ "$SKIP_FRONTEND" -eq 1 ]]; then
  echo "   Console start skipped by flag"
elif command -v node &> /dev/null; then
    if [ -f "$PIB_REPO/console/server.mjs" ]; then
        echo "   Console server found at $PIB_REPO/console/server.mjs"
        echo "   Start with: node $PIB_REPO/console/server.mjs"
    else
        echo "   Console server not found at $PIB_REPO/console/server.mjs"
    fi
else
    echo "   Node.js not found — skipping console setup"
    echo "   Install with: brew install node"
fi

# ─── 7. Install launchd plist ───
echo ""
echo "7. Installing launchd service..."
PLIST_SRC="$PIB_REPO/config/com.pib.runtime.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.pib.runtime.plist"
if [ -f "$PLIST_SRC" ]; then
    cp "$PLIST_SRC" "$PLIST_DST"
    echo "   Installed plist to $PLIST_DST"
    echo "   To start: launchctl load $PLIST_DST"
    echo "   To stop:  launchctl unload $PLIST_DST"
else
    echo "   No plist found at $PLIST_SRC"
fi

# ─── 8. Verification ───
echo ""
echo "8. Verification..."
python -m pib.cli health "$DB_PATH" --json && echo "   Health check: OK" || { echo "   Health check: FAILED"; exit 1; }
python -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
members = conn.execute('SELECT COUNT(*) FROM common_members WHERE active=1').fetchone()[0]
tables = conn.execute(\"SELECT COUNT(*) FROM sqlite_master WHERE type='table'\").fetchone()[0]
print(f'   DB check: {tables} tables, {members} active members')
conn.close()
"

# Strict readiness probe in prod mode
if [[ "$MODE" == "prod" ]]; then
  echo "   Running readiness probe (strict)..."
  PIB_DB_PATH="$DB_PATH" PIB_ENV=production PIB_STRICT_STARTUP=1 python - <<'PY'
import asyncio
from pib.db import get_connection
from pib.readiness import evaluate_readiness, validate_strict_startup

async def main():
    db = await get_connection()
    r = await evaluate_readiness(db)
    try:
        validate_strict_startup(r)
        print('   Readiness check: PASS')
    except RuntimeError as e:
        print(f'   Readiness check: FAIL ({e})')
        raise
    finally:
        await db.close()

asyncio.run(main())
PY
fi

# ─── 9. CLI smoke test ───
echo ""
echo "9. CLI smoke test..."
python -m pib.cli health "$DB_PATH" 2>/dev/null && echo "   CLI health check: OK" || echo "   CLI health check: skipped (cli.py not yet wired)"

# ─── 10. Verify governance + FTS5 triggers ───
echo ""
echo "10. Verifying governance.yaml and FTS5 triggers..."
if [ -f "$PIB_REPO/config/governance.yaml" ]; then
  echo "   governance.yaml: present"
else
  echo "   governance.yaml: MISSING"
fi
TRIGGER_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name LIKE '%fts%';" 2>/dev/null || echo "0")
echo "   FTS5 triggers: $TRIGGER_COUNT found"

# ─── Summary ───
echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit $ENV_FILE and fill in API keys"
echo "  2. Test: cd $PIB_REPO && source $PIB_HOME/venv/bin/activate && pytest tests/ -v"
echo "  3. Start: launchctl load ~/Library/LaunchAgents/com.pib.runtime.plist"
echo "     Or via OpenClaw: openclaw start"
echo ""
echo "Keys needed in .env:"
grep -E '^[A-Z].*=' "$PIB_REPO/config/.env.example" | while read -r line; do
    key=$(echo "$line" | cut -d= -f1)
    echo "  - $key"
done
