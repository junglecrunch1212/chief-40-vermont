# Personal Mac Mini Setup Guide — PIB v5 (chief-40-vermont)

> **Version:** 1.0 · **Date:** 2026-03-04 · **Status:** 📋 PROPOSED
>
> This guide configures James's and Laura's personal Mac Minis as Apple bridge nodes that push sensor data to the central CoS Mac Mini running OpenClaw/PIB.

---

## 1. Architecture Overview

### Hub + Spoke Diagram

```
                        ┌─────────────────────────┐
                        │    CoS Mac Mini (Hub)    │
                        │   $COS_HOST :3141        │
                        │                         │
                        │  ┌───────────────────┐  │
                        │  │ OpenClaw / PIB v5  │  │
                        │  │ Sensor Bus         │  │
                        │  │ Task Capture       │  │
                        │  │ Privacy Fence      │  │
                        │  └───────────────────┘  │
                        └────────┬───────┬────────┘
                                 │       │
                    LAN :3141    │       │   LAN :3141
                   ┌─────────────┘       └─────────────┐
                   ▼                                     ▼
        ┌─────────────────────┐             ┌─────────────────────┐
        │  James's Mac Mini   │             │  Laura's Mac Mini   │
        │  james-mini.local   │             │  laura-mini.local   │
        │                     │             │                     │
        │  • BlueBubbles      │             │  • BlueBubbles      │
        │  • Apple Shortcuts  │             │  • Apple Shortcuts  │
        │  • HomeKit Bridge   │             │  • (NO HomeKit)     │
        │  • Homebridge       │             │                     │
        └─────────────────────┘             └─────────────────────┘
```

### What Runs Where

| Component | CoS Mac Mini | James's Mini | Laura's Mini |
|-----------|:---:|:---:|:---:|
| OpenClaw / PIB brain | ✅ | ❌ | ❌ |
| Sensor Bus (ingest) | ✅ | ❌ | ❌ |
| Task Capture API | ✅ | ❌ | ❌ |
| Privacy Fence | ✅ | ❌ | ❌ |
| BlueBubbles (iMessage) | ❌ | ✅ (James's Apple ID) | ✅ (Laura's Apple ID) |
| Apple Shortcuts sensors | ❌ | ✅ | ✅ |
| HomeKit bridge | ❌ | ✅ (Home owner) | ❌ |
| Homebridge | ❌ | ✅ | ❌ |

### Network Requirements

- **All three Minis on the same LAN.** No internet exposure required.
- **Ports:**
  | Port | Host | Purpose |
  |------|------|---------|
  | 3141 | CoS Mini | Sensor ingest + task capture API |
  | 1234 | James/Laura | BlueBubbles server (default) |
  | 8581 | James | Homebridge UI |
  | 51826 | James | Homebridge HAP (HomeKit) |
- **DNS:** Use `.local` mDNS names or static IPs. mDNS is enabled by default on macOS.

### Key Endpoints

| Endpoint | URL |
|----------|-----|
| Sensor ingest | `http://$COS_HOST:3141/api/sensors/ingest` |
| Task capture | `http://$COS_HOST:3141/api/capture/task` |

> **`$COS_HOST`** = the CoS Mac Mini's address, e.g. `pib-mini.local` or `192.168.1.100`. Set this once in each Mini's environment.

---

## 2. James's Mac Mini Setup

### 2.1 macOS System Settings

#### Prevent Sleep
1. **System Settings → Energy Saver** (or **Battery → Power Adapter** on laptops)
2. Set "Turn display off after" → **Never** (or 15 min if you want display off — doesn't affect background tasks)
3. Enable **"Prevent your Mac from automatically sleeping when the display is off"**
4. Enable **"Start up automatically after a power failure"**

#### Enable Remote Login (SSH)
1. **System Settings → General → Sharing**
2. Enable **Remote Login**
3. Click (i) and add your user to "Allow access for"

#### Set Hostname

```bash
sudo scutil --set HostName james-mini
sudo scutil --set LocalHostName james-mini
sudo scutil --set ComputerName "James Mini"
dscacheutil -flushcache
```

Verify:

```bash
hostname
# → james-mini
scutil --get LocalHostName
# → james-mini
```

#### Disable Automatic macOS Updates
1. **System Settings → General → Software Update → Automatic Updates**
2. Turn OFF:
   - "Download new updates when available"
   - "Install macOS updates"
   - "Install application updates from the App Store"
3. Updates will be done manually during maintenance windows.

#### Set Environment Variable for CoS Host

Add to `~/.zshrc`:

```bash
echo 'export COS_HOST="pib-mini.local"' >> ~/.zshrc
source ~/.zshrc
```

### 2.2 Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the post-install instructions to add Homebrew to PATH:

```bash
echo >> ~/.zprofile
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### 2.3 Install & Configure BlueBubbles

BlueBubbles bridges iMessage to webhooks. James's instance uses **James's Apple ID**.

#### Install

1. Download BlueBubbles Server from [bluebubbles.app](https://bluebubbles.app)
2. Open the `.dmg` and drag to Applications
3. Grant Full Disk Access: **System Settings → Privacy & Security → Full Disk Access** → add BlueBubbles
4. Grant Accessibility access when prompted

#### Configure

1. Launch BlueBubbles Server
2. In **Settings → Connection**:
   - Server URL: use the local address (e.g., `http://james-mini.local:1234`)
3. In **Settings → Webhooks**, add a new webhook:
   - **URL:** `http://$COS_HOST:3141/api/webhooks/bluebubbles/james`
   - **Events:** Select all message events (new message, updated message, typing indicator)
4. In **Settings → General**:
   - Enable "Start on Login"
   - Enable "Keep macOS Awake"

#### Verify

```bash
curl http://localhost:1234/api/v1/server/info
```

Should return server info JSON.

> **Note:** James's Apple ID must be signed into iMessage on this Mac. Go to **Messages → Settings → iMessage** and confirm the account is active.

### 2.4 Apple Shortcuts Automations

Each shortcut POSTs sensor data to the CoS. See [Section 6](#6-apple-shortcuts--detailed-build-instructions) for step-by-step build instructions.

| Shortcut | Trigger | Endpoint |
|----------|---------|----------|
| PIB Health Export | Daily 6:00 AM | `/api/sensors/ingest` |
| PIB FindMy Location | Every 30 min, 7 AM–11 PM | `/api/sensors/ingest` |
| PIB Focus Mode | On focus change | `/api/sensors/ingest` |
| PIB Siri Capture | Manual ("Hey Siri, tell Poopsy…") | `/api/capture/task` |
| PIB Battery Status | Hourly | `/api/sensors/ingest` |

### 2.5 HomeKit Bridge Setup

James is the HomeKit Home owner, so the HomeKit bridge runs on his Mini. See [Section 7](#7-homekit-bridge-options) for detailed options. **Recommended: Option B (Homebridge + webhook plugin).**

#### Quick Install

```bash
# Install Node.js (if not already present)
brew install node

# Install Homebridge
sudo npm install -g homebridge homebridge-config-ui-x

# Install webhook plugin
sudo npm install -g homebridge-webhook

# Create config directory
mkdir -p ~/.homebridge
```

#### Configure Homebridge

Write `~/.homebridge/config.json`:

```json
{
  "bridge": {
    "name": "PIB HomeKit Bridge",
    "username": "CC:22:3D:E3:CE:30",
    "pin": "031-45-154",
    "port": 51826
  },
  "platforms": [
    {
      "platform": "config",
      "name": "Config",
      "port": 8581
    },
    {
      "platform": "HttpWebHookPlatform",
      "webhook_port": 51828,
      "sensors": [
        {
          "id": "front_door_lock",
          "name": "Front Door Lock",
          "type": "lock"
        },
        {
          "id": "thermostat_main",
          "name": "Main Thermostat",
          "type": "thermostat"
        },
        {
          "id": "living_room_lights",
          "name": "Living Room Lights",
          "type": "light"
        },
        {
          "id": "hallway_motion",
          "name": "Hallway Motion",
          "type": "motion"
        }
      ]
    }
  ]
}
```

#### Start Homebridge as a Service

```bash
# Install as a launchd service
sudo homebridge-config-ui-x service install

# Start it
sudo homebridge-config-ui-x service start
```

Access the UI at `http://james-mini.local:8581` (default login: `admin` / `admin` — change immediately).

#### Pair with HomeKit
1. Open **Home** app on James's iPhone/Mac
2. Tap **+** → **Add Accessory**
3. Enter the PIN from config: `031-45-154`
4. Assign devices to rooms

#### HomeKit → CoS Webhook Forwarding

Create a Shortcut automation for each HomeKit device state change. Example for front door lock:

1. **Shortcuts → Automation → +**
2. **"When Front Door Lock locks/unlocks"**
3. Add action: **Get Contents of URL**
   - URL: `http://$COS_HOST:3141/api/sensors/ingest`
   - Method: POST
   - Headers: `Content-Type: application/json`
   - Body (JSON):

```json
{
  "source": "homekit",
  "member_id": "james",
  "timestamp": "[[Current Date formatted as ISO 8601]]",
  "data": {
    "device_id": "front_door_lock",
    "device_name": "Front Door Lock",
    "device_type": "lock",
    "state": "locked",
    "changed_at": "[[Current Date formatted as ISO 8601]]"
  }
}
```

> Repeat for each device × each state change. Yes, it's tedious. That's why Option B (Homebridge webhook plugin) is recommended — it can auto-forward all changes.

---

## 3. Laura's Mac Mini Setup

### 3.1 macOS System Settings

Identical to James's setup (Section 2.1), except:

#### Set Hostname

```bash
sudo scutil --set HostName laura-mini
sudo scutil --set LocalHostName laura-mini
sudo scutil --set ComputerName "Laura Mini"
dscacheutil -flushcache
```

#### Environment

```bash
echo 'export COS_HOST="pib-mini.local"' >> ~/.zshrc
source ~/.zshrc
```

All other system settings (prevent sleep, auto-restart, remote login, disable auto-updates) are the same as Section 2.1.

### 3.2 Install Homebrew

Same as Section 2.2.

### 3.3 Install & Configure BlueBubbles

Same as Section 2.3, but:

- Sign in with **Laura's Apple ID** in Messages
- Webhook URL: `http://$COS_HOST:3141/api/webhooks/bluebubbles/laura`

### 3.4 Apple Shortcuts Automations

Same shortcuts as James (Section 2.4), but every payload uses `"member_id": "laura"`.

| Shortcut | Trigger | Endpoint |
|----------|---------|----------|
| PIB Health Export | Daily 6:00 AM | `/api/sensors/ingest` |
| PIB FindMy Location | Every 30 min, 7 AM–11 PM | `/api/sensors/ingest` |
| PIB Focus Mode | On focus change | `/api/sensors/ingest` |
| PIB Siri Capture | Manual ("Hey Siri, tell Poopsy…") | `/api/capture/task` |
| PIB Battery Status | Hourly | `/api/sensors/ingest` |

### 3.5 NO HomeKit

Laura's Mini does **not** run HomeKit or Homebridge. James's Mini is the sole HomeKit bridge.

### 3.6 Privacy Classification

> ⚠️ **IMPORTANT:** All sensor data from Laura's Mini is classified as **`privileged`** at the CoS privacy fence.

This means:
- Laura's health data (sleep, activity, heart rate, meds) → `privileged`
- Laura's location → `privileged`
- Laura's focus mode → `privileged`
- Laura's battery → `privileged`

The CoS Privacy Fence applies this classification automatically based on `member_id: "laura"`. James cannot see Laura's raw sensor data through the console unless the privacy fence explicitly allows it. The PIB brain uses it for coaching (e.g., "Laura seems stressed") without exposing raw values.

Each payload from Laura's shortcuts includes:

```json
{
  "source": "...",
  "member_id": "laura",
  "classification": "privileged",
  ...
}
```

The CoS will also enforce this server-side regardless of what the client sends, but including it client-side is defense-in-depth.

---

## 4. Sensor Webhook Contract

All sensor data is POSTed to:

```
POST http://$COS_HOST:3141/api/sensors/ingest
Content-Type: application/json
```

### Common Envelope

Every payload follows this structure:

```json
{
  "source": "<sensor_type>",
  "member_id": "james" | "laura",
  "timestamp": "2026-03-04T06:00:00-05:00",
  "classification": "normal" | "privileged",
  "data": { }
}
```

| Field | Type | Required | Notes |
|-------|------|:---:|-------|
| `source` | string | ✅ | One of the defined sensor types below |
| `member_id` | string | ✅ | `"james"` or `"laura"` |
| `timestamp` | ISO 8601 | ✅ | When the data was captured |
| `classification` | string | ❌ | Defaults to `"normal"`. Laura's data auto-promoted to `"privileged"` server-side |
| `data` | object | ✅ | Sensor-specific payload |

### Sensor Payloads

#### `apple_health_sleep`

```json
{
  "source": "apple_health_sleep",
  "member_id": "james",
  "timestamp": "2026-03-04T06:00:00-05:00",
  "data": {
    "bed_time": "2026-03-03T23:15:00-05:00",
    "wake_time": "2026-03-04T05:45:00-05:00",
    "total_minutes": 390,
    "deep_minutes": 85,
    "rem_minutes": 110,
    "core_minutes": 155,
    "awake_minutes": 40,
    "sleep_quality_score": null
  }
}
```

#### `apple_health_activity`

```json
{
  "source": "apple_health_activity",
  "member_id": "james",
  "timestamp": "2026-03-04T06:00:00-05:00",
  "data": {
    "date": "2026-03-03",
    "steps": 8432,
    "active_calories": 485,
    "total_calories": 2210,
    "exercise_minutes": 32,
    "stand_hours": 10,
    "distance_km": 6.2,
    "flights_climbed": 5
  }
}
```

#### `apple_health_heart`

```json
{
  "source": "apple_health_heart",
  "member_id": "james",
  "timestamp": "2026-03-04T06:00:00-05:00",
  "data": {
    "date": "2026-03-03",
    "resting_hr": 62,
    "avg_hr": 74,
    "max_hr": 142,
    "min_hr": 55,
    "hrv_avg_ms": 45,
    "has_irregular_rhythm_notification": false
  }
}
```

#### `apple_health_meds`

```json
{
  "source": "apple_health_meds",
  "member_id": "james",
  "timestamp": "2026-03-04T06:00:00-05:00",
  "data": {
    "date": "2026-03-03",
    "medications": [
      {
        "name": "Medication A",
        "scheduled_time": "08:00",
        "taken": true,
        "taken_at": "2026-03-03T08:12:00-05:00"
      },
      {
        "name": "Medication B",
        "scheduled_time": "20:00",
        "taken": true,
        "taken_at": "2026-03-03T20:05:00-05:00"
      }
    ],
    "adherence_pct": 100
  }
}
```

#### `location`

```json
{
  "source": "location",
  "member_id": "james",
  "timestamp": "2026-03-04T10:30:00-05:00",
  "data": {
    "latitude": 44.4759,
    "longitude": -73.2121,
    "accuracy_m": 10,
    "altitude_m": 45,
    "speed_mps": 0,
    "label": null
  }
}
```

> The CoS can enrich with geofence labels (home, office, gym, etc.) server-side.

#### `focus`

```json
{
  "source": "focus",
  "member_id": "james",
  "timestamp": "2026-03-04T09:00:00-05:00",
  "data": {
    "focus_mode": "Work",
    "previous_mode": "Personal",
    "is_active": true
  }
}
```

Valid `focus_mode` values: `"Do Not Disturb"`, `"Personal"`, `"Work"`, `"Sleep"`, `"Driving"`, `"Fitness"`, `"none"` (no focus active).

#### `battery`

```json
{
  "source": "battery",
  "member_id": "james",
  "timestamp": "2026-03-04T14:00:00-05:00",
  "data": {
    "device": "iphone",
    "level_pct": 72,
    "is_charging": false,
    "battery_state": "unplugged",
    "low_power_mode": false
  }
}
```

`battery_state`: `"unplugged"`, `"charging"`, `"full"`.

#### `homekit`

```json
{
  "source": "homekit",
  "member_id": "james",
  "timestamp": "2026-03-04T18:30:00-05:00",
  "data": {
    "device_id": "front_door_lock",
    "device_name": "Front Door Lock",
    "device_type": "lock",
    "state": "locked",
    "previous_state": "unlocked",
    "changed_at": "2026-03-04T18:30:00-05:00",
    "room": "Entryway"
  }
}
```

`device_type`: `"lock"`, `"thermostat"`, `"light"`, `"motion"`, `"contact"`, `"switch"`.

State values vary by type:
- **lock:** `"locked"` / `"unlocked"` / `"jammed"`
- **thermostat:** `{ "current_temp_f": 68, "target_temp_f": 70, "mode": "heat" }`
- **light:** `{ "on": true, "brightness_pct": 80 }`
- **motion:** `"detected"` / `"clear"`
- **contact:** `"open"` / `"closed"`

#### `siri_capture`

> Note: Siri captures go to the **sensor** endpoint (not task capture) when they're observational rather than actionable. If the user says "tell Poopsy," it goes to **task capture** (Section 5).

```json
{
  "source": "siri_capture",
  "member_id": "james",
  "timestamp": "2026-03-04T11:15:00-05:00",
  "data": {
    "raw_text": "I'm feeling really good today, slept great",
    "intent": "observation",
    "context": "siri_dictation"
  }
}
```

---

## 5. Task Capture Webhook Contract

Actionable captures (e.g., "Hey Siri, tell Poopsy buy milk") go to:

```
POST http://$COS_HOST:3141/api/capture/task
Content-Type: application/json
```

### Payload

```json
{
  "member_id": "james",
  "source": "siri",
  "text": "buy milk",
  "timestamp": "2026-03-04T11:20:00-05:00"
}
```

| Field | Type | Required | Notes |
|-------|------|:---:|-------|
| `member_id` | string | ✅ | `"james"` or `"laura"` |
| `source` | string | ✅ | `"siri"`, `"shortcut"`, or `"manual"` |
| `text` | string | ✅ | The raw captured text |
| `timestamp` | ISO 8601 | ✅ | When captured |

### Response

```json
{
  "status": "ok",
  "task_id": "cap_20260304_112000_james_a1b2",
  "message": "Captured: buy milk"
}
```

The CoS will:
1. Parse the text for intent
2. Create a task in the TASKS SSOT
3. Optionally respond via BlueBubbles/WhatsApp with confirmation

---

## 6. Apple Shortcuts — Detailed Build Instructions

> **Prerequisites:** On each Mac Mini, open **Shortcuts** app. These shortcuts also work on iPhone/Apple Watch for mobile sensor data.

### 6.1 PIB Health Export

| Property | Value |
|----------|-------|
| **Name** | `PIB Health Export` |
| **Trigger** | Automation → Time of Day → 6:00 AM → Daily → Run Immediately |
| **Member ID** | `james` (or `laura` on Laura's Mini) |

#### Shortcut Steps

1. **Find Health Samples**
   - Type: Sleep Analysis
   - Start Date: yesterday at 12:00 AM
   - End Date: today at 12:00 AM
   - Group By: None
   - → Save to variable `sleepData`

2. **Find Health Samples**
   - Type: Steps
   - Start Date: yesterday at 12:00 AM
   - End Date: today at 12:00 AM
   - → Save to variable `stepsData`

3. **Find Health Samples**
   - Type: Active Energy
   - Start Date: yesterday
   - End Date: today
   - → Save to variable `caloriesData`

4. **Find Health Samples**
   - Type: Heart Rate
   - Start Date: yesterday
   - End Date: today
   - → Save to variable `heartData`

5. **Dictionary** — Build the sleep payload:
   ```
   source: apple_health_sleep
   member_id: james
   timestamp: [Current Date, ISO 8601]
   data:
     total_minutes: [Count of sleepData]
     (other fields as available)
   ```

6. **Get Contents of URL**
   - URL: `http://pib-mini.local:3141/api/sensors/ingest`
   - Method: **POST**
   - Headers: `Content-Type` → `application/json`
   - Request Body: **JSON** → the dictionary from step 5

7. **Repeat steps 5–6** for activity, heart payloads (each as a separate POST)

8. **If** (error handling — see below)

#### Error Handling Block

Wrap each "Get Contents of URL" in an error handler:

```
Get Contents of URL...
If [Result] is [empty/error]:
    → Save Dictionary to File
      - Path: Shortcuts/PIB_Queue/health_YYYY-MM-DD.json
    → (Will be retried by the queue runner — see Section 8)
End If
```

> **Shortcut UI path:** After the "Get Contents of URL" action, add **If** → "If Result" "does not have any value" → add **Save File** action pointing to iCloud Drive or local folder.

### 6.2 PIB FindMy Location

| Property | Value |
|----------|-------|
| **Name** | `PIB FindMy Location` |
| **Trigger** | Automation → Time of Day → Every 30 min from 7 AM to 11 PM → Run Immediately |
| **Member ID** | `james` / `laura` |

> **Note:** macOS Shortcuts doesn't support "every 30 minutes" natively. Workaround: create **32 separate time-based automations** (7:00, 7:30, 8:00, ..., 22:30, 23:00). Alternatively, use a cron job to invoke the shortcut:

```bash
# Add to crontab on james-mini
# Run every 30 min from 7am to 11pm
*/30 7-22 * * * shortcuts run "PIB FindMy Location" 2>/dev/null
```

#### Shortcut Steps

1. **Get Current Location**
   - Accuracy: Best

2. **Dictionary** — Build payload:
   ```
   source: location
   member_id: james
   timestamp: [Current Date, ISO 8601]
   data:
     latitude: [Latitude of Current Location]
     longitude: [Longitude of Current Location]
     accuracy_m: 10
     altitude_m: [Altitude of Current Location]
     speed_mps: 0
   ```

3. **Get Contents of URL**
   - URL: `http://pib-mini.local:3141/api/sensors/ingest`
   - Method: **POST**
   - Headers: `Content-Type` → `application/json`
   - Request Body: **JSON** → the dictionary

4. Error handling (same pattern as 6.1)

### 6.3 PIB Focus Mode

| Property | Value |
|----------|-------|
| **Name** | `PIB Focus Mode` |
| **Trigger** | Automation → Focus → [each focus mode] → When Turning On / Off → Run Immediately |
| **Member ID** | `james` / `laura` |

> Create one automation per Focus mode (Do Not Disturb, Work, Personal, Sleep, etc.), each triggering the same shortcut with a parameter.

#### Shortcut Steps

1. **Receive** Shortcut Input (text — the focus mode name)
   - Or: Use **Get Current Focus** action (macOS 15+)

2. **Dictionary**:
   ```
   source: focus
   member_id: james
   timestamp: [Current Date, ISO 8601]
   data:
     focus_mode: [Shortcut Input]
     is_active: true
   ```

3. **Get Contents of URL** — POST to sensor ingest

4. Error handling

### 6.4 PIB Siri Capture

| Property | Value |
|----------|-------|
| **Name** | `Tell Poopsy` |
| **Trigger** | Manual (Siri: "Hey Siri, tell Poopsy buy milk") |
| **Member ID** | `james` / `laura` |

> The shortcut name `Tell Poopsy` means Siri will recognize "Tell Poopsy [anything]" as a trigger.

#### Shortcut Steps

1. **Receive** text input from Siri
   - If no input: **Ask for Input** → "What do you want to tell Poopsy?"

2. **Dictionary**:
   ```
   member_id: james
   source: siri
   text: [Shortcut Input]
   timestamp: [Current Date, ISO 8601]
   ```

3. **Get Contents of URL**
   - URL: `http://pib-mini.local:3141/api/capture/task`
   - Method: **POST**
   - Headers: `Content-Type` → `application/json`
   - Request Body: **JSON** → the dictionary

4. **If** result has value:
   - **Show Result**: "Got it! Told Poopsy: [Shortcut Input]"
5. **Otherwise**:
   - **Save File** to queue folder
   - **Show Result**: "Poopsy is offline. Saved for later."

### 6.5 PIB Battery Status

| Property | Value |
|----------|-------|
| **Name** | `PIB Battery Status` |
| **Trigger** | Automation → Time of Day → Every hour → Run Immediately |
| **Member ID** | `james` / `laura` |

> Same crontab workaround as FindMy for hourly:

```bash
0 * * * * shortcuts run "PIB Battery Status" 2>/dev/null
```

#### Shortcut Steps

1. **Get Battery Level** → variable `level`
2. **Get Battery State** (Is Charging) → variable `charging`

3. **Dictionary**:
   ```
   source: battery
   member_id: james
   timestamp: [Current Date, ISO 8601]
   data:
     device: mac_mini
     level_pct: [level]
     is_charging: [charging]
     battery_state: [if charging then "charging" else "unplugged"]
     low_power_mode: false
   ```

4. **Get Contents of URL** — POST to sensor ingest

5. Error handling

### 6.6 Local Queue Runner (Error Recovery)

For when the CoS is unreachable, shortcuts save payloads to a local queue folder. A cron job retries them:

Create `~/Scripts/pib_queue_flush.sh`:

```bash
#!/bin/bash
QUEUE_DIR="$HOME/Library/Mobile Documents/iCloud~is~workflow~my~workflows/Documents/PIB_Queue"
COS_HOST="${COS_HOST:-pib-mini.local}"

# Check if CoS is reachable
if ! curl -sf "http://${COS_HOST}:3141/health" > /dev/null 2>&1; then
    exit 0  # CoS down, try later
fi

for f in "$QUEUE_DIR"/*.json; do
    [ -f "$f" ] || continue
    endpoint=$(jq -r '.endpoint // "/api/sensors/ingest"' "$f")
    payload=$(jq -c 'del(.endpoint)' "$f")

    if curl -sf -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "http://${COS_HOST}:3141${endpoint}"; then
        rm "$f"
        echo "Flushed: $(basename "$f")"
    fi
done
```

```bash
chmod +x ~/Scripts/pib_queue_flush.sh

# Run every 5 minutes
(crontab -l 2>/dev/null; echo "*/5 * * * * $HOME/Scripts/pib_queue_flush.sh") | crontab -
```

---

## 7. HomeKit Bridge Options

### Option A: Apple Shortcuts Automations (Simplest)

**How it works:** Create a Shortcuts automation for each device × each state change. Each automation POSTs to the CoS sensor endpoint.

| Pros | Cons |
|------|------|
| No extra software | One automation per device per state = many automations |
| Native Apple | Can't capture all state changes (only those with automation triggers) |
| Zero maintenance | No centralized config |

**Best for:** ≤5 devices with simple states.

### Option B: Homebridge + Webhook Plugin (Recommended) ✅

**How it works:** Homebridge runs on James's Mini, exposes HomeKit accessories via HAP protocol. The `homebridge-webhook` plugin forwards all state changes to the CoS via HTTP webhooks.

| Pros | Cons |
|------|------|
| All devices in one config | Requires Node.js + Homebridge |
| Auto-forwards all state changes | Another service to maintain |
| Web UI for management | Initial setup complexity |
| Plugin ecosystem | |

**Setup:** See Section 2.5 above.

#### Webhook Forwarding Script

Instead of relying solely on the homebridge-webhook plugin's built-in forwarding, add a forwarding script for reliability. Create `~/Scripts/homebridge_forwarder.js`:

```javascript
const http = require('http');

const COS_HOST = process.env.COS_HOST || 'pib-mini.local';
const LISTEN_PORT = 51829;

const server = http.createServer((req, res) => {
  if (req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      const event = JSON.parse(body);

      const payload = JSON.stringify({
        source: 'homekit',
        member_id: 'james',
        timestamp: new Date().toISOString(),
        data: {
          device_id: event.accessory,
          device_name: event.name || event.accessory,
          device_type: event.type || 'unknown',
          state: event.value,
          changed_at: new Date().toISOString()
        }
      });

      const options = {
        hostname: COS_HOST,
        port: 3141,
        path: '/api/sensors/ingest',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload)
        }
      };

      const fwd = http.request(options, (fwdRes) => {
        res.writeHead(200);
        res.end('forwarded');
      });

      fwd.on('error', () => {
        // Queue locally on failure
        const fs = require('fs');
        const queueDir = `${process.env.HOME}/Scripts/homekit_queue`;
        fs.mkdirSync(queueDir, { recursive: true });
        fs.writeFileSync(
          `${queueDir}/${Date.now()}.json`,
          payload
        );
        res.writeHead(200);
        res.end('queued');
      });

      fwd.write(payload);
      fwd.end();
    });
  }
});

server.listen(LISTEN_PORT, () => {
  console.log(`HomeKit forwarder listening on :${LISTEN_PORT}`);
});
```

Run as a service:

```bash
# Create launchd plist
cat > ~/Library/LaunchAgents/com.pib.homekit-forwarder.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pib.homekit-forwarder</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/node</string>
        <string>/Users/james/Scripts/homebridge_forwarder.js</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>COS_HOST</key>
        <string>pib-mini.local</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/homekit-forwarder.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/homekit-forwarder.err</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.pib.homekit-forwarder.plist
```

### Option C: Homebridge + MQTT (Most Flexible)

**How it works:** Homebridge publishes state changes to an MQTT broker. The CoS subscribes to MQTT topics.

| Pros | Cons |
|------|------|
| Decoupled pub/sub | Requires MQTT broker (Mosquitto) |
| Most reliable delivery | Most complex setup |
| Supports bidirectional control | Another service to run |

**Skip this unless** you need bidirectional HomeKit control from the CoS (e.g., PIB locking doors).

---

## 8. Network & Security

### LAN-Only Architecture

All traffic between the three Minis stays on the local network. **No ports are exposed to the internet.**

```
Internet ──── Router/Firewall ──── LAN
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
               CoS Mini       James Mini       Laura Mini
             :3141 (API)    :1234 (BB)       :1234 (BB)
                            :8581 (HB UI)
                            :51826 (HAP)
                            :51829 (Fwd)
```

### Bearer Token Authentication (Recommended)

Add a shared secret for sensor endpoints:

On the CoS, configure the API to require a bearer token:

```
Authorization: Bearer <SENSOR_TOKEN>
```

On each Mini, store the token:

```bash
# Add to ~/.zshrc on each Mini
export PIB_SENSOR_TOKEN="your-shared-secret-here"
```

Update all Shortcuts to include the header:
- In "Get Contents of URL" → Headers → add `Authorization` → `Bearer [your-token]`

Update the queue flush script to include `-H "Authorization: Bearer ${PIB_SENSOR_TOKEN}"`.

### Firewall Rules

#### CoS Mini

```bash
# Allow sensor ingest from LAN only
# In System Settings → Network → Firewall → Options:
# - Enable Firewall
# - Allow incoming connections for: Node.js (port 3141)
```

Or via `pf`:

```bash
# /etc/pf.anchors/pib
pass in on en0 proto tcp from 192.168.1.0/24 to any port 3141
block in on en0 proto tcp from any to any port 3141
```

#### James's Mini

```bash
# Allow BlueBubbles (1234), Homebridge UI (8581), HAP (51826) from LAN
pass in on en0 proto tcp from 192.168.1.0/24 to any port { 1234, 8581, 51826, 51828, 51829 }
```

#### Laura's Mini

```bash
# Allow BlueBubbles (1234) from LAN only
pass in on en0 proto tcp from 192.168.1.0/24 to any port 1234
```

### When CoS Is Down

Each Mini implements local queuing (see Section 6.6):

1. Shortcut POSTs fail → payload saved to local JSON file in queue folder
2. Cron job (`pib_queue_flush.sh`) checks CoS health every 5 minutes
3. When CoS comes back, queued payloads are replayed in order
4. Successfully sent payloads are deleted from queue

**Data loss window:** Sensor data generated between queue-flush attempts (max 5 min) could be lost if the Mini itself crashes. This is acceptable for sensor data.

---

## 9. Maintenance & Monitoring

### Checking Bridge Status

#### From James's Mini

```bash
# BlueBubbles
curl -sf http://localhost:1234/api/v1/server/info && echo "BB OK" || echo "BB DOWN"

# Homebridge
curl -sf http://localhost:8581 && echo "HB OK" || echo "HB DOWN"

# HomeKit Forwarder
curl -sf http://localhost:51829 && echo "Fwd OK" || echo "Fwd DOWN"
```

#### From Laura's Mini

```bash
# BlueBubbles
curl -sf http://localhost:1234/api/v1/server/info && echo "BB OK" || echo "BB DOWN"
```

#### From CoS Mini

```bash
# Check all bridges remotely
for host in james-mini.local laura-mini.local; do
    echo "=== $host ==="
    curl -sf "http://${host}:1234/api/v1/server/info" && echo "BB OK" || echo "BB DOWN"
done

# Check James's Homebridge
curl -sf http://james-mini.local:8581 && echo "HB OK" || echo "HB DOWN"
```

### CoS-Side: Sensor Staleness Detection

The c40v sensor bus already tracks last-seen timestamps per source per member. If a sensor hasn't reported within its expected interval + grace period, it's flagged as stale.

| Sensor | Expected Interval | Stale After |
|--------|-------------------|-------------|
| health_* | 24h | 36h |
| location | 30min | 2h |
| focus | event-driven | 24h (no focus change in a day is unusual but valid) |
| battery | 1h | 3h |
| homekit | event-driven | 24h |

### Restart Procedures

#### BlueBubbles (either Mini)

```bash
# Force quit and reopen
killall BlueBubbles
open -a BlueBubbles
```

Or via System Settings → General → Login Items — ensure BlueBubbles is listed.

#### Homebridge (James's Mini)

```bash
sudo homebridge-config-ui-x service restart
```

Or via the web UI at `http://james-mini.local:8581` → top-right power icon → Restart.

#### HomeKit Forwarder (James's Mini)

```bash
launchctl unload ~/Library/LaunchAgents/com.pib.homekit-forwarder.plist
launchctl load ~/Library/LaunchAgents/com.pib.homekit-forwarder.plist
```

#### Full Mini Restart

```bash
# Remote restart via SSH
ssh james@james-mini.local 'sudo shutdown -r now'
```

### macOS Auto-Update Policy

**Auto-updates are disabled** (Section 2.1). Updates are done manually:

1. Check for updates: **System Settings → General → Software Update**
2. Coordinate with CoS downtime window
3. Update one Mini at a time
4. Verify all services restart correctly after update
5. Log the update in the CoS ops ledger

---

## 10. Troubleshooting

### BlueBubbles Disconnects

**Symptom:** iMessage bridge stops forwarding messages.

| Check | Fix |
|-------|-----|
| Is BB running? | `pgrep -f BlueBubbles` — if empty, restart |
| Is iMessage signed in? | Open Messages app, check Settings → iMessage |
| Full Disk Access revoked? | System Settings → Privacy & Security → Full Disk Access → ensure BB checked |
| macOS update changed permissions? | Re-grant Full Disk Access and Accessibility |
| Webhook URL wrong? | Open BB → Settings → Webhooks → verify URL matches `http://$COS_HOST:3141/api/webhooks/bluebubbles/[member]` |

**Nuclear option:**
```bash
# Reset BlueBubbles
killall BlueBubbles
rm -rf ~/Library/Application\ Support/BlueBubbles
# Reopen and reconfigure from scratch
open -a BlueBubbles
```

### Shortcuts Failing Silently

**Symptom:** Sensor data stops arriving at CoS, but no errors visible.

| Check | Fix |
|-------|-----|
| Is the automation enabled? | Shortcuts → Automations → verify toggle is ON |
| "Ask Before Running" enabled? | Must be OFF for background automations. Edit automation → disable "Ask Before Running" |
| Did macOS update reset automations? | Re-check all automations after any macOS update |
| Network issue? | `curl -sf http://$COS_HOST:3141/health` from the Mini |
| Check queue folder | `ls ~/Library/Mobile\ Documents/iCloud~is~workflow~my~workflows/Documents/PIB_Queue/` |
| Shortcut permissions revoked? | Run the shortcut manually — macOS will re-prompt for permissions |

**Debug a shortcut:**
1. Open Shortcuts app
2. Click the shortcut
3. Click ▶️ (Run) button
4. Watch for errors in each step

### Health Permissions

**Symptom:** Health Export shortcut returns empty data.

| Check | Fix |
|-------|-----|
| Health access granted? | System Settings → Privacy & Security → Health → ensure Shortcuts is checked |
| No Health data on Mac? | Health data syncs from iPhone/Watch. Ensure the Mac has the same Apple ID and Health sync is enabled |
| Data type not available? | Some Health data types are only available on iPhone. May need to run the Health Export shortcut from iPhone instead |

**iPhone Health permissions:**
1. Open **Health** app on iPhone
2. Tap profile icon → **Apps** → **Shortcuts**
3. Enable all required data types: Sleep, Steps, Active Energy, Heart Rate, Medications

### HomeKit Pairing Issues

**Symptom:** Homebridge accessories not appearing in Home app.

| Check | Fix |
|-------|-----|
| Homebridge running? | `curl -sf http://localhost:8581` |
| PIN correct? | Check `~/.homebridge/config.json` → `bridge.pin` |
| Already paired? | Remove from Home app → re-pair |
| Port conflict? | `lsof -i :51826` — ensure nothing else uses the HAP port |
| mDNS/Bonjour issue? | Restart Bonjour: `sudo launchctl kickstart -k system/com.apple.mDNSResponder` |

**Reset Homebridge pairing:**
```bash
sudo homebridge-config-ui-x service stop
rm -rf ~/.homebridge/persist ~/.homebridge/accessories
sudo homebridge-config-ui-x service start
# Re-pair in Home app
```

### CoS Unreachable from Minis

```bash
# Basic connectivity
ping -c 3 $COS_HOST

# Port check
nc -zv $COS_HOST 3141

# Health endpoint
curl -v http://$COS_HOST:3141/health

# DNS resolution
dscacheutil -q host -a name pib-mini.local
```

If mDNS fails, fall back to IP address:
```bash
# On the CoS Mini, get its IP
ifconfig en0 | grep 'inet '
# Update $COS_HOST on each personal Mini to use the IP
```

### Cron Jobs Not Running

```bash
# Check if cron is allowed
# System Settings → Privacy & Security → Full Disk Access → add /usr/sbin/cron

# List current crontab
crontab -l

# Check cron logs
log show --predicate 'process == "cron"' --last 1h
```

---

## Appendix A: Complete Crontab for James's Mini

```bash
# PIB Sensor Automations
# FindMy Location — every 30 min, 7am-11pm
*/30 7-22 * * * /usr/bin/shortcuts run "PIB FindMy Location" 2>/dev/null

# Battery Status — every hour
0 * * * * /usr/bin/shortcuts run "PIB Battery Status" 2>/dev/null

# Queue Flush — every 5 min
*/5 * * * * $HOME/Scripts/pib_queue_flush.sh 2>/dev/null
```

## Appendix B: Complete Crontab for Laura's Mini

```bash
# PIB Sensor Automations
# FindMy Location — every 30 min, 7am-11pm
*/30 7-22 * * * /usr/bin/shortcuts run "PIB FindMy Location" 2>/dev/null

# Battery Status — every hour
0 * * * * /usr/bin/shortcuts run "PIB Battery Status" 2>/dev/null

# Queue Flush — every 5 min
*/5 * * * * $HOME/Scripts/pib_queue_flush.sh 2>/dev/null
```

## Appendix C: Quick Verification Checklist

Run through this after setting up each Mini:

- [ ] Hostname set correctly (`hostname` returns expected name)
- [ ] `$COS_HOST` resolves (`ping $COS_HOST`)
- [ ] CoS API reachable (`curl http://$COS_HOST:3141/health`)
- [ ] BlueBubbles running and webhook configured
- [ ] Send a test iMessage → verify it appears in CoS logs
- [ ] Run each Shortcut manually → verify data arrives at CoS
- [ ] Crontab installed (`crontab -l`)
- [ ] Queue flush script works (`bash ~/Scripts/pib_queue_flush.sh`)
- [ ] (James only) Homebridge running (`curl http://localhost:8581`)
- [ ] (James only) HomeKit devices visible in Home app
- [ ] (James only) HomeKit state change → CoS receives sensor event
- [ ] Sleep prevention working (leave overnight, check uptime next day)
- [ ] Reboot and verify all services auto-start
