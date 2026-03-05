# PIB v5 — Bootstrap Instructions

**Target:** Fresh Mac Mini M2+ running macOS Sequoia 15+
**Goal:** Go from unboxed hardware to operational PIB household system
**Time:** ~2 hours (including Google OAuth setup)

---

## Prerequisites

- Mac Mini M2 or later
- macOS Sequoia 15.0+
- Stable internet connection
- Admin account access
- Anthropic API key
- Google Workspace account (for Calendar, Sheets, Gmail)
- Twilio account (SMS fallback)
- BlueBubbles instances (optional, for iMessage)

---

## Phase 1: System Setup

### 1.1 Install Homebrew
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### 1.2 Install Dependencies
```bash
brew install python@3.12 node@22 sqlite git age
brew install --cask cloudflare-warp  # Optional: Cloudflare Tunnel
```

### 1.3 Install OpenClaw
```bash
npm install -g @openclaw/cli
openclaw --version
```

---

## Phase 2: Workspace & Code Setup

### 2.1 Create Working Directory
```bash
sudo mkdir -p /opt/pib/{data,logs,config,backups}
sudo chown -R $(whoami):staff /opt/pib
```

### 2.2 Clone PIB Repository
```bash
cd /opt/pib
git clone https://github.com/junglecrunch1212/chief-40-vermont.git repo
cd repo
```

### 2.3 Install Python Dependencies
```bash
python3.12 -m venv /opt/pib/venv
source /opt/pib/venv/bin/activate
pip install -e ".[dev]"
```

### 2.4 Initialize OpenClaw Workspace
```bash
openclaw init --workspace ~/.openclaw/workspace-cos
cd ~/.openclaw/workspace-cos
cp /opt/pib/repo/workspace-template/cos/* .
```

---

## Phase 3: Credentials & Config

### 3.1 Create `.env` File
```bash
cd /opt/pib/repo
cp config/.env.example config/.env
chmod 600 config/.env
```

Edit `config/.env` and fill in:
- `ANTHROPIC_API_KEY` — from console.anthropic.com
- `TWILIO_*` — from twilio.com/console
- `GOOGLE_SA_KEY_PATH` — will create in next step
- `BLUEBUBBLES_*_SECRET` and `BLUEBUBBLES_*_URL` — from each bridge Mac Mini
- `SIRI_BEARER_TOKEN` — generate with `openssl rand -hex 32`
- `BACKUP_PUBLIC_KEY` — generate with `age-keygen`

### 3.2 Google OAuth Setup
```bash
# Install gog CLI (included with OpenClaw)
gog auth login

# Follow browser OAuth flow
# Grant access to: Calendar, Sheets, Gmail, Drive

# Verify
gog calendar list
```

### 3.3 Google Service Account (for server-side access)
1. Go to console.cloud.google.com
2. Create new project: "PIB Household"
3. Enable APIs: Calendar, Sheets, Gmail, Drive
4. Create Service Account
5. Download JSON key → save to `/opt/pib/config/google-sa-key.json`
6. Share calendars with service account email

---

## Phase 4: Database Initialization

### 4.1 Create SQLite Database
```bash
cd /opt/pib/repo
source /opt/pib/venv/bin/activate
export PIB_DB_PATH=/opt/pib/data/pib.db

# Run bootstrap (applies schema + seed data)
python -m pib.cli bootstrap $PIB_DB_PATH
```

Expected output:
```
✓ Schema initialized (47 tables created)
✓ Migrations applied (current version: 4)
✓ Seed data loaded (2 members, 3 sources, 12 calendar mappings)
✓ FTS5 indexes created
Database ready: /opt/pib/data/pib.db (4.2 MB)
```

### 4.2 Verify Database Health
```bash
python -m pib.cli health $PIB_DB_PATH --json
```

Expected: `"status": "healthy"`

---

## Phase 5: Console Server Setup

### 5.1 Install Console Dependencies
```bash
cd /opt/pib/repo/console
npm install
```

### 5.2 Test Console Server
```bash
PIB_DB_PATH=/opt/pib/data/pib.db \
PIB_CONSOLE_PORT=3333 \
node server.mjs
```

Open browser: http://localhost:3333
Expected: Dashboard loads with empty state

Press Ctrl+C to stop server

---

## Phase 6: OpenClaw Gateway Configuration

### 6.1 Configure Agent Instances
```bash
cd ~/.openclaw/workspace-cos
cat > openclaw.json <<EOF
{
  "agent_id": "pib-cos",
  "model": "anthropic/claude-sonnet-4-5",
  "capabilities": "none",
  "channels": ["imessage", "signal", "webchat"]
}
EOF
```

Repeat for coach and dev workspaces (see config/openclaw-agents.yaml for each)

### 6.2 Start Gateway
```bash
openclaw gateway start
```

Verify:
```bash
openclaw gateway status
```

Expected: `Status: running`

---

## Phase 7: Launchd Service Setup (Auto-start on Boot)

### 7.1 Install Service
```bash
cd /opt/pib/repo
sudo cp config/com.pib.runtime.plist /Library/LaunchDaemons/
sudo launchctl load /Library/LaunchDaemons/com.pib.runtime.plist
```

### 7.2 Verify Service
```bash
sudo launchctl list | grep pib
```

Expected: `com.pib.runtime` with PID

### 7.3 Check Logs
```bash
tail -f /opt/pib/logs/pib-stdout.log
```

---

## Phase 8: Calendar Sync & First Run

### 8.1 Trigger Initial Calendar Sync
```bash
cd ~/.openclaw/workspace-cos
node scripts/core/calendar_sync.mjs --full
```

Expected: 12 calendars synced, events classified

### 8.2 Compute Daily States
```bash
python -m pib.cli compute-daily-states $PIB_DB_PATH
```

Expected: `Daily state computed for 2026-03-05`

### 8.3 Test whatNow()
```bash
python -m pib.cli what-now $PIB_DB_PATH --member m-james --json
```

Expected: JSON with `the_one_task` field

---

## Phase 9: Webhook Setup (Optional)

### 9.1 Twilio SMS Webhook
In Twilio console:
- Phone Number Settings → Messaging
- Webhook URL: `https://pib.yourdomain.com/api/webhooks/twilio`
- Method: POST

### 9.2 BlueBubbles Webhooks
On each bridge Mac Mini:
```bash
# BlueBubbles → Settings → Webhooks
URL: http://pib-mini.local:3333/api/webhooks/bluebubbles/james
Secret: <BLUEBUBBLES_JAMES_SECRET from .env>
Events: message.created
```

### 9.3 Google Sheets Webhook (optional)
Apps Script trigger for Live OS sheet:
```javascript
function onEdit(e) {
  UrlFetchApp.fetch("http://pib-mini.local:3333/api/webhooks/sheets", {
    method: "post",
    payload: JSON.stringify({
      sheet: e.source.getName(),
      range: e.range.getA1Notation(),
      value: e.value
    }),
    headers: { "Authorization": "Bearer " + PropertiesService.getScriptProperties().getProperty("PIB_TOKEN") }
  });
}
```

---

## Phase 10: Verification Checklist

Run these probes to verify system health:

### ✓ Database
```bash
sqlite3 $PIB_DB_PATH "PRAGMA integrity_check"
# Expected: ok
```

### ✓ Calendar Sync
```bash
python -m pib.cli calendar-query $PIB_DB_PATH --date today --json | jq '.events | length'
# Expected: >0 (number of events today)
```

### ✓ whatNow() Determinism
```bash
python -m pib.cli what-now $PIB_DB_PATH --member m-james --json
# Run twice — should return identical task ID
```

### ✓ Custody Calculation
```bash
python -m pib.cli custody $PIB_DB_PATH --json
# Expected: {"with": "m-james", ...}
```

### ✓ Console Access
```bash
curl http://localhost:3333/api/health | jq .status
# Expected: "healthy"
```

### ✓ OpenClaw Agent
```bash
echo "what's next?" | openclaw chat --workspace ~/.openclaw/workspace-cos
# Expected: Response with task recommendation
```

### ✓ Privacy Filtering
```bash
# As James
python -m pib.cli calendar-query $PIB_DB_PATH --member m-james --date today --json | jq '.events[] | select(.privacy == "privileged")'
# Expected: Laura's work events show title_redacted only
```

---

## Phase 11: Cron Jobs (Scheduled Tasks)

### 11.1 Configure OpenClaw Cron
Edit `~/.openclaw/workspace-cos/crontab.yaml`:

```yaml
jobs:
  - name: calendar_sync
    schedule: "*/15 * * * *"
    command: "node scripts/core/calendar_sync.mjs --incremental"
  
  - name: daily_state
    schedule: "30 5 * * *"
    command: "python -m pib.cli compute-daily-states $PIB_DB_PATH"
  
  - name: recurring_spawn
    schedule: "0 6 * * *"
    command: "python -m pib.cli recurring-spawn $PIB_DB_PATH"
  
  - name: morning_digest
    schedule: "15 7 * * *"
    command: "python -m pib.cli morning-digest $PIB_DB_PATH --member m-james"
  
  - name: proactive_scan
    schedule: "*/30 7-22 * * *"
    command: "python -m pib.cli proactive-scan $PIB_DB_PATH"
  
  - name: backup
    schedule: "0 * * * *"
    command: "python -m pib.cli backup $PIB_DB_PATH"
```

### 11.2 Reload Cron
```bash
openclaw gateway restart
```

---

## Troubleshooting

### Database Locked
```bash
# Check for stale connections
lsof | grep pib.db
# Kill if needed, then:
sqlite3 $PIB_DB_PATH "PRAGMA wal_checkpoint(TRUNCATE)"
```

### Calendar Sync Fails
```bash
# Re-authenticate
gog auth login --force
# Check calendar IDs
python -m pib.cli sources $PIB_DB_PATH --json | jq '.sources[] | select(.source_type == "google_calendar")'
```

### Anthropic API Errors
```bash
# Test key
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'
```

### OpenClaw Gateway Won't Start
```bash
# Check logs
openclaw gateway logs
# Reset
openclaw gateway stop
rm ~/.openclaw/gateway.pid
openclaw gateway start
```

---

## Next Steps

1. **Onboard Family Members** — Add Laura, Charlie via console Settings → Household
2. **Import Calendars** — Run discovery: `python -m pib.cli discover calendars`
3. **Classify Sources** — Review proposals: `python -m pib.cli proposals --pending`
4. **Test Messaging** — Send "what's next?" via iMessage/Signal/webchat
5. **Morning Brief** — Wait for 7:15 AM or trigger manually
6. **Monitor** — Watch `/opt/pib/logs/pib.jsonl` for activity

---

## Rollback

If bootstrap fails or needs to be reset:

```bash
# Backup existing DB
cp $PIB_DB_PATH $PIB_DB_PATH.backup

# Drop and recreate
rm $PIB_DB_PATH
python -m pib.cli bootstrap $PIB_DB_PATH --seed

# Restore from backup if needed
cp $PIB_DB_PATH.backup $PIB_DB_PATH
```

---

## Support

- **Docs:** `/opt/pib/repo/docs/`
- **Logs:** `/opt/pib/logs/pib.jsonl`
- **Health:** `python -m pib.cli health $PIB_DB_PATH --verbose`
- **Issues:** https://github.com/junglecrunch1212/chief-40-vermont/issues
