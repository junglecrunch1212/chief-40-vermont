# Mac Mini Setup Walkthrough — PIB v5 Deployment

**For:** Physical Mac Mini M2+ out of the box → production PIB household system
**Audience:** James (Bossman) or technical admin with physical access
**Time:** 2-3 hours (first-time setup)

---

## Hardware You Need

| Item | Notes |
|------|-------|
| Mac Mini M2 (or later) | 16GB RAM minimum, 256GB+ storage |
| Ethernet cable | Wired connection for stability |
| HDMI monitor + keyboard | For initial setup only (can be headless after) |
| Power cable | Included with Mac Mini |
| Router with open port | For Cloudflare Tunnel (optional but recommended) |

---

## Part 1: Unboxing → First Boot (30 min)

### 1.1 Physical Setup
1. Unbox Mac Mini
2. Connect Ethernet cable from router to Mac Mini
3. Connect HDMI to monitor
4. Connect keyboard (USB or Bluetooth)
5. Plug in power → press power button (back left corner)

### 1.2 macOS Setup Assistant
Follow the on-screen prompts:
- **Country:** United States
- **Keyboard:** U.S. English
- **Wi-Fi:** Skip (using Ethernet)
- **Migration Assistant:** Don't transfer (new setup)
- **Sign in with Apple ID:** Use household Apple ID (jrstice@gmail.com) or skip
- **Create computer account:**
  - Name: `Bossman` or `PIB Admin`
  - Username: `admin`
  - Password: <secure, store in password manager>
- **Express Setup:** Customize settings
- **Analytics:** Decline (privacy)
- **Screen Time:** Skip
- **Siri:** Enable (optional — we'll use Shortcuts separately)
- **FileVault:** Enable (encrypt disk)
- **Touch ID:** Skip (no fingerprint sensor on Mini)

### 1.3 System Preferences → Settings
Open System Settings (click Apple logo → System Settings):

1. **General → Software Update:**
   - Enable "Keep my Mac up to date" → Manual install only
   - Check now → update to latest macOS Sequoia 15.x

2. **General → Sharing:**
   - Computer Name: `pib-mini` or `cos-1`
   - Enable Remote Login (SSH) — needed for headless management

3. **Network:**
   - Ethernet → Details → TCP/IP → Configure IPv4: DHCP with manual address
   - Reserve IP in router: `192.168.1.50` (example — adjust for your network)

4. **Energy Saver:**
   - Prevent automatic sleeping when display is off: ON
   - Start up automatically after a power failure: ON

5. **Users & Groups:**
   - Add user `pib` (Standard, not admin) — will run services as this user

---

## Part 2: Command Line Setup (15 min)

### 2.1 Open Terminal
Cmd+Space → type "Terminal" → Enter

### 2.2 Install Xcode Command Line Tools
```bash
xcode-select --install
# Click "Install" in the popup
# Wait 5-10 minutes
```

### 2.3 Install Homebrew
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Follow the "Next steps" instructions to add Homebrew to PATH
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Verify
brew --version
```

### 2.4 Install Core Dependencies
```bash
brew install python@3.12 node@22 sqlite git age
brew install --cask visual-studio-code  # Optional: for editing config files

# Verify installations
python3.12 --version  # Should be 3.12.x
node --version        # Should be 22.x
sqlite3 --version     # Should be 3.45+
git --version
age --version
```

---

## Part 3: PIB Installation (20 min)

### 3.1 Create Directory Structure
```bash
sudo mkdir -p /opt/pib/{data,logs,config,backups,repo}
sudo chown -R $(whoami):staff /opt/pib
```

### 3.2 Clone PIB Repository
```bash
cd /opt/pib
git clone https://github.com/junglecrunch1212/chief-40-vermont.git repo
cd repo
git checkout main  # Or specific tag/branch
```

### 3.3 Install Python Virtual Environment
```bash
python3.12 -m venv /opt/pib/venv
source /opt/pib/venv/bin/activate

# Install PIB package + dependencies
cd /opt/pib/repo
pip install --upgrade pip
pip install -e ".[dev]"

# Verify CLI works
python -m pib.cli --help
```

### 3.4 Install OpenClaw
```bash
npm install -g @openclaw/cli

# Verify
openclaw --version
openclaw help
```

---

## Part 4: Credentials Setup (30 min)

### 4.1 Create `.env` File
```bash
cd /opt/pib/repo
cp config/.env.example config/.env
chmod 600 config/.env
code config/.env  # Or use nano/vim
```

Fill in these values (see BOOTSTRAP_INSTRUCTIONS.md for where to get each):

#### Anthropic API Key
1. Go to https://console.anthropic.com/
2. Sign in
3. Settings → API Keys → Create Key
4. Copy key → paste into `ANTHROPIC_API_KEY=sk-ant-...`

#### Twilio (SMS)
1. Go to https://twilio.com/console
2. Copy Account SID → `TWILIO_ACCOUNT_SID=AC...`
3. Copy Auth Token → `TWILIO_AUTH_TOKEN=...`
4. Phone Numbers → Buy a number → copy → `TWILIO_PHONE_NUMBER=+1...`

#### Google Service Account
1. Go to https://console.cloud.google.com/
2. Create project: "PIB Household"
3. APIs & Services → Enable APIs: Calendar, Sheets, Gmail, Drive
4. Create Credentials → Service Account
5. Download JSON key → save as `/opt/pib/config/google-sa-key.json`
6. Copy path → `GOOGLE_SA_KEY_PATH=/opt/pib/config/google-sa-key.json`

#### BlueBubbles (iMessage Bridges)
For each Mac Mini running BlueBubbles:
1. Open BlueBubbles app → Settings → Server
2. Copy "Server Address" → `BLUEBUBBLES_JAMES_URL=http://james-mini.local:1234`
3. Settings → Security → API Key → Copy → `BLUEBUBBLES_JAMES_SECRET=...`
4. Repeat for Laura's bridge

#### Siri Bearer Token (generate random)
```bash
openssl rand -hex 32
# Copy output → SIRI_BEARER_TOKEN=...
```

#### Backup Key (generate with age)
```bash
age-keygen -o /opt/pib/config/age-key.txt
# Copy public key → BACKUP_PUBLIC_KEY=age1...
chmod 600 /opt/pib/config/age-key.txt
```

### 4.2 Google OAuth Setup
```bash
# Install gog CLI (bundled with OpenClaw)
gog auth login

# Browser will open → sign in with jrstice@gmail.com
# Grant access to:
#   - Google Calendar
#   - Google Sheets
#   - Gmail
#   - Google Drive

# Verify
gog calendar list
# Should show 12 calendars (James, Laura, Charlie, shared, etc.)
```

### 4.3 Share Calendars with Service Account
In Google Calendar web UI:
1. For each calendar (James, Laura, Charlie, Household, etc.):
   - Settings → Share with specific people
   - Add the service account email (from JSON key: `client_email`)
   - Permission: "Make changes to events"
2. Click "Send"

---

## Part 5: Database Initialization (10 min)

### 5.1 Bootstrap Database
```bash
cd /opt/pib/repo
source /opt/pib/venv/bin/activate
export PIB_DB_PATH=/opt/pib/data/pib.db

python -m pib.cli bootstrap $PIB_DB_PATH
```

Expected output:
```
PIB v5 Bootstrap
================

✓ Schema initialized (47 tables, 18 indexes)
✓ Migrations applied (version 4)
✓ Seed data loaded:
  - 2 members (m-james, m-laura)
  - 3 source classifications
  - 12 calendar source mappings
  - 5 budget categories
  - 3 life phases
✓ FTS5 indexes created (ops_tasks_fts, ops_items_fts)

Database ready: /opt/pib/data/pib.db (4.8 MB)
```

### 5.2 Verify Database
```bash
# Check integrity
sqlite3 $PIB_DB_PATH "PRAGMA integrity_check"
# Expected: ok

# Check schema version
sqlite3 $PIB_DB_PATH "SELECT version FROM meta_schema_version ORDER BY version DESC LIMIT 1"
# Expected: 4

# List tables
sqlite3 $PIB_DB_PATH ".tables"
# Should show 47+ tables (common_*, ops_*, cal_*, fin_*, mem_*, pib_*)
```

---

## Part 6: Console Server Setup (10 min)

### 6.1 Install Node Dependencies
```bash
cd /opt/pib/repo/console
npm install
```

### 6.2 Test Console Locally
```bash
export PIB_DB_PATH=/opt/pib/data/pib.db
export PIB_CONSOLE_PORT=3333
node server.mjs
```

Expected output:
```
PIB Console running on http://localhost:3333
Database: /opt/pib/data/pib.db
```

### 6.3 Test in Browser
Open http://localhost:3333

You should see:
- Dashboard with empty state
- Sidebar with Health, Tasks, Schedule, Lists tabs
- Member selector (James, Laura, Charlie)

Press Ctrl+C to stop server.

---

## Part 7: OpenClaw Workspace Setup (15 min)

### 7.1 Create Workspace for CoS Agent
```bash
openclaw init --workspace ~/.openclaw/workspace-cos

cd ~/.openclaw/workspace-cos

# Copy template files
cp /opt/pib/repo/workspace-template/cos/* .

# Verify files
ls -la
# Should see: SOUL.md, AGENTS.md, USER.md, MEMORY.md, HEARTBEAT.md, scripts/
```

### 7.2 Configure Agent
Edit `openclaw.json`:
```json
{
  "agent_id": "pib-cos",
  "display_name": "PIB — Chief of Staff",
  "model": "anthropic/claude-sonnet-4-5",
  "capabilities": "none",
  "channels": ["imessage", "signal", "webchat"],
  "env": {
    "PIB_CALLER_AGENT": "cos",
    "PIB_DB_PATH": "/opt/pib/data/pib.db"
  }
}
```

### 7.3 Repeat for Coach and Dev Agents
```bash
# Coach
openclaw init --workspace ~/.openclaw/workspace-coach
cd ~/.openclaw/workspace-coach
cp /opt/pib/repo/workspace-template/coach/* .
# Edit openclaw.json (set agent_id=pib-coach, model=sonnet, capabilities=none)

# Dev
openclaw init --workspace ~/.openclaw/workspace-dev
cd ~/.openclaw/workspace-dev
cp /opt/pib/repo/workspace-template/dev/* .
# Edit openclaw.json (set agent_id=pib-dev, model=opus, capabilities=full)
```

---

## Part 8: Start Services (10 min)

### 8.1 Start OpenClaw Gateway
```bash
openclaw gateway start

# Verify
openclaw gateway status
# Expected: Status: running
```

### 8.2 Start Console Server (background)
```bash
cd /opt/pib/repo/console
nohup node server.mjs > /opt/pib/logs/console.log 2>&1 &

# Verify
curl http://localhost:3333/api/health | jq .status
# Expected: "healthy"
```

### 8.3 Install Launchd Service (Auto-start on Boot)
```bash
cd /opt/pib/repo
sudo cp config/com.pib.runtime.plist /Library/LaunchDaemons/
sudo launchctl load /Library/LaunchDaemons/com.pib.runtime.plist

# Verify
sudo launchctl list | grep pib
# Expected: com.pib.runtime with PID
```

---

## Part 9: First Calendar Sync (15 min)

### 9.1 Run Full Calendar Sync
```bash
cd ~/.openclaw/workspace-cos
node scripts/core/calendar_sync.mjs --full
```

Expected output:
```
Calendar Sync — Full Mode
=========================

Fetching calendars from Google...
✓ 12 calendars found

Syncing events (last 30 days + next 90 days)...
✓ james-personal: 47 events
✓ laura-work: 89 events (privacy: privileged)
✓ charlie-school: 23 events
✓ household-shared: 12 events
...

Total: 312 events synced
Classified: 287 events
Pending human review: 25 events

Run `python -m pib.cli proposals --pending` to review.
```

### 9.2 Classify Pending Events
```bash
cd /opt/pib/repo
source /opt/pib/venv/bin/activate
python -m pib.cli proposals --pending
```

Follow prompts to classify ambiguous events:
- "Team standup" → work (Laura) → privileged
- "Doctor appt" → health (James) → normal
- etc.

### 9.3 Compute Daily State
```bash
python -m pib.cli compute-daily-states $PIB_DB_PATH
```

Expected:
```
Daily State Computation
=======================

Date: 2026-03-05
Custody: Charlie with James (overnight: James)
Laura availability: 4 blocks (2h, 1h, 3h, 1.5h)
James availability: All day (Charlie pickup 3:30pm)
Complexity score: 2.3 (low)

✓ State saved to cal_daily_states
```

---

## Part 10: Test whatNow() (5 min)

### 10.1 Add a Test Task
```bash
python -m pib.cli task-create $PIB_DB_PATH \
  --title "Call roofer about leak estimate" \
  --assignee m-james \
  --domain household \
  --effort small \
  --energy medium \
  --due 2026-03-06 \
  --micro "Pick up phone → call Dan at (404) 555-0142 → ask about Saturday availability" \
  --json
```

### 10.2 Run whatNow()
```bash
python -m pib.cli what-now $PIB_DB_PATH --member m-james --json
```

Expected JSON response:
```json
{
  "ok": true,
  "the_one_task": {
    "id": "t-0001",
    "title": "Call roofer about leak estimate",
    "micro_script": "Pick up phone → call Dan at (404) 555-0142 → ask about Saturday availability",
    "effort": "small",
    "energy": "medium",
    "points": 3,
    "score": 745,
    "reasoning": "High score: due soon + blocks_household + energy match"
  },
  "energy": {
    "level": "high",
    "meds": true,
    "sleep": "great"
  },
  "completions_today": 0,
  "cap": 15
}
```

### 10.3 Complete the Task
```bash
python -m pib.cli task-complete $PIB_DB_PATH --task t-0001 --member m-james --json
```

Expected response includes reward tier:
```json
{
  "ok": true,
  "reward_tier": "jackpot",
  "reward_message": "🎉 JACKPOT! That's the run. You're crushing it.",
  "streak": {
    "current": 1,
    "best": 1,
    "grace": 0
  },
  "next_active_idx": 1
}
```

---

## Part 11: Configure Cron Jobs (10 min)

### 11.1 Create Crontab Config
```bash
cd ~/.openclaw/workspace-cos
cat > crontab.yaml <<EOF
jobs:
  - name: calendar_sync_incremental
    schedule: "*/15 * * * *"
    command: "node scripts/core/calendar_sync.mjs --incremental"
  
  - name: daily_state_compute
    schedule: "30 5 * * *"
    command: "python -m pib.cli compute-daily-states \$PIB_DB_PATH"
  
  - name: recurring_spawn
    schedule: "0 6 * * *"
    command: "python -m pib.cli recurring-spawn \$PIB_DB_PATH"
  
  - name: morning_digest_james
    schedule: "15 7 * * *"
    command: "python -m pib.cli morning-digest \$PIB_DB_PATH --member m-james"
  
  - name: proactive_trigger_scan
    schedule: "*/30 7-22 * * *"
    command: "python -m pib.cli proactive-scan \$PIB_DB_PATH"
  
  - name: backup_hourly
    schedule: "0 * * * *"
    command: "python -m pib.cli backup \$PIB_DB_PATH"
  
  - name: cleanup_expired
    schedule: "0 3 * * *"
    command: "python -m pib.cli cleanup \$PIB_DB_PATH"
EOF
```

### 11.2 Reload Gateway
```bash
openclaw gateway restart
```

### 11.3 Verify Cron Jobs
```bash
openclaw cron list
```

Expected: List of 7 jobs with next run times

---

## Part 12: Test Messaging (10 min)

### 12.1 Test Webchat
1. Open browser: http://localhost:3333
2. Click "Chat" tab
3. Type: "what's next?"
4. Press Enter

Expected: Agent responds with whatNow() result + micro-script

### 12.2 Test iMessage (if BlueBubbles configured)
From your phone (James's number):
1. Send iMessage to household number
2. Message: "what's next?"

Expected: PIB responds within 5 seconds with task + micro-script

### 12.3 Test Siri Shortcut (optional)
Create Siri Shortcut:
1. Shortcuts app → New Shortcut
2. Add action: "Get Contents of URL"
   - URL: `http://pib-mini.local:3333/api/capture/task`
   - Method: POST
   - Headers: `Authorization: Bearer <SIRI_BEARER_TOKEN>`
   - Body: JSON
     ```json
     {
       "member_id": "m-james",
       "source": "siri",
       "text": "Task goes here",
       "timestamp": "<current time>"
     }
     ```
3. Add action: "Show Result"
4. Rename shortcut: "Tell PIB"
5. Test: "Hey Siri, Tell PIB buy milk"

Expected: Task captured to inbox

---

## Part 13: Going Headless (5 min)

Once everything works:

### 13.1 Enable Screen Sharing (optional — for remote GUI access)
System Settings → Sharing → Screen Sharing → ON

### 13.2 Test SSH Access
From your laptop:
```bash
ssh admin@pib-mini.local
# Or use the IP: ssh admin@192.168.1.50
```

### 13.3 Disconnect Monitor + Keyboard
Mac Mini will continue running headless.

### 13.4 Monitor Remotely
```bash
# SSH in
ssh admin@pib-mini.local

# Check logs
tail -f /opt/pib/logs/pib.jsonl

# Check gateway status
openclaw gateway status

# Check console
curl http://pib-mini.local:3333/api/health | jq

# Check database size
du -h /opt/pib/data/pib.db
```

---

## Verification Checklist

Run through this checklist to confirm everything works:

- [ ] Database exists: `/opt/pib/data/pib.db`
- [ ] Database integrity: `sqlite3 $PIB_DB_PATH "PRAGMA integrity_check"` → ok
- [ ] Calendar sync: `gog calendar list` → shows 12 calendars
- [ ] whatNow() works: `python -m pib.cli what-now $PIB_DB_PATH --member m-james --json`
- [ ] Console loads: http://localhost:3333 → dashboard renders
- [ ] OpenClaw gateway: `openclaw gateway status` → running
- [ ] Cron jobs: `openclaw cron list` → 7 jobs listed
- [ ] Health check: `python -m pib.cli health $PIB_DB_PATH --json` → status: healthy
- [ ] Messaging: Send "what's next?" via webchat → receives response
- [ ] Privacy: Laura's work calendar titles redacted for James
- [ ] Backup: `/opt/pib/backups/` contains `.db.age` files
- [ ] Launchd: `sudo launchctl list | grep pib` → service running
- [ ] SSH: `ssh admin@pib-mini.local` → connects
- [ ] Headless: Disconnect monitor → system continues working

---

## Maintenance Tasks

### Daily
- Check `/opt/pib/logs/pib.jsonl` for errors (or set up log monitoring)
- Verify morning digest sent at 7:15 AM

### Weekly
- Review backups: `/opt/pib/backups/` should have 168 hourly + 7 daily files
- Check disk space: `df -h /`
- Review pending approvals: console → Decisions tab

### Monthly
- Update macOS: System Settings → Software Update (on a Sunday with backup first)
- Rotate API keys: Anthropic, Twilio (track in `common_audit_log`)
- Review governance gates: Any actions that should be confirm → true or vice versa?

### Quarterly
- Review privacy classifications: Any sources need reclassification?
- Archive old data: `python -m pib.cli archive $PIB_DB_PATH --before 2025-01-01`
- Test disaster recovery: Restore from backup on test machine

---

## Troubleshooting

See BOOTSTRAP_INSTRUCTIONS.md § Troubleshooting for common issues.

Quick fixes:

| Problem | Fix |
|---------|-----|
| "Database is locked" | `sqlite3 $PIB_DB_PATH "PRAGMA wal_checkpoint(TRUNCATE)"` |
| Calendar sync fails | `gog auth login --force` |
| Gateway won't start | `openclaw gateway stop && rm ~/.openclaw/gateway.pid && openclaw gateway start` |
| Console 404 | Check `nohup.out`: `tail /opt/pib/logs/console.log` |
| Cron jobs not running | `openclaw gateway restart` |
| Anthropic API 401 | Verify `ANTHROPIC_API_KEY` in `.env` |

---

## Next Steps

Now that PIB is operational:

1. **Onboard Family**
   - Add Laura to console: Settings → Household → Add Member
   - Set up Laura's view mode: `compressed`
   - Configure Laura's work calendar privacy: `privileged`

2. **Import Historical Data**
   - Recurring tasks: `python -m pib.cli import-recurring $PIB_DB_PATH --csv tasks.csv`
   - Financial data: `python -m pib.cli import-transactions $PIB_DB_PATH --csv bank.csv`
   - CRM: `python -m pib.cli import-items $PIB_DB_PATH --csv contacts.csv`

3. **Configure Proactive Triggers**
   - Morning digest timing
   - Paralysis detection threshold (2 hours silence during peak)
   - One-more-nudge timing (after completions)

4. **Set Up Monitoring**
   - Health endpoint: `GET /api/health` every 5 minutes
   - Alert on: `status != "healthy"` or `checks.database.ok != true`

5. **Test Edge Cases**
   - Power outage recovery (launchd auto-starts)
   - Internet outage (Layer 1 fallback)
   - API key expiration (alert + graceful degradation)

---

## Support

- **Docs:** `/opt/pib/repo/docs/`
- **Logs:** `/opt/pib/logs/pib.jsonl`
- **CLI Help:** `python -m pib.cli --help`
- **Health Check:** `python -m pib.cli health $PIB_DB_PATH --verbose`
- **Issues:** https://github.com/junglecrunch1212/chief-40-vermont/issues

---

**You're done!** PIB is now operational. Send "what's next?" and watch the magic happen.
