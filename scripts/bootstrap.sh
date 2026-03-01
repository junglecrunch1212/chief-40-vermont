#!/usr/bin/env bash
# PIB v5 — Mac Mini Bootstrap Script
# Creates directory structure, installs deps, seeds DB, installs launchd plist.
# Run once on a fresh Mac Mini. Idempotent (safe to re-run).

set -euo pipefail

PIB_HOME="/opt/pib"
PIB_REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== PIB v5 Bootstrap ==="
echo "Repo:  $PIB_REPO"
echo "Home:  $PIB_HOME"

# ─── 1. Directory structure ───
echo ""
echo "1. Creating directory structure..."
sudo mkdir -p "$PIB_HOME"/{data,logs,config,data/backups}
sudo chown -R "$(whoami)" "$PIB_HOME"
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
    echo "   .env already exists at $ENV_FILE"
fi

# ─── 5. Seed database ───
echo ""
echo "5. Seeding database..."
DB_PATH="$PIB_HOME/data/pib.db"
PIB_DB_PATH="$DB_PATH" python "$PIB_REPO/scripts/seed_data.py" "$DB_PATH"
echo "   Database at $DB_PATH"

# ─── 6. Build frontend (if node is available) ───
echo ""
echo "6. Building frontend..."
if command -v node &> /dev/null; then
    if [ -d "$PIB_REPO/frontend" ]; then
        cd "$PIB_REPO/frontend"
        if [ ! -d "node_modules" ]; then
            npm install
        fi
        npm run build
        echo "   Frontend built to $PIB_REPO/static/"
    fi
else
    echo "   Node.js not found — skipping frontend build"
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
python -c "from pib.web import app; print('   Import check: OK')"
python -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
members = conn.execute('SELECT COUNT(*) FROM common_members WHERE active=1').fetchone()[0]
tables = conn.execute(\"SELECT COUNT(*) FROM sqlite_master WHERE type='table'\").fetchone()[0]
print(f'   DB check: {tables} tables, {members} active members')
conn.close()
"

# ─── Summary ───
echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit $ENV_FILE and fill in API keys"
echo "  2. Test: cd $PIB_REPO && source $PIB_HOME/venv/bin/activate && pytest tests/ -v"
echo "  3. Start: launchctl load ~/Library/LaunchAgents/com.pib.runtime.plist"
echo "     Or manual: uvicorn pib.web:app --port 3141"
echo ""
echo "Keys needed in .env:"
grep -E '^[A-Z].*=' "$PIB_REPO/config/.env.example" | while read line; do
    key=$(echo "$line" | cut -d= -f1)
    echo "  - $key"
done
