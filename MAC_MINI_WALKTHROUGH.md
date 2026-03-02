# Mac Mini Setup Walkthrough — Complete Beginner Guide

**You:** Have never used a Mac before.
**Goal:** Mac Mini running OpenClaw + ready to deploy PIB v5.
**Time:** ~2-3 hours, mostly waiting for downloads.

---

## PART 1: Unboxing & First Boot (15 min)

### 1.1 Plug It In
- Connect power cable to Mac Mini
- Connect HDMI cable to a monitor/TV (you need a screen for initial setup only — later it runs headless)
- Connect a USB keyboard and mouse (or Bluetooth ones — it'll pair during setup)
- Connect Ethernet cable to router (faster and more reliable than WiFi for a server)
- Press the power button (it's on the bottom-back of the Mac Mini)

### 1.2 macOS Setup Wizard
A setup wizard appears on screen. Walk through it:

1. **Language:** English
2. **Country:** United States
3. **Accessibility:** Skip (click "Not Now")
4. **Wi-Fi:** Skip if you plugged in Ethernet. Otherwise pick your WiFi and enter password.
5. **Migration Assistant:** Click **"Not Now"** — you don't want to transfer from another Mac
6. **Apple ID:** Sign in with your Apple ID (the one you use for iMessage). If you don't have one, create one. **You need this for iMessage/BlueBubbles later.**
7. **Terms & Conditions:** Agree
8. **Computer Account:**
   - Full Name: `James`
   - Account Name: `james` (this becomes your username)
   - Password: Pick something strong. **Write it down.** You'll need it for SSH and sudo commands.
9. **Screen Time:** Skip
10. **Analytics:** Uncheck everything, click Continue
11. **Desktop appearance:** Pick whatever you like (Dark is nice for a server)

You're now at the macOS desktop. It looks like a big empty screen with a dock (row of icons) at the bottom.

### 1.3 Find Terminal
Everything from here happens in **Terminal** — the Mac equivalent of a command line.

1. Click the **magnifying glass icon** in the top-right corner of the screen (or press `Cmd + Space`)
2. Type: `Terminal`
3. Click **Terminal.app** when it appears
4. A white/black window opens with a blinking cursor. This is where you type commands.

**Pro tip:** Right-click Terminal in the dock → Options → Keep in Dock. You'll use it a lot.

---

## PART 2: Mac Settings for Server Use (15 min)

Copy-paste each command into Terminal and press Enter. When it asks for a password, type your account password (the one from step 1.2 #8). **You won't see the password as you type — that's normal on Mac.**

### 2.1 Never Sleep
```bash
sudo pmset -a sleep 0
sudo pmset -a disksleep 0
sudo pmset -a displaysleep 0
sudo pmset -a hibernatemode 0
sudo pmset -a autorestart 1
```
*What this does: Prevents the Mac from sleeping, and auto-restarts after power loss.*

### 2.2 Set Timezone
```bash
sudo systemsetup -settimezone America/New_York
```

### 2.3 Set Computer Name
```bash
sudo scutil --set HostName pib-mini
sudo scutil --set LocalHostName pib-mini
sudo scutil --set ComputerName pib-mini
```

### 2.4 Enable Remote Login (SSH)
This lets you control the Mac from your laptop later, without needing a monitor.

**Via GUI (easier):**
1. Click the **Apple menu** (top-left corner) → **System Settings**
2. Click **General** in the sidebar
3. Click **Sharing**
4. Toggle **Remote Login** to ON
5. It will show something like: `ssh james@192.168.1.XXX` — **write down this IP address**

**Or via Terminal:**
```bash
sudo systemsetup -setremotelogin on
```

### 2.5 Find Your IP Address
```bash
ipconfig getifaddr en0
```
This prints something like `192.168.1.105`. **Write this down** — it's how you'll access the console and SSH from other devices.

### 2.6 Disable Automatic macOS Updates
1. Apple menu → **System Settings**
2. Click **General** → **Software Update**
3. Click the **(i)** icon next to "Automatic Updates"
4. Turn OFF everything (Download, Install macOS, Install app updates, Install Security Responses)

*Why: You don't want a server randomly rebooting for updates at 3 AM.*

### 2.7 Enable Auto-Login
1. Apple menu → **System Settings**
2. Click **Users & Groups**
3. Click the **(i)** next to your account
4. Toggle **Automatic Login** to ON
5. It may ask: System Settings → General → Login Items → also check here

*Why: After a power outage and restart, the Mac needs to log in automatically so all services start.*

---

## PART 3: Install Software (20 min)

### 3.1 Install Xcode Command Line Tools
```bash
xcode-select --install
```
A popup appears: click **Install**. Wait 5-10 minutes for download.

### 3.2 Install Homebrew
Homebrew is the Mac package manager (like apt-get on Linux).
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
It will ask for your password. Then it prints instructions at the end — **read them carefully.** You need to run two commands it tells you, something like:
```bash
echo >> /Users/james/.zprofile
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> /Users/james/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```
**(Run whatever it actually prints — the paths may differ.)**

Verify it worked:
```bash
brew --version
```
Should print something like `Homebrew 4.x.x`.

### 3.3 Install Node.js
```bash
brew install node@22
```
Verify:
```bash
node --version
npm --version
```
Should show `v22.x.x` and `10.x.x`.

**If `node --version` says "command not found":**
```bash
brew link node@22
```

### 3.4 Install Python
```bash
brew install python@3.12
```
Verify:
```bash
python3 --version
pip3 --version
```
Should show `Python 3.12.x`.

### 3.5 Install Git
```bash
brew install git
git --version
```

Set your Git identity (used for commits):
```bash
git config --global user.name "PIB"
git config --global user.email "pib@stice-sclafani.local"
```

### 3.6 Verify SQLite FTS5
macOS comes with SQLite, but let's verify FTS5 works:
```bash
sqlite3 ':memory:' "CREATE VIRTUAL TABLE t USING fts5(x); SELECT 1;"
```
Should print `1`. If it errors, install a fresh SQLite:
```bash
brew install sqlite
```

### 3.7 Install Helpful Extras
```bash
brew install jq tmux
```
- `jq` = pretty-print JSON in terminal
- `tmux` = persistent terminal sessions (stays running when you disconnect SSH)

---

## PART 4: Set Up GitHub (10 min)

### 4.1 Create an SSH Key
```bash
ssh-keygen -t ed25519 -C "pib-mini"
```
It asks:
- **File:** Just press Enter (accept default)
- **Passphrase:** Just press Enter twice (no passphrase — this is a server)

### 4.2 Copy the Key
```bash
cat ~/.ssh/id_ed25519.pub
```
This prints a long line starting with `ssh-ed25519`. **Select and copy the ENTIRE line.**

### 4.3 Add to GitHub
1. Open Safari (click the compass icon in the dock)
2. Go to `github.com` and sign in as `junglecrunch1212`
3. Click your **profile icon** (top-right) → **Settings**
4. In the sidebar, click **SSH and GPG keys**
5. Click **New SSH key**
6. Title: `pib-mini`
7. Key: Paste the line you copied
8. Click **Add SSH key**

### 4.4 Test It
```bash
ssh -T git@github.com
```
Type `yes` when it asks about fingerprint. Should say:
```
Hi junglecrunch1212! You've successfully authenticated...
```

---

## PART 5: Install OpenClaw (5 min)

### 5.1 Install
```bash
npm install -g openclaw
```

### 5.2 Verify
```bash
openclaw --version
```

### 5.3 Initialize Workspace
```bash
openclaw init
```
This creates the workspace at `~/.openclaw/workspace/`. That `~` means `/Users/james` — your home folder.

### 5.4 Quick Test
```bash
openclaw gateway start
```
Wait 5 seconds, then:
```bash
openclaw gateway status
```
Should show it's running. Then stop it (we'll start it for real later):
```bash
openclaw gateway stop
```

---

## PART 6: Wire Google (10 min)

### 6.1 Authenticate with Google
```bash
gog auth login
```
This opens Safari with a Google sign-in page.
1. Sign in with `jrstice@gmail.com`
2. Click "Allow" on all permission prompts (Calendar, Sheets, Gmail, etc.)
3. It says "Authentication successful" — close the browser tab

### 6.2 Verify Calendar Works
```bash
gog calendar list --no-input
```
Should print a list of your Google calendars.

### 6.3 Verify Sheets Works
```bash
gog sheets list --no-input
```
Should print accessible spreadsheets.

### 6.4 (Optional) Add Laura's Google Account
If Laura's calendar needs its own auth:
```bash
gog auth login --account lcholland12@gmail.com
```
Same browser flow, but Laura signs in with her account.

---

## PART 7: Wire Anthropic (5 min)

### 7.1 Get API Key
1. In Safari, go to `console.anthropic.com`
2. Sign in (or create account)
3. Go to **Plans & Billing** → make sure credits are loaded
4. Go to **API Keys** → **Create Key**
5. Name it `pib-mini`
6. **Copy the key** (starts with `sk-ant-`)

### 7.2 Store It
```bash
openclaw config set ANTHROPIC_API_KEY sk-ant-PASTE-YOUR-KEY-HERE
```

---

## PART 8: Wire iMessage via BlueBubbles (20 min)

This is what lets PIB send and receive iMessages.

### 8.1 Make Sure iMessage Works
1. Open **Messages** app (green speech bubble icon in the dock, or Cmd+Space → Messages)
2. If not signed in: Messages menu → Settings → iMessage → Sign in with your Apple ID
3. Send yourself a test message to verify it works

### 8.2 Download BlueBubbles
1. In Safari, go to `https://bluebubbles.app/downloads/`
2. Download the **macOS** version
3. Open the downloaded `.dmg` file
4. Drag BlueBubbles to the Applications folder
5. Open BlueBubbles from Applications (if it says "unverified developer": System Settings → Privacy & Security → click "Open Anyway")

### 8.3 Configure BlueBubbles
1. BlueBubbles opens a setup wizard
2. **Server Configuration:**
   - Set a **server password** — write it down, you'll need it later
   - Choose **Local** for now (you can add Cloudflare tunnel later for remote access)
3. **Private API:** Enable it (this gives read receipts, typing indicators, reactions)
   - It may ask you to install a helper — follow its instructions
4. Note the **server URL** it shows (something like `http://localhost:1234`)

### 8.4 Set BlueBubbles to Auto-Start
1. In BlueBubbles: Settings → **Start on Login** → ON
2. Also: Apple menu → System Settings → General → Login Items → add BlueBubbles if not already there

### 8.5 Store Credentials
```bash
openclaw config set BLUEBUBBLES_URL http://localhost:1234
openclaw config set BLUEBUBBLES_PASSWORD your-server-password-here
```

---

## PART 9: Wire Signal (5 min, optional)

```bash
openclaw channel add signal
```
Follow the on-screen instructions. It'll show a QR code — scan it with Signal on your phone (Signal → Settings → Linked Devices → Link New Device).

---

## PART 10: Wire WhatsApp (5 min, optional)

```bash
openclaw channel add whatsapp
```
Follow the QR code flow — scan with WhatsApp on your phone (WhatsApp → Settings → Linked Devices → Link a Device).

---

## PART 11: Wire Twilio for SMS (15 min, optional)

### 11.1 Get Twilio Credentials
1. Go to `console.twilio.com` in Safari
2. Sign up or sign in
3. From the dashboard, copy:
   - **Account SID** (starts with `AC`)
   - **Auth Token** (click "Show" to reveal)
4. Buy a phone number if you don't have one ($1/month): Phone Numbers → Buy a Number

### 11.2 Store Credentials
```bash
openclaw config set TWILIO_ACCOUNT_SID ACxxxxxxxxxxxxxxxxxxxx
openclaw config set TWILIO_AUTH_TOKEN xxxxxxxxxxxxxxxxxxxxxxxx
openclaw config set TWILIO_PHONE_NUMBER +1xxxxxxxxxx
```

### 11.3 Set Up Webhook URL
Twilio needs to reach your Mac Mini from the internet. Easiest way:

```bash
brew install cloudflared
cloudflared tunnel login
```
This opens Safari — sign in to Cloudflare (free account). Then:
```bash
cloudflared tunnel create pib
cloudflared tunnel route dns pib pib.yourdomain.com
```
*(You need a domain on Cloudflare for this. If you don't have one, use ngrok as a temporary alternative: `brew install ngrok && ngrok http 18789`)*

Then in Twilio console: Phone Number → your number → Messaging → Webhook URL → `https://pib.yourdomain.com/webhooks/twilio`

---

## PART 12: Create Agent Files (10 min)

These are the files that tell OpenClaw who it is and what to do. Copy-paste each block into Terminal.

### 12.1 SOUL.md
```bash
cat > ~/.openclaw/workspace/SOUL.md << 'AGENTFILE'
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
After deployment, expand this SOUL.md with full personality and coaching protocols
from the build spec (pib-v5-build-spec.md §2).
AGENTFILE
```

### 12.2 AGENTS.md
```bash
cat > ~/.openclaw/workspace/AGENTS.md << 'AGENTFILE'
# AGENTS.md — PIB Deployment Agent

## Mission
Deploy chief-40-vermont on this OpenClaw instance per docs/openclaw-integration.md.

## Phase 1: Deploy
1. Clone chief-40-vermont repo into this workspace
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
AGENTFILE
```

### 12.3 USER.md
```bash
cat > ~/.openclaw/workspace/USER.md << 'AGENTFILE'
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
AGENTFILE
```

### 12.4 HEARTBEAT.md
```bash
cat > ~/.openclaw/workspace/HEARTBEAT.md << 'AGENTFILE'
# HEARTBEAT.md

Run: python3 -m pib.cli health --json

Report any items with status "error" or "warn". If all "ok", reply HEARTBEAT_OK.

Also check:
- gog calendar list --no-input (Google auth still valid?)
- Console server responding on port 3333?
AGENTFILE
```

### 12.5 MEMORY.md
```bash
cat > ~/.openclaw/workspace/MEMORY.md << 'AGENTFILE'
# MEMORY.md

(Fresh instance. Memories will accumulate from operation.)
AGENTFILE
```

### 12.6 TOOLS.md
```bash
cat > ~/.openclaw/workspace/TOOLS.md << 'AGENTFILE'
# TOOLS.md

## Python CLI (PIB engine)
All PIB domain logic is accessed via: python3 -m pib.cli <command> --json
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
AGENTFILE
```

---

## PART 13: Set Up Auto-Start (10 min)

These make OpenClaw and the console restart automatically if the Mac reboots.

### 13.1 Create the OpenClaw auto-start file
```bash
mkdir -p ~/Library/LaunchAgents

cat > ~/Library/LaunchAgents/com.openclaw.gateway.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openclaw.gateway</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/openclaw</string>
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
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>/Users/james</string>
    </dict>
</dict>
</plist>
PLIST
```

**Note:** If `which openclaw` shows a different path than `/opt/homebrew/bin/openclaw`, edit the plist to match.

### 13.2 Activate It
```bash
launchctl load ~/Library/LaunchAgents/com.openclaw.gateway.plist
```

### 13.3 Verify It's Running
```bash
launchctl list | grep openclaw
openclaw gateway status
```

---

## PART 14: Pre-Flight Checklist

Run each command. Every one should succeed.

```bash
echo "=== HARDWARE ==="
pmset -g | grep sleep              # Should show sleep 0
hostname                            # Should show pib-mini

echo "=== SOFTWARE ==="
node --version                      # v22.x.x
python3 --version                   # 3.12.x
git --version                       # git version 2.x.x
sqlite3 --version                   # 3.x.x

echo "=== OPENCLAW ==="
openclaw --version                  # Should print version
openclaw gateway status             # Should show running or stopped

echo "=== CREDENTIALS ==="
ssh -T git@github.com 2>&1         # "Hi junglecrunch1212!"
gog calendar list --no-input 2>&1 | head -3   # Calendar names
gog sheets list --no-input 2>&1 | head -3     # Spreadsheet names

echo "=== AGENT FILES ==="
ls ~/.openclaw/workspace/SOUL.md    # Should exist
ls ~/.openclaw/workspace/AGENTS.md  # Should exist
ls ~/.openclaw/workspace/USER.md    # Should exist
ls ~/.openclaw/workspace/HEARTBEAT.md  # Should exist
ls ~/.openclaw/workspace/MEMORY.md  # Should exist
ls ~/.openclaw/workspace/TOOLS.md   # Should exist

echo "=== NETWORK ==="
ipconfig getifaddr en0              # Your local IP

echo "=== ALL GOOD ==="
echo "Ready to deploy c40v!"
```

Save this as a script if you want:
```bash
cat > ~/preflight.sh << 'SCRIPT'
#!/bin/bash
echo "=== Pre-Flight Check ==="
echo -n "Node: " && node --version
echo -n "Python: " && python3 --version
echo -n "Git: " && git --version
echo -n "OpenClaw: " && openclaw --version 2>/dev/null || echo "NOT INSTALLED"
echo -n "GitHub: " && ssh -T git@github.com 2>&1 | head -1
echo -n "Google: " && gog calendar list --no-input 2>&1 | head -1
echo -n "Agent files: "
for f in SOUL.md AGENTS.md USER.md HEARTBEAT.md MEMORY.md TOOLS.md; do
  [ -f ~/.openclaw/workspace/$f ] && echo -n "✓$f " || echo -n "✗$f "
done
echo ""
echo -n "IP: " && ipconfig getifaddr en0
echo ""
echo "=== Done ==="
SCRIPT
chmod +x ~/preflight.sh
~/preflight.sh
```

---

## PART 15: Deploy PIB

Everything is ready. Start OpenClaw gateway if it isn't running:

```bash
openclaw gateway start
```

Open the OpenClaw webchat in Safari:
```bash
# Find the dashboard URL:
openclaw gateway status
# Look for "Dashboard: http://..."
# Open that URL in Safari
```

In the webchat, type:

```
Read docs/openclaw-integration.md in the chief-40-vermont repo at 
https://github.com/junglecrunch1212/chief-40-vermont.

Clone the repo into this workspace. Follow the integration spec to deploy 
PIB v5 on this OpenClaw instance. The spec has everything: what to keep, 
what to replace, file structure, the CLI to write, cron jobs, and success probes.

Start with Phase 1 from AGENTS.md. Run all probes from integration spec §9 
when done.
```

Then wait. The agent will work autonomously. It'll take 2-4 hours. Check back periodically — it may ask you to approve something.

---

## PART 16: After Deployment — Verify

Once the agent says it's done:

### From Terminal:
```bash
# Engine works?
cd ~/.openclaw/workspace/pib
python3 -m pib.cli what-now --member m-james --json

# Tests pass?
pytest tests/ -v

# Console works?
curl http://localhost:3333/api/household-status
```

### From Safari:
- Console: `http://localhost:3333/`
- Scoreboard: `http://localhost:3333/scoreboard`

### From your phone:
- Send "what's next?" via Signal/WhatsApp/iMessage
- Should get a response with your next task

### From the kitchen TV:
- Open browser, go to `http://YOUR-IP:3333/scoreboard`
- (Use the IP from `ipconfig getifaddr en0`)

---

## PART 17: SSH Access (Control Mac Mini from Your Laptop)

Once the Mac Mini is set up, you don't need the monitor anymore. Control it from your laptop:

### From a Mac/Linux laptop:
```bash
ssh james@192.168.1.XXX
# Use the IP you wrote down earlier
# Enter the password from initial setup
```

### From a Windows laptop:
1. Open PowerShell or Command Prompt
2. `ssh james@192.168.1.XXX`

### Using tmux (keeps commands running after you disconnect):
```bash
ssh james@192.168.1.XXX
tmux new -s pib
# Do your work...
# Press Ctrl+B then D to detach (it keeps running)
# Reconnect later:
ssh james@192.168.1.XXX
tmux attach -t pib
```

---

## Troubleshooting

**"command not found" after installing something:**
Close Terminal and reopen it (new terminals load the updated PATH).

**"Permission denied" on a command:**
Add `sudo` before it: `sudo the-command-here` (then enter your password).

**Can't SSH from laptop:**
Make sure Remote Login is on (System Settings → Sharing → Remote Login).

**BlueBubbles won't start:**
System Settings → Privacy & Security → scroll down → click "Open Anyway" next to BlueBubbles.

**"gog auth" browser doesn't open:**
Copy the URL it prints in Terminal, paste it into Safari manually.

**Mac fell asleep despite settings:**
```bash
sudo pmset -a sleep 0
caffeinate -d &
```
`caffeinate` forces the Mac to stay awake. The `&` makes it run in the background.

**Forgot your password:**
Restart Mac → hold `Cmd+R` during boot → Terminal → `resetpassword`

**How to copy-paste in Mac Terminal:**
- Copy: `Cmd+C`
- Paste: `Cmd+V`
- (It's Cmd, not Ctrl — the key with ⌘ on it, next to the spacebar)
