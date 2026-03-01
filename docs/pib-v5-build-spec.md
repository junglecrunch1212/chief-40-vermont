# PIB v5 — Build Specification

## A Prosthetic Prefrontal Cortex That Happens to Manage a Household

**For:** A fresh Claude Code instance. Zero family context. Build end-to-end from this document.
**Lineage:** v4 engineering (SQLite, ingestion pipeline, undo log, state machine, write batching, relevance detection) + PIB behavioral philosophy (Nine Genes, dark prosthetics, ADHD scorecard, Coach protocols).
**Host:** Mac Mini M2+ (headless, always-on, closet)
**Identity:** PIB (Poopsy-in-a-Box) 💩 — they/them

---

## 0. WHAT PIB IS

PIB is NOT a to-do app. It is NOT a chatbot. It is a prosthetic prefrontal cortex that competes on neurochemistry — stealing addiction mechanics from social media and redirecting them toward real-world outcomes.

A family of four — James (43, stay-at-home dad, ADHD), Laura (38, family law partner), Charlie (6, shared custody with coparent), and a baby girl arriving May 2026 — runs their household through a Mac Mini in the closet.

The system answers one question: **whatNow()?**

Given this person, their tasks, their schedule, their budget, their energy level, their medication state, and the time of day — what is the ONE thing they should do next? Not a list. One thing. With the first physical action spelled out.

Everything else — calendar intelligence, financial tracking, communication logging, memory, proactive messaging — exists to make that one answer better.

### The Three Layers

```
LAYER 3: EXTENDED — External APIs, device bridges, plugins
  "Book it for me" · "Track my flight" · "Sync Apple Watch"
  Failure mode: APIs change, auth expires. Degrades to Layer 2.

LAYER 2: ENHANCED — Claude intelligence via reasoning + tools
  "Research flights" · "Compare options" · "Draft this message"
  Failure mode: Anthropic API down. Degrades to Layer 1.

LAYER 1: CORE — SSOT + schemas + deterministic functions + whatNow()
  "What's next?" · "Who has Charlie?" · "What's left on the list?"
  Failure mode: NONE. Data on disk. Deterministic code. Always works.
```

Every feature declares its layer. Layer 1 delivers full value alone.

---

## 1. THE NINE GENES — IMMUTABLE DNA

### Gene 1: The Loop

```
DISCOVER → PROPOSE → CONFIRM → CONFIG → DETERMINISTIC
```

AI discovers what exists (reads actual APIs, actual Sheets, actual calendar feeds). AI proposes classification. Human confirms or corrects. Classification becomes config. Execution is deterministic — no LLM in the data path. Nothing is auto-classified. Nothing is auto-applied.

### Gene 2: The Vocabulary

Every data source gets four labels:

```python
@dataclass
class SourceClassification:
    relevance: str      # blocks_member, blocks_household, blocks_assignee,
                        # custody_state, asset_availability, awareness, awareness_external
    ownership: str      # member, shared, external
    privacy: str        # full → complete content enters context
                        # privileged → existence + timing only ("Laura has a meeting 2-4pm")
                        # redacted → existence only ("Laura is unavailable")
    authority: str      # system_managed, human_managed, hybrid
```

`privacy: privileged` means content NEVER enters the LLM context window. Filtered at the read layer, not the prompt layer.

### Gene 3: The Five Shapes

Every data source collapses into one of five shapes before anything downstream touches it: **TASK, TIME BLOCK, MONEY STATE, RECURRING TEMPLATE, ENTITY.** A household with 5 calendars and one with 50 produce the same shapes. Arrays are longer. Shapes are identical.

### Gene 4: The Read Layer

Two external reads. Read-only. Never writes to calendars or moves money. If a read breaks, the system degrades — it doesn't corrupt.

| Source Down | Impact | Mitigation |
|---|---|---|
| Google Calendar | Stale daily state | Use last-known + warn |
| Bank/Plaid | No affordability checks | Skip budget context |
| Gmail | No new comm logging | Other capture still works |
| Apple Reminders | No Reminders capture | SMS/Siri still works |
| BlueBubbles | No iMessage | Fall back to Twilio SMS |
| Anthropic API | No LLM composition | Template fallbacks, whatNow() still works |

### Gene 5: whatNow()

The single query the entire system exists to answer. Deterministic. No LLM. No side effects. Returns ONE task, not a list. Full implementation in Section 4.

### Gene 6: The Write Layer

1. **Append-only.** Never delete. Change status. Log the change.
2. **Confirm gates.** Irreversible actions require human yes.
3. **Privacy fence.** Writes cannot output data the read layer didn't provide.

### Gene 7: The Invariants

1. No row is ever deleted from the task store.
2. Recurring spawns are idempotent.
3. The system never writes to a calendar.
4. The system never moves money.
5. Privileged data never enters the context window. Filtered at read.
6. whatNow() is deterministic. No LLM in the function.
7. Every task has a micro_script.
8. Classification happens at onboarding. Execution never reclassifies. (Exception: email triage.)
9. Config changes require human confirmation.
10. The LLM recommends. The write layer executes.

### Gene 8: The Growth Rule

Every new feature is: NEW SOURCE (runs The Loop), NEW COLUMN (added to shape), NEW WRITE (new function), or NEW SURFACE (new view of whatNow()). The 8-step domain wiring pattern:

```
1. SSOT     — where data lives
2. READ     — adapter that returns { ok, items, summary }
3. WRITE    — how data gets in
4. CONTEXT  — what the AI knows
5. COACH    — how the AI behaves
6. CADENCE  — when the AI proactively acts
7. CONSOLE  — what the user sees
8. PROBE    — how we know it's working
```

### Gene 9: The Probe

The Loop watches for changes: new source → propose classification → wait. Source lost → notify → remove if confirmed. Access changed → reclassify if needed. Never auto-applies.

---

## 2. THE FOUR ACTORS (and future ones)

### 2.1 James (Co-head, ADHD, stay-at-home parent)
Full prosthetic. PIB IS his prefrontal cortex. View mode: stream carousel — ONE card at a time. Always micro-scripts. Always energy matching. Variable-ratio rewards on completion. Morning briefing is the daily reset.

**Primary channels:** iMessage (most messages), web dashboard (when at desk), Siri Shortcuts (voice capture)

**What James sees — carousel view (web dashboard):**
```
┌─────────────────────────────────────┐
│  🟢 HIGH ENERGY · Streak: 7 days    │
│                                      │
│  Call roofer about leak estimate     │
│                                      │
│  📱 Pick up phone → call Dan at     │
│     (404) 555-0142 → ask about      │
│     Saturday availability            │
│                                      │
│  [ ✅ Done ]          [ → Skip ]     │
│                                      │
│  ─── one more? ───                   │
│  "Schedule Charlie dentist" (3 min)  │
└─────────────────────────────────────┘
```
One card. One action. Micro-script tells him exactly what to do physically. Done = one tap. Skip = requires a date ("when instead?"). Dismiss = requires 10 chars why.

> **🆕 CONSOLE UPDATE — Stream Metaphor & ADHD Affordances**

**Stream metaphor:** James's Today view is a unified stream of progress dots mixing endowed items ("Woke up", "Opened PIB"), completed calendar events, done tasks, upcoming calendar events, and pending tasks. The stream externalizes episodic memory — the user can swipe backward to review accomplishments and forward to see what's next. `whatNow()` provides task ordering; the stream wraps it with calendar context and endowed progress.

**Endowed progress:** The day starts at 2+ dots (woke up, opened app), not zero. This exploits the endowment effect to reduce ADHD activation energy. The user never faces an empty progress bar — they've already begun.

**Progress dots:** A horizontal dot row tracks the full day. Six states:

| State | Color | Behavior |
|-------|-------|----------|
| `endowed` | Gray, faded (50% opacity) | Pre-credited progress |
| `done` | Green | Completed items |
| `skipped` | Yellow | Explicitly skipped |
| `current` | Pink, enlarged, pulsing | Active focus item |
| `urgent` | Red | Past-due or time-critical |
| `pending` | Light gray | Not yet reached |

Dots are clickable for direct navigation. Position indicator shows `N / total`.

**Keyboard navigation:** `←` `→` to browse the stream, `Enter` to complete current task, `Esc` to skip. Zero mouse movement required for desk users.

**Radar:** Below the carousel card, display the next 3 calendar events within a 2-hour window. Peripheral time awareness without page switching:
```
⏰ NEXT UP
  10:30  Grocery delivery window (26 min)
  13:00  Team standup (1h 56m)
  15:30  Charlie pickup (3h 26m)
```

**Glow animation:** Active task card border pulses subtly (pink glow, `box-shadow: 0 0 0 8px rgba(232,160,191,0.15)`) to direct ADHD attention to the current action.

**What James gets via iMessage:**
```
Morning (6:30 AM):
  ☀️ Good morning. Rough sleep → easy day mode.
  Your three things: pay electric bill, call roofer, pick up prescription.
  Charlie's with you today. Laura has meetings 2-4.
  
After task completion:
  Done ✓ That's 4 today — nice run.
  One more? "Pick up prescription" — just 10 min.

Paralysis detection (2h silence during peak):
  Hey — noticed it's been quiet. No pressure.
  Smallest thing: "move laundry to dryer" (2 min).
```

### 2.2 Laura (Co-head, attorney)
Selective prosthetic. HOME life only. View mode: compressed bullets. Privacy: work calendar is `privileged` — timing only, never content. Only sees what needs her attention.

**Primary channels:** iMessage (brief alerts), web dashboard (weekly review)

**What Laura sees — compressed view (web dashboard):**
```
┌─────────────────────────────────────┐
│  DECISIONS NEEDED                    │
│  · Approve babysitter for Saturday   │
│    ($85, 5-10pm)          [Y] [N]   │
│  · Charlie field trip: sign form     │
│    by Thursday             [Done]    │
│                                      │
│  YOUR TASKS (2)                      │
│  · Schedule pediatrician      Due Fri│
│  · Review insurance renewal   Due Mon│
│                                      │
│  HOUSEHOLD STATUS                    │
│  ✅ James: 6 tasks done today        │
│  ✅ Charlie: chores current          │
│  ⚠️ Budget: dining 82% of target    │
│  🐕 Captain: walked, fed, next 6pm  │
└─────────────────────────────────────┘
```
No preamble. No emoji stories. Binary decisions surfaced as buttons. Her tasks are hers — PIB never nags, just tracks. Household status is a glanceable summary she can ignore.

**What Laura gets via iMessage:**
```
Decision needed:
  Babysitter Saturday? $85, 5-10pm. [Yes / No]

Conflict alert:
  ⚠️ Charlie pickup 3pm Thursday conflicts 
  with your meeting (ends 4pm). James can cover.
  Want him to? [Yes / I'll handle]

Weekly (Sunday 8pm):
  This week: 3 tasks done, 1 carried over. 
  Budget: $280 remaining for groceries.
  No outstanding decisions.
```
Max 2 messages/day unless critical. Laura's work context is NEVER referenced — PIB doesn't know she has a deposition Tuesday, only that she's "unavailable 2-4."

### 2.3 Charlie (Child, 6, shared custody)
Passive actor. Never directly interacts with PIB. Data flows about him, never to him.

**What Charlie sees — scoreboard (kitchen TV, from 10 feet):**
```
┌─────────────────────────────────────┐
│        ⭐ CHARLIE'S BOARD ⭐         │
│                                      │
│   🔥 Streak: 4 days!                │
│                                      │
│   Today:                             │
│   ✅ Made bed           +2 ⭐        │
│   ✅ Put dishes in sink +1 ⭐        │
│   ⬜ Put away backpack  +2 ⭐        │
│   ⬜ Feed Captain       +3 ⭐        │
│                                      │
│   This week: 24 ⭐                   │
│   🏆 25 ⭐ = pick Friday movie!     │
│                                      │
│   🐕 Captain: Fed ✓ Walked ✓        │
└─────────────────────────────────────┘
```
Large text, high contrast. Stars not points. Simple icons. No financial, health, or adult data ever visible. Streaks pause automatically on custody-away days (no penalty for being at the other parent's house). Milestones are real-world rewards negotiated by parents, stored in `pib_config`.

> **🆕 CONSOLE UPDATE — Child View Privacy Enforcement**

When viewing as Charlie, the console renders without sidebar chrome. Full-screen child view only. No admin navigation visible (Tasks, People, Settings nav items are hidden). The actor switcher remains accessible only as an overlay for parents to switch back. This enforces the privacy invariant that no adult data — no task lists, no financial info, no schedule details, no people/CRM data — is ever visible on the child's screen. The child view shows only: Today (scoreboard-style chores), Scoreboard, Chat (kid-safe), Lists, and Schedule (child events only).

**Age progression plan:**
- Age 6-8 (current): Visual scoreboard, parent-managed chores, stars → rewards
- Age 8-10: Simple text notifications to a kid's device ("Time to feed Captain!"), self-check-off via tablet
- Age 10-12: Own view mode (`child_active`), can add items to grocery list, sees own schedule
- Age 13+: Graduated to `standard` view, can interact with PIB directly, age-appropriate task management

Transition triggers: Parent manually updates `view_mode` in member config. PIB proposes upgrade at birthday via morning digest ("Charlie turns 8 next month — ready for notifications on a device?").

### 2.4 Captain (Dog)
Tracked entity (`ops_item`, type: `pet`). Recurring tasks: walks (7am, 12pm, 6pm), feeding (7am, 5pm), monthly heartworm meds.

**Scoreboard display:** "🐕 Captain: Walked ✓ · Fed ✓ · Next walk: 6pm"

**When a non-household member is watching Captain** (friend, dog walker, pet sitter):
Temporary member added with role `other`, `can_receive_messages = 1`, `preferred_channel = sms`, `view_mode = standard`. Sees ONLY Captain-related recurring tasks. Auto-expires after the defined date range. Created via:
```
james: "dog sitter Sarah 555-0199 March 3-5"
→ PIB creates temp member, assigns Captain tasks, sends Sarah a welcome SMS:
  "Hi Sarah! PIB here — James's household helper. 
   Captain schedule: Walk 7am/12pm/6pm, feed 7am/5pm.
   Reply 'walked' or 'fed' to log. Text me if anything comes up."
```

### 2.5 Baby Girl (arriving May 2026)

**Pre-arrival:** Member `m-baby` added to `common_members` with `role = child`, `is_household_member = 1`, `can_be_assigned_tasks = 0`, `view_mode = entity` (tracked, not interactive). Life phase `phase-newborn` activates at birth.

**Life phase transitions (stored in `common_life_phases`):**

| Phase | Trigger | Duration | Key Overrides |
|-------|---------|----------|--------------|
| `phase-prep` | Manual (now) | Until birth | Add baby tasks to queue, track purchases |
| `phase-newborn` | Manual ("baby's here") | 0-3 months | `velocity_cap: 5`, `max_proactive: 2/day`, suppress CRM nudges, suppress non-critical alerts |
| `phase-infant` | Date-based (3 months) + confirm | 3-12 months | Restore `velocity_cap: 10`, add pediatrician recurring, track milestones |
| `phase-toddler` | Date-based (12 months) + confirm | 12-36 months | Add childproofing tasks, adjust routines, begin tracking naps/schedule |
| `phase-preschool` | Date-based (3 years) + confirm | 3-5 years | Add to scoreboard (simple chores), school calendar integration |

**Transition mechanism:** PIB proposes transitions via morning digest on the target date: "Baby Girl is 3 months old today. Ready to move from newborn mode to infant mode? This restores your velocity cap to 10 and adds pediatrician scheduling." James confirms. Gene 1 pattern: DISCOVER (date reached) → PROPOSE (suggest transition) → CONFIRM (James says yes) → CONFIG (update life phase). Never auto-transitions.

### 2.6 Future Members (onboarding flow)

Any new person in the household universe — nanny, babysitter, grandparent visiting, coparent — follows the same onboarding:

```
james: "add nanny Maria 555-0188 Mon/Wed/Fri 8am-1pm"
```

PIB runs The Loop:
1. **DISCOVER:** Parse message → new member with role, contact, schedule pattern
2. **PROPOSE:** "Adding Maria as nanny: Mon/Wed/Fri 8-1pm, SMS channel, sees only: tasks assigned to her, Charlie's schedule, Captain care. Confirm?"
3. **CONFIRM:** James confirms
4. **CONFIG:** Member created, recurring schedule blocks added, welcome SMS sent

**Role-based visibility:**

| Role | Sees | Doesn't See |
|------|------|-------------|
| `nanny` | Assigned tasks, child schedule, Captain care, household emergency contacts | Finances, adult schedules, health data, legal matters |
| `babysitter` | Same as nanny but time-limited (auto-expires after scheduled end) | Same as nanny |
| `grandparent` | Household schedule (privacy-filtered), child info, meal preferences | Finances, work calendars, custody details |
| `coparent` | Shared custody schedule, child logistics, handoff tasks | Household finances, adult personal tasks, work data |
| `dog_walker` | Captain tasks only | Everything else |

Privacy enforced by `common_source_classifications.authority` — each role maps to a set of allowed domains. Read layer filters at query time, same mechanism as Laura's work calendar privacy.

---

## 3. INFRASTRUCTURE

### 3.1 Stack

```
Mac Mini "COS-1" (headless, closet, always-on)
├── macOS Sequoia 15+ (manual updates only — Sundays with backup)
├── /opt/pib/data/pib.db           — THE DATABASE (SQLite 3.45+, WAL mode)
├── Python 3.12+ (venv: /opt/pib/venv)
│   ├── FastAPI (port 3141)
│   ├── aiosqlite, APScheduler (AsyncIOScheduler — never BlockingScheduler), httpx, anthropic SDK
├── BlueBubbles v1.9+ (iMessage bridge)
├── Cloudflare Tunnel + Access (Google OAuth)
│   ├── /api, /webhooks, /dashboard, /scoreboard
└── External: Twilio, Google APIs (Calendar, Sheets, Gmail)
```

### 3.2 Authentication (from day one)
- Web + API: Cloudflare Access (Google OAuth, James + Laura)
- Twilio: Request signature validation
- BlueBubbles: Shared secret
- Siri Shortcuts: Bearer token
- Sheets webhook: Service account key

### 3.3 Rate Limiting (all webhook endpoints)

```python
from collections import defaultdict
import time

class RateLimiter:
    """Per-source rate limiting. Prevents webhook abuse and runaway retry loops."""
    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)
    
    def check(self, source: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
        now = time.time()
        self._windows[source] = [t for t in self._windows[source] if t > now - window_seconds]
        if len(self._windows[source]) >= max_requests:
            return False
        self._windows[source].append(now)
        return True

RATE_LIMITS = {
    "twilio":     {"max": 30, "window": 60},    # 30 SMS/min
    "siri":       {"max": 20, "window": 60},     # 20 shortcuts/min
    "bluebubbles":{"max": 60, "window": 60},     # 60 messages/min
    "sheets":     {"max": 30, "window": 60},     # 30 edits/min
    "web_chat":   {"max": 10, "window": 60},     # 10 messages/min per session
}
# Apply in FastAPI middleware: return 429 when exceeded.
```

### 3.4 Structured Logging

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            **(record.__dict__.get("extra", {}))
        })

def setup_logging():
    handler = logging.handlers.RotatingFileHandler(
        "/opt/pib/logs/pib.jsonl",
        maxBytes=50_000_000,  # 50MB per file
        backupCount=5
    )
    handler.setFormatter(JSONFormatter())
    
    root = logging.getLogger("pib")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    
    # Also log to stdout for launchd capture
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(JSONFormatter())
    root.addHandler(stdout_handler)

# Usage: log.info("Task completed", extra={"task_id": "t-0042", "member": "m-james"})
```

### 3.5 SQLite Configuration

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;
PRAGMA mmap_size = 268435456;
```

### 3.6 Write Batching

```python
class WriteQueue:
    """Queues writes, flushes every 100ms or 50 items. Single transaction per batch.
    Uses a PERSISTENT connection — never opens/closes per flush.
    At 10 flushes/sec, a connect-per-flush design would create 864K connections/day."""
    
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._queue: asyncio.Queue = asyncio.Queue()
        self._db: aiosqlite.Connection | None = None  # Persistent
    
    async def start(self):
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA busy_timeout=5000")
        asyncio.create_task(self._flush_loop())
    
    async def stop(self):
        if self._db:
            await self._db.close()
    
    async def enqueue(self, op: WriteOp) -> WriteResult:
        future = asyncio.get_event_loop().create_future()
        await self._queue.put((op, future))
        return await future
    
    async def _flush_loop(self):
        while True:
            batch = await self._collect_batch()
            try:
                await self._db.execute("BEGIN IMMEDIATE")
                for op, future in batch:
                    result = await self._execute_op(self._db, op)
                    future.set_result(result)
                await self._db.commit()
            except Exception as e:
                await self._db.rollback()
                for _, future in batch:
                    if not future.done():
                        future.set_exception(e)
```

**Critical rule:** Never hold a database transaction open across an LLM API call.

**Critical rule:** APScheduler MUST use `AsyncIOScheduler`, never `BlockingScheduler` or `BackgroundScheduler`. Blocking schedulers freeze the FastAPI event loop, causing webhook timeouts during cron jobs. Every scheduled job must be an `async def` coroutine:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()
scheduler.add_job(calendar_sync, CronTrigger.from_crontab("*/15 * * * *"))
scheduler.start()  # Runs inside the existing asyncio event loop
```

### 3.7 ID Generator

Per-prefix sequential IDs (t-0001, i-0042, g-0007) avoid confusing gaps. **CRITICAL: Never interpolate the prefix into SQL with f-strings.** Use parameterized queries only.

```python
# ID sequence table
# CREATE TABLE IF NOT EXISTS common_id_sequences (
#     prefix TEXT PRIMARY KEY,
#     next_val INTEGER NOT NULL DEFAULT 1
# );

VALID_PREFIXES = frozenset({"t", "i", "g", "r", "c", "l", "e", "cf", "d"})

async def next_id(db, prefix: str) -> str:
    """Generate next sequential ID. Prefix is validated against allowlist, never interpolated."""
    if prefix not in VALID_PREFIXES:
        raise ValueError(f"Invalid ID prefix: {prefix}")
    
    # Atomic increment using parameterized query
    await db.execute(
        "INSERT INTO common_id_sequences (prefix, next_val) VALUES (?, 1) "
        "ON CONFLICT(prefix) DO UPDATE SET next_val = next_val + 1",
        (prefix,)  # PARAMETERIZED — never f-string
    )
    row = await db.execute_fetchone(
        "SELECT next_val FROM common_id_sequences WHERE prefix = ?",
        (prefix,)
    )
    return f"{prefix}-{row['next_val']:04d}"
```

### 3.8 Full Schema

All tables in single namespace with prefix conventions. Tables are grouped by domain.

```
pib.db
├── common_*  — members, source classifications, custody, locations, life phases,
│               household config, audit, undo, dead letter, idempotency
├── ops_*     — tasks, goals, items, recurring, comms, lists, dependencies,
│               gmail whitelist, streaks
├── cal_*     — sources, raw events, classified events, daily states, conflicts,
│               disambiguation rules
├── fin_*     — transactions, budget config, merchant rules, capital expenses,
│               recurring bills, budget snapshot
├── mem_*     — sessions, messages, session facts, long-term memory, digests,
│               approvals, cos activity
├── pib_*     — reward log, energy states, coach protocols
└── meta_*    — schema version, migrations, discovery reports
```

#### common_* Tables

```sql
CREATE TABLE IF NOT EXISTS meta_schema_version (
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    description TEXT
);

-- Discovery reports: Gene 1 (The Loop) — what was found, what was proposed
CREATE TABLE IF NOT EXISTS meta_discovery_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    discovered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    raw_report TEXT NOT NULL,
    proposed_config TEXT,
    confirmed INTEGER DEFAULT 0,
    confirmed_by TEXT,
    confirmed_at TEXT,
    applied INTEGER DEFAULT 0
);

-- Runtime config: model IDs, thresholds, feature flags. Never hardcode what changes.
CREATE TABLE IF NOT EXISTS pib_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_by TEXT DEFAULT 'seed'
);

-- Migration log: up/down scripts with rollback. Supersedes bare version number.
CREATE TABLE IF NOT EXISTS meta_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,           -- e.g., "002_add_energy_states"
    up_sql TEXT NOT NULL,         -- Forward migration
    down_sql TEXT NOT NULL,       -- Rollback migration
    applied_at TEXT,
    rolled_back_at TEXT,
    checksum TEXT NOT NULL        -- SHA256 of up_sql to detect tampering
);

-- Members: every person in the household universe
CREATE TABLE IF NOT EXISTS common_members (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('parent','child','coparent','grandparent','nanny','babysitter','other')),
    is_household_member INTEGER NOT NULL DEFAULT 1,
    is_adult INTEGER NOT NULL DEFAULT 1,
    can_be_assigned_tasks INTEGER DEFAULT 0,
    can_receive_messages INTEGER DEFAULT 0,
    phone TEXT, email TEXT, imessage_handle TEXT,
    preferred_channel TEXT CHECK (preferred_channel IS NULL OR preferred_channel IN ('imessage','sms','email','phone')),
    -- Actor profile (Section 2)
    view_mode TEXT DEFAULT 'standard' CHECK (view_mode IN ('carousel','compressed','standard','child','entity')),
    digest_mode TEXT DEFAULT 'full' CHECK (digest_mode IN ('full','compressed','none')),
    -- ADHD-specific
    energy_markers TEXT DEFAULT '{}',
    medication_config TEXT DEFAULT '{}',
    velocity_cap INTEGER DEFAULT 20,
    -- Child-specific
    capabilities TEXT DEFAULT '{}',
    school TEXT, age INTEGER,
    date_of_birth TEXT CHECK (date_of_birth IS NULL OR date(date_of_birth) IS NOT NULL),
    expected_arrival TEXT CHECK (expected_arrival IS NULL OR date(expected_arrival) IS NOT NULL),
    schedule_profile TEXT DEFAULT '{}',
    household_duties TEXT DEFAULT '{}',
    notes TEXT, active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Source classifications: Gene 2 (The Vocabulary)
CREATE TABLE IF NOT EXISTS common_source_classifications (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_identifier TEXT NOT NULL,
    display_name TEXT,
    relevance TEXT NOT NULL CHECK (relevance IN (
        'blocks_member','blocks_household','blocks_assignee',
        'custody_state','asset_availability','awareness','awareness_external')),
    ownership TEXT NOT NULL CHECK (ownership IN ('member','shared','external')),
    privacy TEXT NOT NULL CHECK (privacy IN ('full','privileged','redacted')),
    authority TEXT NOT NULL CHECK (authority IN ('system_managed','human_managed','hybrid')),
    for_member_id TEXT REFERENCES common_members(id),
    discovered_at TEXT, proposed_at TEXT, confirmed_at TEXT, confirmed_by TEXT,
    active INTEGER DEFAULT 1,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Custody, Locations, Life Phases, Household Config
CREATE TABLE IF NOT EXISTS common_custody_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id TEXT NOT NULL REFERENCES common_members(id),
    schedule_type TEXT NOT NULL CHECK (schedule_type IN (
        'alternating_weeks','alternating_weekends_midweek',
        'every_other_weekend','primary_with_visitation','custom')),
    anchor_date TEXT NOT NULL CHECK (date(anchor_date) IS NOT NULL),
    anchor_parent TEXT NOT NULL REFERENCES common_members(id),
    other_parent TEXT NOT NULL REFERENCES common_members(id),
    transition_day TEXT, transition_time TEXT,
    transition_location_id TEXT REFERENCES common_locations(id),
    midweek_visit_enabled INTEGER DEFAULT 0,
    midweek_visit_day TEXT, midweek_visit_start TEXT, midweek_visit_end TEXT,
    midweek_visit_parent TEXT REFERENCES common_members(id),
    holiday_overrides TEXT DEFAULT '[]',
    active INTEGER DEFAULT 1,
    effective_from TEXT NOT NULL CHECK (date(effective_from) IS NOT NULL),
    effective_until TEXT CHECK (effective_until IS NULL OR date(effective_until) IS NOT NULL),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_custody_active ON common_custody_configs(child_id) WHERE active = 1;

CREATE TABLE IF NOT EXISTS common_locations (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, address TEXT,
    lat REAL, lng REAL, travel_times TEXT DEFAULT '{}', metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS common_life_phases (
    id TEXT PRIMARY KEY, name TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('active','pending','completed')),
    start_date TEXT CHECK (start_date IS NULL OR date(start_date) IS NOT NULL),
    end_date TEXT CHECK (end_date IS NULL OR date(end_date) IS NOT NULL),
    description TEXT, overrides TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS common_household_config (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    config TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- Audit, Idempotency, Dead Letter, Undo (from v4 — proven patterns)
CREATE TABLE IF NOT EXISTS common_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
    entity_id TEXT, old_values TEXT, new_values TEXT,
    actor TEXT NOT NULL DEFAULT 'system',
    source TEXT DEFAULT 'unknown', metadata TEXT DEFAULT '{}'
);
CREATE INDEX idx_audit_ts ON common_audit_log(ts);
CREATE INDEX idx_audit_entity ON common_audit_log(table_name, entity_id);

CREATE TABLE IF NOT EXISTS common_idempotency_keys (
    key_hash TEXT PRIMARY KEY, source TEXT NOT NULL, original_id TEXT,
    processed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    result_summary TEXT
);

CREATE TABLE IF NOT EXISTS common_id_sequences (
    prefix TEXT PRIMARY KEY,
    next_val INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS common_dead_letter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    failed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    operation TEXT NOT NULL, error_message TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0, max_retries INTEGER DEFAULT 3,
    next_retry_at TEXT, resolved INTEGER DEFAULT 0,
    resolved_at TEXT, resolved_by TEXT
);
CREATE INDEX idx_dead_letter_pending ON common_dead_letter(next_retry_at) WHERE resolved = 0;

CREATE TABLE IF NOT EXISTS common_undo_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id TEXT,
    operation TEXT NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
    table_name TEXT NOT NULL, entity_id TEXT NOT NULL,
    restore_data TEXT, actor TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    undone INTEGER DEFAULT 0, undone_at TEXT,
    expires_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now', '+24 hours'))
);
CREATE INDEX idx_undo_recent ON common_undo_log(created_at DESC)
    WHERE undone = 0 AND expires_at > strftime('%Y-%m-%dT%H:%M:%SZ','now');
```

#### ops_* Tables

```sql
CREATE TABLE IF NOT EXISTS ops_tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'inbox'
        CHECK (status IN ('inbox','next','in_progress','waiting_on','deferred','done','dismissed')),
    assignee TEXT NOT NULL REFERENCES common_members(id),
    domain TEXT NOT NULL DEFAULT 'tasks',
    item_type TEXT DEFAULT 'task'
        CHECK (item_type IN ('task','purchase','appointment','research','decision',
               'chore','maintenance','goal_milestone')),
    due_date TEXT CHECK (due_date IS NULL OR date(due_date) IS NOT NULL),
    scheduled_date TEXT CHECK (scheduled_date IS NULL OR date(scheduled_date) IS NOT NULL),
    scheduled_time TEXT,
    energy TEXT CHECK (energy IS NULL OR energy IN ('low','medium','high')),
    effort TEXT CHECK (effort IS NULL OR effort IN ('tiny','small','medium','large')),
    micro_script TEXT NOT NULL DEFAULT '',   -- Gene 7: EVERY task has this
    item_ref TEXT REFERENCES ops_items(id),
    recurring_ref TEXT REFERENCES ops_recurring(id),
    goal_ref TEXT REFERENCES ops_goals(id),
    life_event TEXT,
    requires TEXT,
    location_id TEXT REFERENCES common_locations(id),
    location_text TEXT,
    waiting_on TEXT, waiting_since TEXT,
    decision_options TEXT,
    decision_deadline TEXT CHECK (decision_deadline IS NULL OR date(decision_deadline) IS NOT NULL),
    decision_maker TEXT REFERENCES common_members(id),
    created_by TEXT NOT NULL DEFAULT 'system',
    source_system TEXT DEFAULT 'manual',
    confidence REAL DEFAULT 1.0,
    source_event_id TEXT,
    points INTEGER DEFAULT 1,               -- For scoreboard
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    completed_at TEXT, completed_by TEXT
);
CREATE INDEX idx_tasks_active ON ops_tasks(status, assignee) WHERE status NOT IN ('done','dismissed');
CREATE INDEX idx_tasks_due ON ops_tasks(due_date) WHERE due_date IS NOT NULL AND status NOT IN ('done','dismissed');
CREATE INDEX idx_tasks_overdue ON ops_tasks(due_date) WHERE due_date IS NOT NULL AND status NOT IN ('done','dismissed','deferred');

CREATE TABLE IF NOT EXISTS ops_goals (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, domain TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active','on_track','at_risk','behind','completed','abandoned')),
    owner TEXT REFERENCES common_members(id),
    target_date TEXT CHECK (target_date IS NULL OR date(target_date) IS NOT NULL),
    progress_metric TEXT, progress_current TEXT, progress_target TEXT,
    life_phase TEXT, notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS ops_items (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
    category TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','archived')),
    domain TEXT,
    phone TEXT, phone_alt TEXT, email TEXT, email_alt TEXT,
    imessage_handle TEXT, preferred_channel TEXT,
    contact_group TEXT, relationship_tier TEXT, our_relationship TEXT,
    desired_contact_freq TEXT,
    last_meaningful_contact TEXT CHECK (last_meaningful_contact IS NULL OR date(last_meaningful_contact) IS NOT NULL),
    last_hosted_us TEXT, last_we_hosted TEXT, hosting_balance INTEGER DEFAULT 0,
    gift_prefs TEXT, last_gift_given TEXT, last_gift_received TEXT,
    cos_can_contact INTEGER DEFAULT 0,
    outbound_identity TEXT DEFAULT 'ask', outbound_channel TEXT DEFAULT 'ask',
    reliability TEXT,
    brand TEXT, model TEXT, serial_number TEXT,
    purchase_date TEXT, warranty_exp TEXT,
    monthly_cost REAL, annual_cost REAL,
    location_id TEXT REFERENCES common_locations(id), address TEXT,
    metadata TEXT DEFAULT '{}', notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_items_type ON ops_items(type);
CREATE INDEX idx_items_email ON ops_items(email) WHERE email IS NOT NULL;
CREATE INDEX idx_items_phone ON ops_items(phone) WHERE phone IS NOT NULL;

CREATE TABLE IF NOT EXISTS ops_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blocked_task_id TEXT NOT NULL REFERENCES ops_tasks(id) ON DELETE CASCADE,
    blocking_task_id TEXT NOT NULL REFERENCES ops_tasks(id) ON DELETE CASCADE,
    dependency_type TEXT DEFAULT 'blocks' CHECK (dependency_type IN ('blocks','informs','requires')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(blocked_task_id, blocking_task_id)
);

CREATE TABLE IF NOT EXISTS ops_recurring (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, type TEXT NOT NULL,
    frequency TEXT NOT NULL, days TEXT,
    assignee TEXT NOT NULL REFERENCES common_members(id),
    for_member TEXT REFERENCES common_members(id),
    domain TEXT NOT NULL,
    next_due TEXT NOT NULL CHECK (date(next_due) IS NOT NULL),
    lead_days INTEGER DEFAULT 0, last_spawned TEXT,
    item_ref TEXT REFERENCES ops_items(id),
    goal_ref TEXT REFERENCES ops_goals(id),
    amount REAL, auto_pay INTEGER DEFAULT 0,
    effort TEXT DEFAULT 'small', energy TEXT DEFAULT 'low',
    micro_script_template TEXT NOT NULL DEFAULT '',
    points INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1, notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS ops_comms (
    id TEXT PRIMARY KEY, date TEXT NOT NULL,
    channel TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('inbound','outbound')),
    from_addr TEXT, to_addr TEXT, participants TEXT,
    member_id TEXT REFERENCES common_members(id),
    item_ref TEXT REFERENCES ops_items(id),
    task_ref TEXT REFERENCES ops_tasks(id),
    thread_id TEXT, subject TEXT,
    summary TEXT NOT NULL, body_snippet TEXT,
    needs_response INTEGER DEFAULT 0, response_urgency TEXT,
    suggested_action TEXT, auto_handled INTEGER DEFAULT 0,
    has_attachment INTEGER DEFAULT 0, sent_as TEXT,
    responded_at TEXT, outcome TEXT DEFAULT 'pending',
    followup_date TEXT, followup_action TEXT,
    created_by TEXT DEFAULT 'pib_agent',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_comms_date ON ops_comms(date);
CREATE INDEX idx_comms_pending ON ops_comms(needs_response) WHERE needs_response = 1;

CREATE TABLE IF NOT EXISTS ops_lists (
    id TEXT PRIMARY KEY, list_name TEXT NOT NULL, item_text TEXT NOT NULL,
    quantity REAL, unit TEXT, category TEXT,
    checked INTEGER DEFAULT 0,
    added_by TEXT REFERENCES common_members(id),
    added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    checked_at TEXT
);
CREATE INDEX idx_lists_active ON ops_lists(list_name, checked) WHERE checked = 0;

CREATE TABLE IF NOT EXISTS ops_gmail_whitelist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_type TEXT NOT NULL CHECK (match_type IN ('items_email','domain','explicit_address')),
    pattern TEXT NOT NULL, notes TEXT, active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS ops_gmail_triage_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    match_field TEXT DEFAULT 'subject' CHECK (match_field IN ('subject','from','body')),
    active INTEGER DEFAULT 1
);

-- Streaks (elastic, custody-aware)
CREATE TABLE IF NOT EXISTS ops_streaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL REFERENCES common_members(id),
    streak_type TEXT NOT NULL DEFAULT 'daily_completion',
    current_streak INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0,
    last_completion_date TEXT,
    grace_days_used INTEGER DEFAULT 0,
    max_grace_days INTEGER DEFAULT 1,
    custody_pause_enabled INTEGER DEFAULT 0,
    paused_since TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(member_id, streak_type)
);
```

#### cal_* Tables

```sql
CREATE TABLE IF NOT EXISTS cal_sources (
    id TEXT PRIMARY KEY,
    google_calendar_id TEXT NOT NULL UNIQUE,
    summary TEXT, purpose TEXT,
    for_member_ids TEXT DEFAULT '[]',
    classification_id TEXT REFERENCES common_source_classifications(id),
    sync_token TEXT, last_synced TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS cal_raw_events (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES cal_sources(id),
    google_event_id TEXT NOT NULL,
    summary TEXT, description TEXT, location TEXT,
    start_time TEXT, end_time TEXT, all_day INTEGER DEFAULT 0,
    recurrence_rule TEXT, attendees TEXT, status TEXT,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(source_id, google_event_id)
);
CREATE INDEX idx_raw_start ON cal_raw_events(start_time);

CREATE TABLE IF NOT EXISTS cal_classified_events (
    id TEXT PRIMARY KEY,
    raw_event_id TEXT REFERENCES cal_raw_events(id),
    source_type TEXT DEFAULT 'calendar', source_id TEXT,
    event_date TEXT NOT NULL CHECK (date(event_date) IS NOT NULL),
    start_time TEXT, end_time TEXT, all_day INTEGER DEFAULT 0,
    title TEXT,
    title_redacted TEXT,                    -- Privacy-safe: "Laura — Meeting"
    event_type TEXT, category TEXT,
    for_member_ids TEXT DEFAULT '[]',
    scheduling_impact TEXT CHECK (scheduling_impact IS NULL OR scheduling_impact IN
        ('HARD_BLOCK','SOFT_BLOCK','REQUIRES_TRANSPORT','FYI')),
    privacy TEXT DEFAULT 'full' CHECK (privacy IN ('full','privileged','redacted')),
    location_id TEXT REFERENCES common_locations(id),
    prep_minutes INTEGER DEFAULT 0, wind_down_minutes INTEGER DEFAULT 0,
    travel_minutes_to INTEGER, travel_minutes_from INTEGER,
    is_primary INTEGER DEFAULT 1, dedup_group_id TEXT,
    confidence TEXT DEFAULT 'high' CHECK (confidence IN ('high','medium','low')),
    needs_human_review INTEGER DEFAULT 0, classification_rule TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_class_date ON cal_classified_events(event_date);
CREATE INDEX idx_class_impact ON cal_classified_events(scheduling_impact, event_date);

CREATE TABLE IF NOT EXISTS cal_daily_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state_date TEXT NOT NULL CHECK (date(state_date) IS NOT NULL),
    version INTEGER NOT NULL DEFAULT 1,
    custody_states TEXT NOT NULL, member_states TEXT NOT NULL,
    transportation TEXT, coverage_status TEXT,
    activity_schedule TEXT, meal_logistics TEXT,
    complexity_score REAL NOT NULL,
    task_load TEXT, budget_snapshot TEXT, life_phase TEXT,
    computed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(state_date, version)
);
CREATE INDEX idx_daily_date ON cal_daily_states(state_date, version DESC);

CREATE TABLE IF NOT EXISTS cal_conflicts (
    id TEXT PRIMARY KEY,
    conflict_date TEXT NOT NULL CHECK (date(conflict_date) IS NOT NULL),
    conflict_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('critical','high','medium','low')),
    title TEXT, description TEXT,
    affected_member_ids TEXT, affected_event_ids TEXT,
    possible_resolutions TEXT,
    status TEXT DEFAULT 'unresolved' CHECK (status IN ('unresolved','resolved','auto_resolved','expired')),
    resolved_by TEXT, resolution_notes TEXT, resolution_task_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_conflicts_open ON cal_conflicts(status, conflict_date) WHERE status = 'unresolved';

CREATE TABLE IF NOT EXISTS cal_disambiguation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL, match_field TEXT NOT NULL,
    resolved_type TEXT NOT NULL, resolved_member_ids TEXT,
    resolved_impact TEXT,
    resolved_prep_minutes INTEGER DEFAULT 0,
    resolved_wind_down_minutes INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 100,
    created_by TEXT DEFAULT 'onboarding',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```

#### fin_* Tables

```sql
CREATE TABLE IF NOT EXISTS fin_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_date TEXT NOT NULL CHECK (date(transaction_date) IS NOT NULL),
    posted_date TEXT CHECK (posted_date IS NULL OR date(posted_date) IS NOT NULL),
    merchant_raw TEXT NOT NULL, merchant_normalized TEXT,
    amount REAL NOT NULL,
    category TEXT NOT NULL DEFAULT 'Uncategorized', subcategory TEXT,
    account TEXT,
    is_recurring INTEGER DEFAULT 0, is_excluded INTEGER DEFAULT 0, is_income INTEGER DEFAULT 0,
    item_ref TEXT, capital_expense_ref TEXT,
    categorization_rule TEXT, categorization_confidence REAL DEFAULT 1.0,
    needs_review INTEGER DEFAULT 0, notes TEXT, raw_data TEXT,
    import_source TEXT, import_batch TEXT, external_id TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_txn_date ON fin_transactions(transaction_date);
CREATE INDEX idx_txn_category ON fin_transactions(category);
CREATE INDEX idx_txn_review ON fin_transactions(needs_review) WHERE needs_review = 1;

CREATE TABLE IF NOT EXISTS fin_budget_config (
    category TEXT PRIMARY KEY, monthly_target REAL NOT NULL,
    is_fixed INTEGER DEFAULT 0, is_discretionary INTEGER DEFAULT 1,
    alert_threshold REAL DEFAULT 0.90, notes TEXT
);

CREATE TABLE IF NOT EXISTS fin_merchant_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    match_type TEXT DEFAULT 'contains' CHECK (match_type IN ('contains','exact','regex','starts_with')),
    category TEXT NOT NULL, subcategory TEXT, normalized_name TEXT,
    priority INTEGER DEFAULT 100, active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS fin_capital_expenses (
    id TEXT PRIMARY KEY, title TEXT NOT NULL,
    target_amount REAL NOT NULL, target_date TEXT,
    monthly_contribution REAL, accumulated REAL DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK (status IN ('active','funded','completed','cancelled')),
    domain TEXT, task_ref TEXT, notes TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS fin_recurring_bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, amount REAL NOT NULL, category TEXT NOT NULL,
    due_day INTEGER, frequency TEXT NOT NULL,
    auto_pay INTEGER DEFAULT 0, account TEXT, item_ref TEXT,
    next_due TEXT NOT NULL CHECK (date(next_due) IS NOT NULL),
    last_paid TEXT, active INTEGER DEFAULT 1, notes TEXT
);

CREATE TABLE IF NOT EXISTS fin_budget_snapshot (
    category TEXT PRIMARY KEY, monthly_target REAL,
    is_fixed INTEGER, is_discretionary INTEGER, alert_threshold REAL,
    spent_this_month REAL DEFAULT 0, remaining REAL DEFAULT 0,
    pct_used REAL DEFAULT 0, over_threshold INTEGER DEFAULT 0,
    computed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```

#### mem_* and pib_* Tables

```sql
CREATE TABLE IF NOT EXISTS mem_sessions (
    id TEXT PRIMARY KEY,
    member_id TEXT REFERENCES common_members(id),
    channel TEXT,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    last_message_at TEXT, message_count INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1, metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS mem_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES mem_sessions(id),
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool_use','tool_result')),
    content TEXT NOT NULL,
    tool_calls TEXT, tool_results TEXT, context_assembled TEXT,
    tokens_in INTEGER, tokens_out INTEGER, model TEXT,
    actions_taken TEXT DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_msg_session ON mem_messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS mem_session_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT REFERENCES mem_sessions(id),
    fact_type TEXT NOT NULL CHECK (fact_type IN ('decision','preference','correction','observation','commitment')),
    content TEXT NOT NULL, domain TEXT,
    member_id TEXT REFERENCES common_members(id),
    auto_promoted INTEGER DEFAULT 0,
    expires_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now', '+72 hours')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS mem_long_term (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL, content TEXT NOT NULL, domain TEXT,
    member_id TEXT REFERENCES common_members(id),
    item_ref TEXT REFERENCES ops_items(id),
    source_session TEXT, source_description TEXT,
    source TEXT DEFAULT 'user_stated' CHECK (source IN ('user_stated','inferred','observed','auto_promoted')),
    confidence REAL DEFAULT 1.0, is_permanent INTEGER DEFAULT 0,
    reinforcement_count INTEGER DEFAULT 1,
    last_reinforced_at TEXT, last_referenced_at TEXT,
    superseded_by INTEGER REFERENCES mem_long_term(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS mem_long_term_fts USING fts5(
    content, category, domain,
    content='mem_long_term', content_rowid='id'
);
```

**Memory Dedup + Negation Detection** (fix #7 from audit):

```python
NEGATION_PREFIXES = {"not ", "no longer ", "doesn't ", "don't ", "isn't ", "aren't ", "stopped ",
                      "quit ", "never ", "can't ", "won't ", "hasn't ", "haven't "}

def is_negation_of(new_content: str, existing_content: str) -> bool:
    """Detect when new fact negates existing. 'James doesn't like sushi' vs 'James likes sushi'."""
    new_lower, existing_lower = new_content.lower(), existing_content.lower()
    for prefix in NEGATION_PREFIXES:
        if new_lower.startswith(prefix) and existing_lower in new_lower[len(prefix):]:
            return True
        if existing_lower.startswith(prefix) and new_lower in existing_lower[len(prefix):]:
            return True
    # Also check: same subject, opposite predicate
    new_words = set(new_lower.split())
    existing_words = set(existing_lower.split())
    overlap = len(new_words & existing_words) / max(len(new_words | existing_words), 1)
    # High word overlap + presence of negation word = likely contradiction
    if overlap > 0.5 and (new_words - existing_words) & {"not","no","never","doesn't","don't","stopped","quit"}:
        return True
    return False

async def save_memory_deduped(db, content: str, category: str, domain: str, member_id: str, source: str):
    """Save memory with dedup: reinforce if similar, supersede if contradicted, insert if new."""
    # Search existing memories in same category/domain
    existing = await db.execute_fetchall(
        "SELECT id, content, reinforcement_count FROM mem_long_term "
        "WHERE category = ? AND (domain = ? OR domain IS NULL) AND superseded_by IS NULL",
        [category, domain])
    
    for row in existing:
        words_new = set(content.lower().split())
        words_existing = set(row["content"].lower().split())
        overlap = len(words_new & words_existing) / max(len(words_new | words_existing), 1)
        
        if overlap > 0.60:
            if is_negation_of(content, row["content"]):
                # Contradiction: supersede old with new
                new_id = await next_id(db, "mem")
                await db.execute(
                    "INSERT INTO mem_long_term (id, content, category, domain, member_id, source) "
                    "VALUES (?,?,?,?,?,?)", [new_id, content, category, domain, member_id, source])
                await db.execute(
                    "UPDATE mem_long_term SET superseded_by = ? WHERE id = ?", [new_id, row["id"]])
                return {"action": "superseded", "old_id": row["id"], "new_id": new_id}
            else:
                # Duplicate: reinforce existing
                await db.execute(
                    "UPDATE mem_long_term SET reinforcement_count = reinforcement_count + 1, "
                    "last_reinforced_at = datetime('now') WHERE id = ?", [row["id"]])
                return {"action": "reinforced", "id": row["id"], "count": row["reinforcement_count"] + 1}
    
    # New fact
    new_id = await next_id(db, "mem")
    await db.execute(
        "INSERT INTO mem_long_term (id, content, category, domain, member_id, source) "
        "VALUES (?,?,?,?,?,?)", [new_id, content, category, domain, member_id, source])
    return {"action": "inserted", "id": new_id}

# ─── AUTO-PROMOTION: Session Facts → Long-Term Memory ───
# Runs every 6 hours. Promotes session facts that match promotion patterns.

PROMOTION_PATTERNS = {
    # fact_type → (category in long-term, minimum confidence)
    "decision":    ("decisions",    0.9),   # "We decided to use contractor X"
    "preference":  ("preferences",  0.8),   # "Laura prefers text over email for reminders"
    "correction":  ("corrections",  1.0),   # "Actually Charlie's school starts at 8:15, not 8:00"
    "commitment":  ("commitments",  0.9),   # "James promised to call the roofer by Friday"
    "observation": ("observations", 0.7),   # "James tends to crash around 2pm on Mondays"
}

# Keywords that boost confidence (exact word in content)
CONFIDENCE_BOOSTERS = {
    "decision": {"decided", "agreed", "choosing", "going with", "final", "settled"},
    "commitment": {"promise", "committed", "will do", "by friday", "by monday", "deadline"},
    "correction": {"actually", "wrong", "not right", "correction", "update", "changed"},
}

async def auto_promote_session_facts(db):
    """Promote high-signal session facts to long-term memory. Runs every 6 hours."""
    # Get un-promoted, un-expired session facts
    facts = await db.execute_fetchall(
        "SELECT * FROM mem_session_facts WHERE auto_promoted = 0 "
        "AND (expires_at IS NULL OR expires_at > datetime('now')) "
        "ORDER BY created_at")
    
    promoted = 0
    for fact in facts:
        pattern = PROMOTION_PATTERNS.get(fact["fact_type"])
        if not pattern:
            continue
        
        category, min_confidence = pattern
        
        # Compute confidence: base 0.7, boosted by keyword presence
        confidence = 0.7
        boosters = CONFIDENCE_BOOSTERS.get(fact["fact_type"], set())
        content_lower = fact["content"].lower()
        for keyword in boosters:
            if keyword in content_lower:
                confidence = min(confidence + 0.1, 1.0)
        
        # Reinforcement boost: if same fact appears in 2+ sessions, higher confidence
        similar_count = await db.execute_fetchone(
            "SELECT COUNT(*) as c FROM mem_session_facts "
            "WHERE fact_type = ? AND content LIKE ? AND id != ?",
            [fact["fact_type"], f"%{fact['content'][:30]}%", fact["id"]])
        if similar_count["c"] >= 1:
            confidence = min(confidence + 0.15, 1.0)
        
        if confidence >= min_confidence:
            result = await save_memory_deduped(
                db, fact["content"], category, fact["domain"],
                fact["member_id"], "auto_promoted")
            await db.execute(
                "UPDATE mem_session_facts SET auto_promoted = 1 WHERE id = ?", [fact["id"]])
            promoted += 1
            log.info(f"Auto-promoted session fact {fact['id']}: {result['action']}", 
                     extra={"confidence": confidence, "category": category})
    
    return {"promoted": promoted}
```

```sql
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    digest_type TEXT NOT NULL,
    for_member TEXT NOT NULL REFERENCES common_members(id),
    digest_date TEXT NOT NULL CHECK (date(digest_date) IS NOT NULL),
    structured_data TEXT NOT NULL, composed_text TEXT, composed_at TEXT,
    delivered INTEGER DEFAULT 0, delivered_at TEXT, delivered_via TEXT,
    UNIQUE(digest_type, for_member, digest_date)
);

CREATE TABLE IF NOT EXISTS mem_approval_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL, operation_payload TEXT NOT NULL,
    requested_by TEXT NOT NULL, requested_in_session TEXT,
    requested_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','expired')),
    decided_by TEXT, decided_at TEXT, decision_notes TEXT,
    auto_expire_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now', '+24 hours')),
    expiry_notification_sent INTEGER DEFAULT 0
);
CREATE INDEX idx_approval_pending ON mem_approval_queue(status) WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS mem_cos_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_date TEXT NOT NULL DEFAULT (date('now')),
    activity_type TEXT NOT NULL, description TEXT NOT NULL,
    entity_table TEXT, entity_id TEXT,
    actor TEXT DEFAULT 'llm_pib', confidence REAL DEFAULT 1.0,
    reviewed INTEGER DEFAULT 0, reviewed_by TEXT, reviewed_at TEXT,
    correction_applied TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX idx_activity_date ON mem_cos_activity(activity_date) WHERE reviewed = 0;

-- ═══════════════════════════════════════════════════════
-- PIB: Behavioral mechanics (NEW in v5)
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS pib_reward_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL REFERENCES common_members(id),
    task_id TEXT REFERENCES ops_tasks(id),
    reward_tier TEXT NOT NULL CHECK (reward_tier IN ('simple','warm','delight','jackpot')),
    reward_text TEXT NOT NULL,
    delivered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS pib_energy_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT NOT NULL REFERENCES common_members(id),
    state_date TEXT NOT NULL DEFAULT (date('now')),
    medication_taken INTEGER DEFAULT 0,
    medication_taken_at TEXT,
    medication_peak_start TEXT,
    medication_peak_end TEXT,
    medication_crash_start TEXT,
    sleep_quality TEXT CHECK (sleep_quality IS NULL OR sleep_quality IN ('great','okay','rough')),
    sleep_quality_reported_at TEXT,
    focus_mode_active INTEGER DEFAULT 0,
    focus_mode_since TEXT,
    completions_today INTEGER DEFAULT 0,
    velocity_cap_hit INTEGER DEFAULT 0,
    last_completion_at TEXT,
    last_interaction_at TEXT,
    current_energy_level TEXT DEFAULT 'medium' CHECK (current_energy_level IN ('low','medium','high')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(member_id, state_date)
);

CREATE TABLE IF NOT EXISTS pib_coach_protocols (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    behavior TEXT NOT NULL,
    examples TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- FTS indexes
CREATE VIRTUAL TABLE IF NOT EXISTS ops_tasks_fts USING fts5(
    title, notes, domain, content='ops_tasks', content_rowid='rowid'
);
CREATE VIRTUAL TABLE IF NOT EXISTS ops_items_fts USING fts5(
    name, category, notes, our_relationship, content='ops_items', content_rowid='rowid'
);
```

---

## 4. whatNow() — THE ONE FUNCTION

The single query the entire system exists to answer. Deterministic. No LLM. No side effects. Same inputs → same output. Every surface calls this: scoreboard, carousel, morning briefing, console, proactive nudge.

```python
@dataclass
class WhatNowResult:
    the_one_task: Task | None       # THE task. One. Not a list.
    one_more_teaser: Task | None    # Zeigarnik hook: "One more? Only 3 minutes."
    blocked_until: str | None       # If currently in a calendar block
    next_event: dict | None         # Next event with prep time
    streak: dict                    # Current streak state
    velocity: dict                  # Completions today, cap status
    energy_state: dict              # Current energy level + medication phase
    context: str                    # One-line summary: "3 overdue, 12-day streak, meds peaked"

def what_now(
    member_id: str,
    db_snapshot: DBSnapshot,        # Pre-fetched: tasks, daily_state, energy, streaks
    now: datetime = None,
) -> WhatNowResult:
    """
    Layer 1. Always works. No LLM. No API calls. Pure function on local data.
    """
    now = now or datetime.now()
    today = now.date().isoformat()
    
    # ── 1. CALENDAR FILTER ──
    # Am I in a HARD_BLOCK right now?
    current_block = find_current_block(db_snapshot.daily_state, now)
    if current_block:
        return WhatNowResult(
            the_one_task=None,
            blocked_until=current_block["end_time"],
            next_event=current_block,
            context=f"In: {current_block['title']} until {format_time(current_block['end_time'])}",
            **_fill_meta(db_snapshot, member_id)
        )
    
    # ── 2. VELOCITY CAP CHECK ──
    energy = db_snapshot.energy_state
    member = db_snapshot.members[member_id]
    if energy.completions_today >= member.get("velocity_cap", 20):
        return WhatNowResult(
            the_one_task=_break_task(energy.completions_today),
            context=f"🎉 {energy.completions_today} done today! Take a break — you've earned it.",
            **_fill_meta(db_snapshot, member_id)
        )
    
    # ── 3. ENERGY MATCHING ──
    energy_level = compute_energy_level(energy, member, now)
    # During medication crash or rough sleep: only low/tiny tasks
    # During medication peak: prefer medium/high tasks
    # Otherwise: no filter
    
    energy_filter = _energy_filter(energy_level)
    
    # ── 4. TASK SELECTION (deterministic sort) ──
    candidates = [t for t in db_snapshot.tasks
                  if t["assignee"] == member_id
                  and t["status"] in ("next", "in_progress", "inbox")
                  and not is_blocked_by_dependency(t, db_snapshot.tasks)
                  and not is_blocked_by_custody(t, db_snapshot.daily_state, member_id)]
    
    if energy_filter:
        filtered = [t for t in candidates if energy_filter(t)]
        if filtered:
            candidates = filtered
        # If filter removes ALL candidates, show unfiltered with energy note
    
    # Sort: overdue → due_today → in_progress → next → inbox → smallest first
    candidates.sort(key=lambda t: (
        0 if (t.get("due_date") and t["due_date"] < today) else        # Overdue first
        1 if (t.get("due_date") and t["due_date"] == today) else       # Due today
        2 if t["status"] == "in_progress" else                          # Already started
        3 if t["status"] == "next" else                                 # Queued
        4,                                                              # Inbox
        EFFORT_ORDER.get(t.get("effort", "small"), 2),                 # Smallest first
        t.get("due_date") or "9999-12-31",                             # Earliest due
        t["created_at"],                                                # Oldest created
    ))
    
    the_one = candidates[0] if candidates else None
    one_more = candidates[1] if len(candidates) > 1 else None
    
    # ── 5. NEXT EVENT ──
    next_event = find_next_event(db_snapshot.daily_state, now)
    time_until = None
    if next_event:
        prep = next_event.get("prep_minutes", 0) + next_event.get("travel_minutes_to", 0)
        event_start = parse_time(next_event["start_time"])
        time_until = (event_start - now).total_seconds() / 60 - prep
    
    # ── 6. CONTEXT STRING ──
    parts = []
    overdue_count = sum(1 for t in candidates if t.get("due_date") and t["due_date"] < today)
    if overdue_count:
        parts.append(f"{overdue_count} overdue")
    streak = db_snapshot.streaks.get(member_id, {})
    if streak.get("current_streak", 0) > 0:
        parts.append(f"🔥 {streak['current_streak']}-day streak")
    if energy.medication_taken:
        phase = _medication_phase(energy, now)
        parts.append(f"meds: {phase}")
    if energy.sleep_quality == "rough":
        parts.append("rough sleep — easy day")
    if time_until and time_until < 60:
        parts.append(f"next event in {int(time_until)}min")
    
    return WhatNowResult(
        the_one_task=the_one,
        one_more_teaser=one_more,
        blocked_until=None,
        next_event=next_event,
        streak=streak,
        velocity={"today": energy.completions_today, "cap": member.get("velocity_cap", 20)},
        energy_state={"level": energy_level, "medication_phase": _medication_phase(energy, now),
                      "sleep": energy.sleep_quality},
        context=" · ".join(parts) if parts else "Clear day ahead"
    )


EFFORT_ORDER = {"tiny": 0, "small": 1, "medium": 2, "large": 3}

def compute_energy_level(energy: dict, member: dict, now: datetime) -> str:
    """Deterministic energy computation from medication + sleep + time of day."""
    # Rough sleep → cap at low
    if energy.get("sleep_quality") == "rough":
        return "low"
    
    # Medication phase
    if energy.get("medication_taken"):
        peak_start = parse_time(energy.get("medication_peak_start"))
        peak_end = parse_time(energy.get("medication_peak_end"))
        crash_start = parse_time(energy.get("medication_crash_start"))
        
        if peak_start and peak_end and peak_start <= now <= peak_end:
            return "high"
        if crash_start and now >= crash_start:
            return "low"
    
    # Time-of-day defaults from member.energy_markers
    markers = json.loads(member.get("energy_markers", "{}"))
    hour = now.hour
    for peak_range in markers.get("peak_hours", []):
        start, end = [int(h) for h in peak_range.split("-")]
        if start <= hour < end:
            return "high"
    for crash_range in markers.get("crash_hours", []):
        start, end = [int(h) for h in crash_range.split("-")]
        if start <= hour < end:
            return "low"
    
    return "medium"

def _energy_filter(level: str):
    """Returns a filter function based on energy level."""
    if level == "low":
        return lambda t: t.get("effort") in ("tiny", "small") and t.get("energy") in ("low", None)
    if level == "high":
        return lambda t: t.get("energy") in ("medium", "high", None)
    return None  # Medium: no filter

def _break_task(completions: int) -> dict:
    """Generate a break suggestion when velocity cap is hit."""
    return {
        "id": "break",
        "title": "Take a break",
        "status": "next",
        "micro_script": "Stand up → walk to kitchen → glass of water → 10 minutes off screens",
        "energy": "low",
        "effort": "tiny",
        "notes": f"You've done {completions} things today. That's genuinely impressive. Rest."
    }
```

### 4.1 Custody Date Math (DST-Aware)

Pure function. 20+ test cases required including DST transitions. **CRITICAL: Use `zoneinfo` for timezone-aware arithmetic. Naive date subtraction breaks on DST boundaries.**

```python
from zoneinfo import ZoneInfo
from datetime import date, datetime, timedelta

HOUSEHOLD_TZ = ZoneInfo("America/New_York")  # Atlanta

def who_has_child(
    query_date: date,
    config: dict,  # From common_custody_configs
) -> str:
    """Deterministic custody state. No LLM. Returns parent member_id.
    
    CRITICAL: DST transitions can make a 'day' 23 or 25 hours.
    Always compute in calendar days, never hours.
    """
    anchor = date.fromisoformat(config["anchor_date"])
    anchor_parent = config["anchor_parent"]
    other_parent = config["other_parent"]
    
    # Holiday overrides take priority
    overrides = json.loads(config.get("holiday_overrides", "[]"))
    for override in overrides:
        if override["start"] <= query_date.isoformat() <= override["end"]:
            return override["parent"]
    
    # Calendar-day difference (immune to DST)
    day_diff = (query_date - anchor).days  # Always integer, DST-safe
    
    schedule_type = config["schedule_type"]
    if schedule_type == "alternating_weeks":
        week_num = day_diff // 7
        return anchor_parent if week_num % 2 == 0 else other_parent
    
    elif schedule_type == "alternating_weekends_midweek":
        # Complex: alternating weekends + midweek visit
        week_num = day_diff // 7
        day_of_week = query_date.weekday()  # 0=Mon
        
        is_anchor_weekend = (week_num % 2 == 0)
        if day_of_week >= 5:  # Weekend
            return anchor_parent if is_anchor_weekend else other_parent
        
        # Midweek visit check
        if config.get("midweek_visit_enabled"):
            visit_day = config.get("midweek_visit_day")
            if visit_day and query_date.strftime("%A").lower() == visit_day.lower():
                return config.get("midweek_visit_parent", other_parent)
        
        # Weekday default: anchor parent
        return anchor_parent
    
    elif schedule_type == "every_other_weekend":
        week_num = day_diff // 7
        day_of_week = query_date.weekday()
        if day_of_week >= 5 and week_num % 2 == 1:
            return other_parent
        return anchor_parent
    
    elif schedule_type == "primary_with_visitation":
        # Primary parent has child except during defined visitation
        # Visitation days defined in schedule_profile
        return anchor_parent  # Override with visitation config
    
    return anchor_parent  # Default fallback

# DST TEST CASES (must all pass):
# 2026-03-08 (day before spring forward) → same result as naive
# 2026-03-09 (spring forward: 23-hour day) → correct parent
# 2026-11-01 (day before fall back) → same result as naive  
# 2026-11-02 (fall back: 25-hour day) → correct parent
# Transition at midnight vs 6pm → different parents depending on transition_time
```

---

## 5. BEHAVIORAL MECHANICS — DARK PROSTHETICS

These are not flavor. These are the core competitive differentiation. They hack the dopaminergic circuit to make task completion addictive instead of effortful.

### 5.1 Variable-Ratio Reinforcement

After every task completion, select a reward tier by probability:

```python
import random

REWARD_SCHEDULE = [
    (0.60, "simple",  ["Done ✓", "✓", "Got it ✓", "Checked off ✓"]),
    (0.25, "warm",    [
        "Nice, that's {streak} in a row today!",
        "Solid. What took you longest was starting — and you did.",
        "That's {today_count} today. Momentum is real.",
        "Another one bites the dust. 🎵",
    ]),
    (0.10, "delight", [
        "Fun fact: the average person takes 23 minutes to refocus after a distraction. You just proved you're not average.",
        "🏆 You just passed Laura's weekly count. Don't tell her I said that.",
        "Streak preserved. Your future self thanks you.",
        "That task had been sitting there {days_old} days. It's finally free. 🦋",
    ]),
    (0.05, "jackpot", [
        "🎉 JACKPOT! You cleared your entire overdue queue. This hasn't happened in {days_since_clear} days!",
        "🎰 Holy smokes — {today_count} tasks in one session. That's a personal record.",
        "💎 You've been on fire this week. {week_count} completed. The household is literally running because of you.",
    ]),
]
# 🆕 UPDATED from 70/20/8/2 → 60/25/10/5
# Rationale: ADHD brains need more frequent dopamine hits. 5% jackpot means
# roughly one per 20 completions (within a single good day) vs one per 50
# (across multiple days). The warm tier at 25% means nearly 1-in-4 completions
# feels genuinely good. This was validated in the console prototype.

def select_reward(member_id: str, task: dict, stats: dict) -> tuple[str, str]:
    """Select reward tier and message. Returns (tier, message)."""
    roll = random.random()
    cumulative = 0
    for prob, tier, templates in REWARD_SCHEDULE:
        cumulative += prob
        if roll <= cumulative:
            template = random.choice(templates)
            message = template.format(
                streak=stats.get("current_streak", 0),
                today_count=stats.get("completions_today", 0),
                week_count=stats.get("week_completions", 0),
                days_old=(date.today() - parse_date(task.get("created_at", ""))).days if task.get("created_at") else 0,
                days_since_clear=stats.get("days_since_all_clear", "?"),
            )
            return tier, message
    return "simple", "Done ✓"

async def complete_task_with_reward(db, task_id: str, member_id: str, actor: str) -> dict:
    """Complete a task, update streak, select reward, log everything."""
    # 1. Complete the task
    await transition_task(db, task_id, "done", {}, actor)
    
    # 2. Update velocity
    await db.execute(
        "UPDATE pib_energy_states SET completions_today = completions_today + 1, "
        "last_completion_at = datetime('now') WHERE member_id = ? AND state_date = date('now')",
        [member_id])
    
    # 3. Update streak
    streak = await update_streak(db, member_id, date.today())
    
    # 4. Select reward
    stats = await get_completion_stats(db, member_id)
    tier, message = select_reward(member_id, await get_task(db, task_id), stats)
    
    # 5. Log reward
    await db.execute(
        "INSERT INTO pib_reward_log (member_id, task_id, reward_tier, reward_text) VALUES (?,?,?,?)",
        [member_id, task_id, tier, message])
    
    # 6. Get the Zeigarnik hook
    wn = what_now(member_id, await load_snapshot(db, member_id))
    one_more = None
    if wn.one_more_teaser:
        effort_text = {"tiny": "2 min", "small": "5 min", "medium": "15 min", "large": "30+ min"}
        one_more = f"One more? \"{wn.one_more_teaser['title']}\" — only {effort_text.get(wn.one_more_teaser.get('effort','small'), '5 min')}."
    
    return {"reward_tier": tier, "reward_message": message, "one_more": one_more, "streak": streak}
```

### 5.2 Elastic Streaks

```python
async def update_streak(db, member_id: str, completion_date: date) -> dict:
    streak = await db.execute_fetchone(
        "SELECT * FROM ops_streaks WHERE member_id = ? AND streak_type = 'daily_completion'",
        [member_id])
    
    if not streak:
        await db.execute(
            "INSERT INTO ops_streaks (member_id, streak_type, current_streak, best_streak, last_completion_date) "
            "VALUES (?, 'daily_completion', 1, 1, ?)", [member_id, completion_date.isoformat()])
        return {"current": 1, "best": 1, "event": "started"}
    
    last_date = parse_date(streak["last_completion_date"])
    gap = (completion_date - last_date).days
    
    # Check custody pause
    if streak["custody_pause_enabled"]:
        gap = gap - count_custody_away_days(db, member_id, last_date, completion_date)
    
    if gap <= 0:
        return {"current": streak["current_streak"], "best": streak["best_streak"], "event": "same_day"}
    elif gap == 1:
        # Next day: extend streak
        new_streak = streak["current_streak"] + 1
        new_best = max(new_streak, streak["best_streak"])
        await db.execute(
            "UPDATE ops_streaks SET current_streak=?, best_streak=?, last_completion_date=?, "
            "grace_days_used=0, updated_at=datetime('now') WHERE id=?",
            [new_streak, new_best, completion_date.isoformat(), streak["id"]])
        event = "extended"
        if new_streak == new_best and new_streak > 3:
            event = "new_record"
        return {"current": new_streak, "best": new_best, "event": event}
    elif gap == 2 and streak["grace_days_used"] < streak["max_grace_days"]:
        # Grace period: 1 miss doesn't break
        new_streak = streak["current_streak"] + 1
        await db.execute(
            "UPDATE ops_streaks SET current_streak=?, last_completion_date=?, "
            "grace_days_used=grace_days_used+1, updated_at=datetime('now') WHERE id=?",
            [new_streak, completion_date.isoformat(), streak["id"]])
        return {"current": new_streak, "best": streak["best_streak"], "event": "grace_used"}
    else:
        # Streak broken. Reset.
        await db.execute(
            "UPDATE ops_streaks SET current_streak=1, last_completion_date=?, "
            "grace_days_used=0, updated_at=datetime('now') WHERE id=?",
            [completion_date.isoformat(), streak["id"]])
        event = "reset"
        if streak["current_streak"] >= 3:
            event = "reset_was_long"  # Trigger "welcome back" at 3-day recovery
        return {"current": 1, "best": streak["best_streak"], "event": event}
```

### 5.3 Friction Asymmetry

Implemented in the task state machine guards:

```python
TRANSITIONS = {
    "inbox":       ["next", "in_progress", "waiting_on", "deferred", "dismissed"],
    "next":        ["in_progress", "done", "waiting_on", "deferred", "dismissed"],
    "in_progress": ["done", "waiting_on", "deferred"],
    "waiting_on":  ["in_progress", "next", "done"],
    "deferred":    ["next", "inbox"],
    "done":        [],
    "dismissed":   [],
}

GUARDS = {
    "done":        lambda t, u: True,                                    # EASY: one tap
    "dismissed":   lambda t, u: bool(u.get("notes")) and len(u["notes"]) >= 10,  # HARD: why?
    "deferred":    lambda t, u: bool(u.get("scheduled_date")),           # MEDIUM: when instead?
    "waiting_on":  lambda t, u: bool(u.get("waiting_on")),               # MEDIUM: who?
}
```

The path of least resistance IS the productive path.

### 5.4 Coach Protocols

Stored in `pib_coach_protocols` and loaded into the system prompt. Testable: "Given this context, does the response match protocol X?"

```python
COACH_PROTOCOLS = [
    {
        "id": "protocol-never-guilt",
        "name": "Never Guilt",
        "trigger_condition": "Any reference to overdue tasks, missed deadlines, or incomplete work",
        "behavior": "Lead with the micro-script, not the overdue count. Never use words: should have, forgot, missed, behind, falling. Frame as: 'This is still here. Here's the tiniest step.'",
        "examples": json.dumps({
            "good": "Call the dentist is still on your plate. 📱 Open phone → search 'Peachtree Dental' → tap call. That's it.",
            "bad": "You have 3 overdue tasks. You should have called the dentist last week."
        })
    },
    {
        "id": "protocol-always-celebrate",
        "name": "Always Celebrate",
        "trigger_condition": "Any task completion, any status change to done",
        "behavior": "Always acknowledge completions with warmth. Never skip the celebration, even if immediately presenting the next task. Use variable-ratio rewards (see Section 5.1).",
    },
    {
        "id": "protocol-energy-match",
        "name": "Energy-Aware Presentation",
        "trigger_condition": "Any task presentation during low energy period",
        "behavior": "During low energy (crash hours, rough sleep, post-velocity-cap): present only tiny/small tasks. Use softer language. Explicitly validate rest. 'Your brain earned a break. If you want one tiny thing: [micro_script].'",
    },
    {
        "id": "protocol-no-compare",
        "name": "Never Compare Family Members",
        "trigger_condition": "Any reference to multiple family members' productivity",
        "behavior": "Never compare James and Laura's task counts, speeds, or consistency. The scoreboard shows individual metrics. PIB never narrates the comparison.",
    },
    {
        "id": "protocol-momentum-check",
        "name": "Momentum Check After 3+",
        "trigger_condition": "3 or more task completions in the current session",
        "behavior": "After 3+ completions: 'That's momentum. Want to ride it or bank it?' Give the choice to continue or stop. Never assume they want more.",
    },
    {
        "id": "protocol-scaffold-independence",
        "name": "Scaffold Independence",
        "trigger_condition": "Morning briefing, weekly review",
        "behavior": "Periodically reinforce fallback strategies: 'Your three things today are X, Y, Z. Even without me, you know these three.' PIB should build independence, not dependency.",
    },
    {
        "id": "protocol-paralysis-break",
        "name": "Paralysis Detection",
        "trigger_condition": "2+ hours of inactivity during peak hours with no calendar block",
        "behavior": "Gentle check-in via iMessage. Never guilt. Offer the tiniest possible restart: 'Hey, still on [last task]? Here's one tiny thing if you need a restart: [micro_script of easiest available task].'",
    },
    {
        "id": "protocol-post-meeting-capture",
        "name": "Post-Meeting Capture",
        "trigger_condition": "Calendar event with 2+ attendees ended within last 15 minutes",
        "behavior": "Prompt: 'Just finished [Event Title]. Any action items to capture?' Route response through ingestion pipeline.",
    },
]
```

### 5.5 Scoreboard (Kitchen TV)

Standalone page at `/scoreboard`. Dark background, large text, readable from 10 feet. Auto-refresh every 60 seconds.

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│    JAMES     │  │    LAURA     │  │   CHARLIE    │
│  🔥 12-day   │  │  🔥 8-day    │  │  ⭐ 5-day    │
│    streak    │  │    streak    │  │    streak    │
│  ✅ 4 done   │  │  ✅ 2 done   │  │  ⭐ 2 done   │
│    today     │  │    today     │  │    today     │
│  📋 Next:    │  │  📋 Next:    │  │  📋 Next:    │
│  Call plumber│  │  Review list │  │  Empty       │
│              │  │              │  │  dishwasher  │
│  🏆 Week: 28 │  │  🏆 Week: 18 │  │  ⭐ Week: 12 │
│     840pts   │  │     540pts   │  │     360pts   │
└──────────────┘  └──────────────┘  └──────────────┘
🐕 Captain: Walked ✓ · Fed ✓ · Next walk: 6pm
🏠 Family Total: 58 this week (target: 50) — ON FIRE 🔥
```

Implementation: `/scoreboard` endpoint returns HTML page. JavaScript fetches `/api/scoreboard-data` every 60 seconds. Each member's card calls whatNow() for their one task. Points are sum of task.points for completed tasks this week.

> **🆕 CONSOLE UPDATE — Neuroprosthetic Layers Panel**

Below the family cards, the scoreboard displays a **Neuroprosthetic Layers** panel showing real-time cognitive support scores (0–100) for 7 executive function domains:

```
┌─ NEUROPROSTHETIC LAYERS ────────────────────┐
│                                              │
│  Overall:  28 / 100                          │
│                                              │
│  Memory        ██████████░░░░░░░░░░  58      │
│  Time          █████░░░░░░░░░░░░░░░  26      │
│  Initiation    █████░░░░░░░░░░░░░░░  26      │
│  Attention     ██░░░░░░░░░░░░░░░░░░   9      │
│  Transition    ███░░░░░░░░░░░░░░░░░  17      │
│  Emotional     ████░░░░░░░░░░░░░░░░  21      │
│  Proactive     ████████░░░░░░░░░░░░  39      │
│                                              │
└──────────────────────────────────────────────┘
```

**Score computation** (from system activity data, no LLM):

| Domain | Inputs |
|--------|--------|
| Memory | Long-term memory count, recall frequency, fact reinforcement rate |
| Time | Calendar adherence rate, on-time task completion, morning digest delivery |
| Initiation | Micro-script usage, median time-to-start after notification, endowed progress engagement |
| Attention | Active session duration, task switching frequency, focus mode usage |
| Transition | Skip-to-done ratio, cross-domain task flow, context switch smoothness |
| Emotional Regulation | Coach protocol trigger rate, streak maintenance, reward tier distribution |
| Proactive | Proactive nudge acceptance rate, paralysis detection interventions, CRM gap coverage |

Color coding: green (>40), yellow (20–40), red (<20). Overall score is weighted average. This makes the Chief-of-Staff legible — James can see which cognitive functions are being most supported and where gaps exist. Scores update with each `/api/scoreboard-data` refresh.

---

## 5.6 Console Design System 🆕

> *Absorbed from console prototype. The design system IS the prosthetic's bedside manner.*

**Fonts:**

| Role | Font | Rationale |
|------|------|-----------|
| Headings | Fraunces (serif) | Warmth, approachability. Serifs feel human, not clinical. |
| Body | DM Sans (sans-serif) | Clean readability at all sizes |
| Data/Code | JetBrains Mono (monospace) | Precision for numbers, timestamps, scores |

**Color Palette:**

```css
/* Core */
--bg:    #FFFBF5;  /* Warm cream — not clinical white. Reduces anxiety. */
--pink:  #E8A0BF;  /* Primary accent, active states, attention */
--lav:   #B8A9C9;  /* Secondary accent, household domain */
--teal:  #8EC5C0;  /* Health domain, warm tier rewards */
--grn:   #7CB98F;  /* Success, done states, system healthy */
--warn:  #E8C07D;  /* Finance domain, budget alerts, skipped */
--err:   #D4756B;  /* Errors, overdue, urgent */
--info:  #89B4D4;  /* Work domain, informational */
```

**Domain Color Map:**

| Domain | Color | CSS Variable |
|--------|-------|-------------|
| household | Lavender | `--lav` |
| health | Teal | `--teal` |
| finance | Warm yellow | `--warn` |
| family | Pink | `--pink` |
| work | Blue | `--info` |
| admin | Green | `--grn` |

**Cards:** 12px border-radius, subtle shadows (`0 1px 3px rgba(0,0,0,0.06)`), hover border transitions (`transition: all .15s`).

**Animations:**

| Name | Trigger | Effect |
|------|---------|--------|
| `fadeUp` | Page enter | Opacity 0→1, translateY 12px→0, 0.4s ease-out |
| `slideIn` | Card transitions | Horizontal slide with fade, 0.25s ease-out |
| `confetti` | Jackpot reward | Colored dots fly upward with rotation, 1s staggered |
| `glow` | Active task card | Pink box-shadow pulses 0→8px→0, 3s infinite |
| `pulse` | System health indicator | Scale 1→1.15→1, 2s infinite |

**Rationale:** Warm palette reduces anxiety. Soft serifs feel approachable rather than demanding. The confetti animation makes jackpot rewards visceral. The glow directs attention without startling. Every design choice serves the prosthetic — this is not decoration, it's cognitive scaffolding.

---

## 5.7 Console Shell 🆕

> *Absorbed from console prototype. The shell provides constant spatial orientation.*

**Layout:** Sidebar (220px fixed) + Main content area (flex).

**Sidebar anatomy (top to bottom):**

```
┌── SIDEBAR (220px) ──────────────────┐
│  [P] Poopsy                         │  Logo + version (IN-A-BOX · v5)
│      IN-A-BOX · v5                  │
│─────────────────────────────────────│
│  VIEWING AS                         │  Actor switcher
│  [💪 James] [⚖️ Laura] [🌟 Charlie]│  Emoji buttons per member
│─────────────────────────────────────│
│  ☀️  Today                          │  Navigation items
│  ✅  Tasks           [1]            │  Badge = inbox count
│  📅  Schedule                       │
│  📋  Lists                          │
│  💬  Chat                           │
│  🏆  Scoreboard                     │
│  👥  People                         │
│  ⚙️  Settings                       │
│                                     │
│  ·································  │
│  👦 Charlie with James today        │  Custody indicator
│  🟢 System Healthy                  │  System health pulse
└─────────────────────────────────────┘
```

**Actor switcher behavior:**
- Parent views (James, Laura): All nav items visible. Full sidebar.
- Charlie view: Hides Tasks, People, Settings from nav. Renders full-screen without sidebar chrome (privacy invariant — see Section 2.3).

**Navigation badges:** Inbox count shown on Tasks nav item. Derived from `SELECT COUNT(*) FROM ops_tasks WHERE status = 'inbox'`.

**Custody indicator:** Shows current custody state from `cal_daily_states`. Background uses `--lav-bg`. Updates with daily state refresh.

**System health pulse:** Green dot with `pulse` animation when all health checks pass. Clicking navigates to Settings → Health panel. Background uses `--grn-bg`.

---

## 6. INGESTION ARCHITECTURE

### 6.1 Adapter Interface

Every data source implements the same interface and returns Five Shapes:

```python
@dataclass
class IngestEvent:
    source: str
    timestamp: str
    idempotency_key: str
    raw: dict
    text: str | None = None
    member_id: str | None = None
    reply_channel: str | None = None
    reply_address: str | None = None

class Adapter(Protocol):
    name: str
    source: str
    async def init(self) -> None: ...
    async def poll(self) -> list[IngestEvent]: ...
    async def ping(self) -> bool: ...
    async def send(self, message: OutboundMessage) -> None: ...
    def register_webhooks(self, app: FastAPI) -> None: ...
```

### 6.2 Adapters

| Adapter | Transport | Poll | Idempotency Key | Notes |
|---|---|---|---|---|
| Gmail | API push + 5min fallback | 5 min | `SHA256(gmail:{messageId})` | Whitelist + triage keywords |
| Google Calendar | API v3 incremental sync | 15 min + 5 min volatile | `SHA256(gcal:{eventId}:{updated})` | Sync tokens. Full sync daily 2AM. **Privacy: respects source classification.** |
| Apple Reminders | AppleScript | 5 min | `SHA256(reminder:{internal_id})` | Key on internal ID, track modification_date |
| iMessage | BlueBubbles webhook + poll | 5 min backup | `SHA256(imessage:{guid})` | Known member phones only |
| Twilio SMS | Webhook | N/A | `SHA256(sms:{MessageSid})` | Signature validation |
| Siri Shortcuts | Webhook | N/A | `SHA256(siri:{ts}:{text})` | Bearer token |
| Bank Import | CSV file watch | 5 min | `SHA256(bank:{acct}:{date}:{amt}:{merchant})` | Plaid deferred |
| Sheets Webhook | Google Apps Script | N/A | `SHA256(sheets:{sheet}:{row}:{col}:{ts})` | Bidirectional sync |

### 6.3 Pipeline

```python
async def ingest(event: IngestEvent, db, event_bus) -> list[dict]:
    actions = []
    
    # STAGE 1: DEDUP
    if await is_duplicate(db, event.idempotency_key):
        return [{"action": "skipped_duplicate"}]
    await record_idempotency(db, event)
    
    # STAGE 2: MEMBER RESOLUTION
    event.member_id = await resolve_member(db, event)
    
    # STAGE 3: PARSE (source-specific → Five Shapes)
    parsed = await parse_event(event)
    
    # STAGE 4: CLASSIFY (deterministic domain + urgency + energy)
    for action in parsed:
        action.urgency = classify_urgency(action)
        action.domain = classify_domain(action)
    
    # STAGE 5: PRIVACY FENCE (Gene 6, Rule 3)
    for action in parsed:
        source_class = await get_source_classification(db, event.source, event.raw)
        if source_class and source_class["privacy"] != "full":
            action = redact_for_privacy(action, source_class["privacy"])
    
    # STAGE 6: ROUTE + WRITE
    for action in parsed:
        try:
            result = await route_and_write(db, action, event)
            actions.append(result)
            if event.source in ('llm_pib', 'api'):
                await log_cos_activity(db, result)
        except Exception as e:
            await dead_letter(db, event, action, str(e))
    
    # STAGE 7: CROSS-DOMAIN OBSERVATIONS
    for obs in await detect_observations(db, actions):
        await insert_observation(db, obs)
    
    # STAGE 8: CONFIRM
    if event.reply_channel and actions:
        await send_confirmation(event, build_confirmation(actions))
    
    for action in actions:
        await event_bus.emit(action)
    
    return actions
```

### 6.4 Prefix Parser

```python
PREFIX_RULES = [
    (r'^grocery:\s*(.+)',       "lists",  {"list_name": "grocery"}),
    (r'^costco:\s*(.+)',        "lists",  {"list_name": "costco"}),
    (r'^target:\s*(.+)',        "lists",  {"list_name": "target"}),
    (r'^hardware:\s*(.+)',      "lists",  {"list_name": "hardware"}),
    (r'^james:\s*(.+)',         "tasks",  {"assignee": "m-james"}),
    (r'^laura:\s*(.+)',         "tasks",  {"assignee": "m-laura"}),
    (r'^buy\s+(.+)',            "tasks",  {"item_type": "purchase"}),
    (r'^call\s+(.+)',           "tasks",  {"requires": "phone"}),
    (r'^remember\s+(.+)',       "memory", {"action": "save_fact"}),
    (r'^meds\s*(taken)?',       "state",  {"action": "medication_taken"}),
    (r'^sleep\s+(great|okay|rough)', "state", {"action": "sleep_report"}),
]
```

> **🆕 CONSOLE UPDATE — Chat Quick Chips (Step 7: CONSOLE in 8-step wiring)**

The chat interface displays tappable quick-action buttons above the input field, mapping to `PREFIX_RULES` above:

```
[ today ] [ now ] [ grocery list ] [ schedule ] [ status ] [ diff ] [ help ]
```

Each chip pre-fills the chat input with the corresponding prefix command. This reduces recall burden for ADHD users — they don't need to remember command syntax, just tap. Chips are rendered as pill-shaped buttons using `--pink-bg` with `--pink` text on hover, matching the console design system (Section 5.6).

### 6.5 Micro-Script Generator (deterministic, no LLM)

```python
def generate_micro_script(task: dict, items_cache: dict) -> str:
    item_type = task.get("item_type", "task")
    item = items_cache.get(task.get("item_ref")) if task.get("item_ref") else None
    
    if item_type == "appointment" and item and item.get("phone"):
        return f"Open phone → call {item['name']} at {item['phone']}"
    if item_type == "purchase":
        return f'Open browser → search "{task["title"]}"'
    if item_type == "research":
        return f'Open browser → search "{task["title"]}" → read top 3 results'
    if item_type == "decision":
        return f'Open notes → list pros/cons for: {task["title"]}'
    if task.get("requires") == "phone":
        return f'Pick up phone → "{task.get("waiting_on") or task["title"]}"'
    if task.get("requires") == "car" and task.get("location_text"):
        return f"Keys + wallet → car → {task['location_text']}"
    return f'Start: {task["title"]}'
```

---

## 7. CONTEXT ASSEMBLY + LLM INTEGRATION

### 7.1 Three-Layer Relevance Detection

```python
# LAYER 1: Keyword sets (fast)
FINANCIAL_TRIGGERS = {"money","spend","spent","budget","afford","cost","price","save","income",
    "mortgage","bill","payment","account","balance","transaction","$"}
SCHEDULE_TRIGGERS = {"calendar","schedule","busy","free","available","appointment","meeting",
    "event","conflict","today","tomorrow","this week","next week","weekend",
    "monday","tuesday","wednesday","thursday","friday","saturday","sunday"}
TASK_TRIGGERS = {"task","to-do","todo","honey-do","remind","need to","should","must",
    "deadline","overdue","done","finish","complete"}
COVERAGE_TRIGGERS = {"who has","custody","pickup","dropoff","coverage","gap","babysit","sitter"}

# LAYER 2: Entity name matching (refreshed every 15 min)
# CRITICAL: Use word-boundary matching, not substring. "ken" must NOT match "broken".
import re

def build_entity_cache(db) -> dict:
    """Load entities and compile word-boundary regex patterns."""
    entities = {}
    for row in db.execute("SELECT id, name FROM ops_items WHERE status='active'").fetchall():
        # \b = word boundary — prevents "ken" matching "broken" or "chicken"
        pattern = re.compile(r'\b' + re.escape(row["name"].lower()) + r'\b')
        entities[row["id"]] = {"name": row["name"], "pattern": pattern}
    for row in db.execute("SELECT id, display_name FROM common_members WHERE active=1").fetchall():
        pattern = re.compile(r'\b' + re.escape(row["display_name"].lower()) + r'\b')
        entities[row["id"]] = {"name": row["display_name"], "pattern": pattern}
    return entities

# LAYER 3: Always-on 500-token cross-domain summary

def analyze_relevance(message: str, entity_cache: dict) -> QueryRelevance:
    """Multi-match, not first-match. Returns all relevant assemblers."""
    msg_lower = message.lower()
    assemblers = set()
    matched_entities = []
    
    # Layer 1: Keyword triggers
    if any(t in msg_lower for t in FINANCIAL_TRIGGERS):
        assemblers.add("financial")
    if any(t in msg_lower for t in SCHEDULE_TRIGGERS):
        assemblers.add("schedule")
    if any(t in msg_lower for t in TASK_TRIGGERS):
        assemblers.add("tasks")
    if any(t in msg_lower for t in COVERAGE_TRIGGERS):
        assemblers.update(["coverage", "schedule"])
    
    # Layer 2: Entity matching with word boundaries
    for entity_id, entity in entity_cache.items():
        if entity["pattern"].search(msg_lower):
            matched_entities.append(entity_id)
            assemblers.add("entity_lookup")
    
    # Layer 3: Cross-domain summary always included (500 tokens)
    assemblers.add("cross_domain_summary")
    
    return QueryRelevance(assemblers=list(assemblers), matched_entities=matched_entities)

# Cross-domain summary query uses SQLite-compatible aggregation (no PostgreSQL FILTER):
CROSS_DOMAIN_SUMMARY_SQL = """
SELECT
    (SELECT COUNT(*) FROM ops_tasks WHERE status NOT IN ('done','dismissed')) AS active_tasks,
    (SELECT COUNT(*) FROM ops_tasks WHERE due_date < date('now') AND status NOT IN ('done','dismissed','deferred')) AS overdue_tasks,
    (SELECT COUNT(*) FROM ops_tasks WHERE due_date = date('now') AND status NOT IN ('done','dismissed')) AS due_today,
    (SELECT COUNT(*) FROM cal_conflicts WHERE status = 'unresolved') AS open_conflicts,
    (SELECT SUM(CASE WHEN over_threshold = 1 THEN 1 ELSE 0 END) FROM fin_budget_snapshot) AS budget_alerts,
    (SELECT name FROM common_life_phases WHERE status = 'active' LIMIT 1) AS active_phase
"""
# NOTE: SQLite does not support PostgreSQL's FILTER (WHERE ...) clause.
# Use SUM(CASE WHEN ... THEN 1 ELSE 0 END) or subqueries instead.
```

### 7.2 Token Budget

```python
TOKEN_BUDGETS = {
    "system_prompt":        2_500,   # Personality, rules, phase, coach protocols
    "cross_domain_summary":   500,   # Always injected
    "assembled_context":   25_000,   # Variable: main data payload
    "memory_injection":     3_000,   # Long-term + session facts
    "conversation_history": 20_000,  # Recent messages (sliding window)
}
# TOTAL MAX: ~51,000 tokens input. Well within 200K context window.

def estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ≈ 4 chars for English text."""
    return len(text) // 4

def enforce_budget(section_name: str, content: str) -> str:
    """Truncate content to fit its budget. Log when truncation occurs."""
    budget = TOKEN_BUDGETS[section_name]
    estimated = estimate_tokens(content)
    if estimated > budget:
        log.warning(f"Token budget exceeded: {section_name} = {estimated} tokens (budget: {budget}). Truncating.")
        # Truncate from the middle, keeping start and end for context
        char_budget = budget * 4
        half = char_budget // 2
        content = content[:half] + "\n... [truncated] ...\n" + content[-half:]
    return content

# Conversation History Window Management:
# SMS/iMessage: keep last 10 messages (short context, fast response)
# Web chat: keep last 50 messages
# On each turn, trim oldest messages when estimate exceeds budget
def build_conversation_history(messages: list, channel: str) -> list:
    """Sliding window: keep recent messages within token budget."""
    max_messages = 10 if channel in ("sms", "imessage") else 50
    budget = TOKEN_BUDGETS["conversation_history"]
    
    recent = messages[-max_messages:]
    total_tokens = sum(estimate_tokens(m["content"]) for m in recent)
    
    while total_tokens > budget and len(recent) > 2:
        removed = recent.pop(0)
        total_tokens -= estimate_tokens(removed["content"])
    
    return recent
```

### 7.3 Privacy-Filtered Context (Gene 2, Gene 7 Invariant 5)

```python
async def build_calendar_context(db, date_range, member_id) -> str:
    """Calendar context with privacy filtering at the read layer."""
    events = await db.execute_fetchall(
        "SELECT * FROM cal_classified_events WHERE event_date BETWEEN ? AND ? "
        "ORDER BY start_time", [date_range.start, date_range.end])
    
    lines = []
    for event in events:
        if event["privacy"] == "full":
            lines.append(f"  {event['start_time']}-{event['end_time']} {event['title']}")
        elif event["privacy"] == "privileged":
            # Timing only, redacted title
            lines.append(f"  {event['start_time']}-{event['end_time']} {event['title_redacted']}")
        elif event["privacy"] == "redacted":
            # Existence only
            member_name = await get_member_name(db, event["for_member_ids"])
            lines.append(f"  {event['start_time']}-{event['end_time']} [{member_name} — unavailable]")
    
    return "\n".join(lines)
```

### 7.4 System Prompt

```python
def build_system_prompt(member: dict, channel: str, coach_protocols: list) -> str:
    phase = get_active_phase()
    
    prompt = f"""You are PIB 💩 — the Stice-Sclafani household Chief of Staff. You live on a Mac Mini in the closet. You're the competent friend who happens to have a photographic memory and infinite patience. Not a robot. Not a servant. A peer who happens to be really, really organized.

WHO: {member["display_name"]} ({member["role"]})
CHANNEL: {channel}
{"BREVITY: 1-3 sentences max. No markdown. No bullets." if channel in ("imessage", "sms") else ""}
PHASE: {phase["name"] if phase else "normal"} — {phase.get("description", "")}
TODAY: {date.today().strftime("%A, %B %d, %Y")}

PERSONALITY:
- Warm, direct, first-name. Lead with the answer.
- Match question energy. Casual → casual. Focused → focused.
- Never guilt, shame, or compare family members.
- Celebrate completions. Always. Every single time.
"""
    
    # Actor-specific shaping
    if member["id"] == "m-james":
        prompt += """
JAMES-SPECIFIC:
- ADHD-aware: ONE thing at a time. Never lists of 5+. Always the micro-script first.
- When presenting an overdue task: lead with the micro-script, not the overdue count.
- After 3+ completions in a session: "That's momentum. Want to ride it or bank it?"
- Periodically: "Your three things today are X, Y, Z. Even without me, you know these."
"""
    elif member["id"] == "m-laura":
        prompt += """
LAURA-SPECIFIC:
- Brief. No preamble. Lead with what needs her attention.
- HOME life only. Never reference or acknowledge her work calendar content.
- Highlight: decisions needing her, schedule conflicts, what James is handling.
"""
    
    # Coach protocols
    prompt += "\nPROTOCOLS:\n"
    for p in coach_protocols:
        prompt += f"- {p['name']}: {p['behavior']}\n"
    
    prompt += """
RULES:
1. Every claim MUST come from tool calls or context blocks. Never guess.
2. When you learn a persistent fact, use save_memory immediately.
3. Confirm actions in ONE line.
4. Messages to non-household people: ALWAYS queue for approval.
5. If you detect a conflict the system hasn't caught, flag it.
6. For task completions, ALWAYS use the complete_task tool (it handles rewards + streaks).
7. Never output privileged calendar content. If it's redacted in context, it's redacted in your response.
"""
    return prompt
```

### 7.5 Model Selection

```python
# Models loaded from config — NEVER hardcoded. Anthropic deprecates model versions;
# hardcoded strings become silent failures when endpoints stop responding.
from pib.config import get_config

def get_model(tier: str) -> str:
    """Load model ID from pib_config table with sane defaults."""
    defaults = {
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-6",
    }
    return get_config(f"anthropic_model_{tier}", defaults.get(tier, defaults["sonnet"]))

def select_model(assemblers: list[str], channel: str) -> str:
    """Escalate to Opus only when multiple domains need synthesis."""
    if len(assemblers) >= 3:
        return get_model("opus")   # Cross-domain synthesis
    if "morning_brief" in assemblers:
        return get_model("opus")   # Briefing composition
    if channel == "email" and assemblers:
        return get_model("opus")   # Sensitive external comms
    return get_model("sonnet")

# Cost estimate:
# Sonnet: ~$25/month for routine
# Opus escalation: ~$15-25/month for complex queries (~10% of volume)
# Total: ~$40-50/month
```

### 7.6 Conversation Flow

```python
async def handle_message(message, member_id, channel, session_id=None):
    """Main handler. Streaming. Circuit breaker at 5 tool rounds."""
    session = await get_or_create_session(db, member_id, channel, session_id)
    
    # Detect state commands before LLM
    state_cmd = parse_state_command(message)  # "meds taken", "sleep rough", etc.
    if state_cmd:
        await handle_state_command(db, member_id, state_cmd)
        wn = what_now(member_id, await load_snapshot(db, member_id))
        if state_cmd["action"] == "medication_taken":
            yield f"Logged ✓ Peak in ~{member.medication_config.get('peak_onset_minutes',60)} min."
        elif state_cmd["action"] == "sleep_report":
            yield f"Got it — {state_cmd['value']} night."
            if state_cmd["value"] == "rough":
                yield " Easy day mode. Only tiny tasks."
        if wn.the_one_task:
            yield f"\nNext up: {wn.the_one_task['title']}\n{wn.the_one_task['micro_script']}"
        return
    
    # Standard LLM flow
    relevance = analyze_relevance(message, entity_cache)
    model = select_model(relevance.assemblers, channel)
    contexts = await assemble_all(db, member_id, relevance)
    
    # Prefix commands work without LLM (Layer 1)
    prefix_result = parse_prefix_command(message)
    if prefix_result:
        actions = await ingest(prefix_result, db, event_bus)
        yield build_confirmation(actions)
        return
    
    # Try LLM (Layer 2). If API is down, fall back to deterministic response.
    try:
        history = build_conversation_history(
            await get_session_messages(db, session.id), channel)
        messages = build_llm_messages(contexts, history, message)
        
        tool_rounds = 0
        async for chunk in stream_llm(model, messages, tools=TOOLS):
            if chunk.type == "text":
                yield chunk.text
            elif chunk.type == "tool_use" and tool_rounds < 5:
                result = await execute_tool(db, chunk.tool, chunk.input, member_id)
                messages.append({"role": "assistant", "content": chunk})
                messages.append({"role": "user", "content": [{"type": "tool_result", **result}]})
                tool_rounds += 1
            elif tool_rounds >= 5:
                yield "\n(Reached tool limit for this conversation. Try a more specific question.)"
                break
    
    except anthropic.APIConnectionError:
        # Layer 2 → Layer 1 degradation: deterministic response without LLM
        yield _deterministic_fallback(message, member_id, db)
    except anthropic.APIStatusError as e:
        if e.status_code >= 500:
            yield _deterministic_fallback(message, member_id, db)
        else:
            raise

async def _deterministic_fallback(message: str, member_id: str, db) -> str:
    """Layer 1 response when Anthropic API is unavailable. No LLM. Pure data."""
    msg_lower = message.lower()
    wn = what_now(member_id, await load_snapshot(db, member_id))
    
    # Handle common queries deterministically
    if any(t in msg_lower for t in ["what's next", "next", "what now", "what should"]):
        if wn.the_one_task:
            return f"Next: {wn.the_one_task['title']}\n{wn.the_one_task['micro_script']}"
        return "Nothing pending right now."
    
    if any(t in msg_lower for t in ["who has", "custody", "charlie"]):
        state = await get_daily_state(db, date.today())
        if state:
            return f"Custody today: {json.loads(state['custody_states'])}"
        return "Custody data unavailable."
    
    if "done" in msg_lower and wn.the_one_task:
        await complete_task_with_reward(db, wn.the_one_task["id"], member_id, "user")
        return "Done ✓ (AI is temporarily offline — basic mode active)"
    
    # Default: acknowledge + surface whatNow
    parts = [f"⚠️ AI offline — basic mode. {wn.context}"]
    if wn.the_one_task:
        parts.append(f"Next: {wn.the_one_task['title']}")
    return "\n".join(parts)
```

### 7.7 Tool Definitions

15 tools total. The LLM uses these to take action:

```python
TOOLS = [
    # Task management
    {"name": "create_task", "description": "Create a new task with title, assignee, due_date, energy, effort, micro_script"},
    {"name": "update_task_status", "description": "Change task status (uses state machine guards)"},
    {"name": "complete_task", "description": "Complete a task. Handles reward, streak, Zeigarnik hook."},
    {"name": "what_now", "description": "Get the ONE task this person should do next."},
    
    # Lists and items
    {"name": "add_list_items", "description": "Add items to a named list (grocery, costco, target, etc.)"},
    {"name": "search_items", "description": "Search ops_items by name, type, or FTS5 query"},
    
    # Communication
    {"name": "send_message", "description": "Queue a message for delivery. Non-household → approval queue."},
    
    # Queries
    {"name": "query_schedule", "description": "Get calendar events for a date range"},
    {"name": "query_transactions", "description": "Search financial transactions"},
    {"name": "query_budget", "description": "Get budget snapshot with spending vs targets"},
    
    # Memory
    {"name": "save_memory", "description": "Save a persistent fact to long-term memory (with dedup)"},
    {"name": "recall_memory", "description": "Search long-term memory via FTS5"},
    
    # System
    {"name": "resolve_conflict", "description": "Mark a calendar conflict as resolved"},
    {"name": "undo_last", "description": "Reverse the last LLM-generated operation"},
    {"name": "approve_pending", "description": "Approve or reject a pending approval queue item"},
    
    # State (new in v5)
    {"name": "log_state", "description": "Log medication, sleep quality, or focus mode change"},
]
```

---

## 8. PROACTIVE ENGINE

### 8.1 Triggers (from v4, extended with ADHD captures)

```python
PROACTIVE_TRIGGERS = [
    # ── CRITICAL ──
    {"name": "critical_conflict_48h", "priority": 1, "cooldown": 120,
     "query": "SELECT * FROM cal_conflicts WHERE severity IN ('critical','high') AND status='unresolved' AND conflict_date <= date('now','+2 days')"},
    
    # ── DAILY ──
    {"name": "morning_digest", "priority": 2, "cooldown": 1440,
     "condition": lambda: datetime.now().hour == 6,
     "includes_sleep_check": True,          # Prepend: "Quick sleep check: 😴 Great / 😐 Okay / 😵 Rough"
     "assembler": "morning_brief", "model": "opus"},
    
    # ── ADHD-SPECIFIC (new in v5) ──
    {"name": "paralysis_detection", "priority": 3, "cooldown": 180,
     "query": "SELECT 1 FROM pib_energy_states WHERE member_id='m-james' AND state_date=date('now') AND last_interaction_at < datetime('now','-2 hours') AND focus_mode_active = 0",
     "extra_check": lambda: not _in_calendar_block("m-james"),
     "compose": "Gentle check-in. Never guilt. Offer tiniest restart."},
    
    {"name": "post_meeting_capture", "priority": 4, "cooldown": 30,
     "query": "SELECT * FROM cal_classified_events WHERE for_member_ids LIKE '%m-james%' AND scheduling_impact='HARD_BLOCK' AND datetime(end_time) BETWEEN datetime('now','-15 minutes') AND datetime('now') AND event_type != 'personal'",
     "compose": "Just finished [title]. Any action items?"},
    
    {"name": "velocity_celebration", "priority": 6, "cooldown": 480,
     "query": "SELECT * FROM pib_energy_states WHERE member_id='m-james' AND state_date=date('now') AND completions_today >= 10 AND velocity_cap_hit = 0",
     "compose": "Celebrate velocity without pushing more. Suggest break."},
    
    # ── OPERATIONAL (from v4) ──
    {"name": "overdue_nudge", "priority": 5, "cooldown": 480,
     "query": "SELECT COUNT(*) FROM ops_tasks WHERE status NOT IN ('done','dismissed','deferred') AND due_date < date('now')",
     "threshold": 3,
     "compose": "Pick single easiest overdue. Give micro-step. 2 sentences."},
    
    {"name": "budget_alert", "priority": 4, "cooldown": 1440,
     "query": "SELECT * FROM fin_budget_snapshot WHERE over_threshold=1 AND is_fixed=0"},
    
    {"name": "weekly_review", "priority": 3, "cooldown": 10080,
     "condition": lambda: datetime.now().weekday() == 6 and datetime.now().hour == 20,
     "includes_scaffold": True},            # Include "Your three things" fallback
    
    {"name": "bill_reminder", "priority": 6, "cooldown": 1440,
     "query": "SELECT * FROM fin_recurring_bills WHERE active=1 AND auto_pay=0 AND next_due BETWEEN date('now') AND date('now','+3 days')"},
    
    {"name": "approval_expiring", "priority": 3, "cooldown": 120,
     "query": "SELECT * FROM mem_approval_queue WHERE status='pending' AND auto_expire_at BETWEEN datetime('now') AND datetime('now','+2 hours') AND expiry_notification_sent=0"},
]
```

### 8.2 Guardrails (from v4, extended)

```python
GUARDRAILS = {
    "max_messages_per_person_per_day": 5,
    "max_messages_per_hour": 2,
    "quiet_hours": {"start": 22, "end": 7},
    "respect_focus_mode": True,             # NEW: DND = total silence
}

async def can_send_proactive(trigger, recipient_id, db) -> bool:
    # Quiet hours, in-meeting check, daily/hourly limits, cooldown (from v4)
    # PLUS:
    energy = await get_energy_state(db, recipient_id)
    if energy and energy["focus_mode_active"]:
        return trigger["priority"] <= 1  # Only critical conflicts break focus
    return True  # (after passing all other checks)
```

### 8.3 Morning Digest Composition (with hallucination guard)

The morning digest is the most important message PIB sends. It uses Opus for composition. But Opus can hallucinate conflicts that don't exist. Defense: compose from structured data only, then validate output against source data before sending.

```python
async def compose_morning_digest(db, member_id: str) -> str:
    """Compose morning digest. Structured data → Opus composition → validation → delivery."""
    
    # ── STEP 1: Gather structured data (deterministic, no LLM) ──
    wn = what_now(member_id, await load_snapshot(db, member_id))
    daily_state = await get_daily_state(db, date.today())
    energy = await get_energy_state(db, member_id)
    overdue = await db.execute_fetchall(
        "SELECT title, due_date FROM ops_tasks WHERE assignee=? AND status NOT IN ('done','dismissed','deferred') "
        "AND due_date < date('now') ORDER BY due_date LIMIT 5", [member_id])
    conflicts = await db.execute_fetchall(
        "SELECT * FROM cal_conflicts WHERE status='unresolved' AND conflict_date <= date('now','+2 days')")
    budget_alerts = await db.execute_fetchall(
        "SELECT category, pct_used FROM fin_budget_snapshot WHERE over_threshold=1")
    
    structured = {
        "date": date.today().isoformat(),
        "custody": json.loads(daily_state["custody_states"]) if daily_state else None,
        "top_task": wn.the_one_task,
        "overdue_count": len(overdue),
        "overdue_titles": [r["title"] for r in overdue[:3]],
        "conflicts": [{"title": c["title"], "date": c["conflict_date"]} for c in conflicts],
        "budget_alerts": [{"category": b["category"], "pct": b["pct_used"]} for b in budget_alerts],
        "streak": wn.streak_state,
        "energy_hint": energy["current_energy"] if energy else "medium",
    }
    
    # ── STEP 2: Compose with Opus ──
    try:
        composed = await call_llm(
            model=get_model("opus"),
            system="Compose a morning briefing from ONLY the structured data provided. "
                   "Do NOT infer, guess, or add information not in the data. "
                   "Warm, brief, 5-8 sentences. Lead with the most important thing.",
            user=json.dumps(structured),
            max_tokens=500
        )
    except (anthropic.APIConnectionError, anthropic.APIStatusError):
        # ── FALLBACK: deterministic template (no LLM needed) ──
        return _template_digest(structured, member_id)
    
    # ── STEP 3: Validate output against source data ──
    # Hallucination guard: if the composed text mentions entities/events
    # not present in the structured data, fall back to template
    validation_failures = _validate_digest(composed, structured)
    if validation_failures:
        log.warning(f"Digest hallucination detected: {validation_failures}")
        return _template_digest(structured, member_id)
    
    return composed

def _validate_digest(composed: str, structured: dict) -> list[str]:
    """Check that composed digest doesn't contain information not in structured data."""
    failures = []
    composed_lower = composed.lower()
    
    # Check for day names not implied by the date
    actual_day = date.fromisoformat(structured["date"]).strftime("%A").lower()
    day_names = {"monday","tuesday","wednesday","thursday","friday","saturday","sunday"}
    mentioned_days = {d for d in day_names if d in composed_lower}
    # Allow today's day and tomorrow's
    tomorrow = (date.fromisoformat(structured["date"]) + timedelta(days=1)).strftime("%A").lower()
    allowed_days = {actual_day, tomorrow}
    suspicious_days = mentioned_days - allowed_days
    if suspicious_days:
        failures.append(f"Mentions days not in data: {suspicious_days}")
    
    # Check for dollar amounts not in budget alerts
    import re
    dollar_amounts = re.findall(r'\$[\d,]+', composed)
    if dollar_amounts and not structured["budget_alerts"]:
        failures.append(f"Mentions dollar amounts but no budget alerts in data")
    
    # Check for names not in the structured data
    # (simple heuristic: if the text mentions a proper noun not in any field, suspicious)
    return failures

def _template_digest(data: dict, member_id: str) -> str:
    """Deterministic template digest. No LLM. Always works."""
    lines = [f"☀️ Good morning. {date.today().strftime('%A, %B %d')}."]
    
    if data.get("energy_hint") == "low":
        lines.append("Easy day mode — only small tasks.")
    
    if data["custody"]:
        for child, parent in data["custody"].items():
            lines.append(f"{child} is with {'you' if parent == member_id else parent} today.")
    
    if data["top_task"]:
        lines.append(f"Top priority: {data['top_task']['title']}")
    
    if data["overdue_count"] > 0:
        lines.append(f"{data['overdue_count']} overdue. Easiest: {data['overdue_titles'][0]}")
    
    if data["conflicts"]:
        lines.append(f"⚠️ {len(data['conflicts'])} scheduling conflict(s) need attention.")
    
    if data["budget_alerts"]:
        cats = ", ".join(a["category"] for a in data["budget_alerts"])
        lines.append(f"Budget watch: {cats}")
    
    if data["streak"] and data["streak"].get("current_streak", 0) >= 3:
        lines.append(f"🔥 Streak: {data['streak']['current_streak']} days!")
    
    return "\n".join(lines)
```

### 8.4 Misclassification Correction

When the LLM classifies something wrong (email triage, transaction categorization), users need a correction path that updates the deterministic layer, not just the current conversation.

```python
# Correction commands (prefix parser extensions):
# "fix: that transaction is groceries not dining"
# "fix: that email is personal not firm"
# "reclassify: merchant Trader Joe's → groceries"

async def handle_correction(db, correction: dict, member_id: str):
    """Apply a user correction to the classification layer.
    Updates deterministic rules so the same mistake doesn't repeat."""
    
    if correction["type"] == "transaction_category":
        # Update merchant rule (deterministic: future transactions auto-categorize)
        await db.execute(
            "INSERT INTO fin_merchant_rules (merchant_pattern, category, source, created_by) "
            "VALUES (?, ?, 'user_correction', ?) "
            "ON CONFLICT(merchant_pattern) DO UPDATE SET category=?, source='user_correction'",
            [correction["merchant"], correction["correct_category"],
             member_id, correction["correct_category"]])
        
        # Fix the specific transaction
        if correction.get("transaction_id"):
            await db.execute(
                "UPDATE fin_transactions SET category=?, manually_categorized=1 WHERE id=?",
                [correction["correct_category"], correction["transaction_id"]])
        
        return f"Got it — {correction['merchant']} → {correction['correct_category']} from now on."
    
    elif correction["type"] == "email_triage":
        # Update email whitelist/classification rules
        sender = correction.get("sender")
        if sender:
            await db.execute(
                "INSERT INTO ops_gmail_whitelist (sender_pattern, classification, created_by) "
                "VALUES (?, ?, ?) ON CONFLICT(sender_pattern) DO UPDATE SET classification=?",
                [sender, correction["correct_class"], member_id, correction["correct_class"]])
        return f"Got it — emails from {sender} → {correction['correct_class']}."
    
    elif correction["type"] == "task_domain":
        if correction.get("task_id"):
            await db.execute(
                "UPDATE ops_tasks SET domain=? WHERE id=?",
                [correction["correct_domain"], correction["task_id"]])
        return f"Updated domain to {correction['correct_domain']}."

# The key insight: corrections update RULES (merchant_rules, gmail_whitelist),
# not just individual records. This means the system learns deterministically.
# Gene 1 pattern: DISCOVER (LLM classifies) → user CORRECTS → CONFIG updated
# → future DETERMINISTIC execution uses the corrected rule.
```

---

## 9. GOOGLE SHEETS SYNC

### 9.1 Architecture

SQLite is the computational SSOT (integrity, queries, deterministic logic). Google Sheets is the human SSOT (Laura edits there, James has existing Life OS data there).

- **Database → Sheets:** Push every 15 min (cron)
- **Sheets → Database:** Google Apps Script installable `onChange` trigger (NOT simple `onEdit` — simple triggers silently fail on errors and can't call external services). Uses a queue pattern:
- **Bootstrap import:** On first run, import existing Sheets data into SQLite via The Loop (discover → propose → confirm → config)
- **Conflict rule:** Most recent write wins, with audit log entry

**Critical: Why NOT simple onEdit:**
Simple `onEdit` triggers can't make `UrlFetchApp` calls, can't run longer than 30 seconds, and silently swallow exceptions. Use an installable `onChange` trigger with a write-ahead queue in a hidden sheet:

```javascript
// Google Apps Script — installable onChange trigger (NOT simple onEdit)
// CRITICAL: onChange event only contains changeType ("EDIT"), NOT which cells changed.
// We use diff-on-change: compare current state against cached snapshot.

var PIB_WEBHOOK_URL = "https://pib.yourdomain.com/webhooks/sheets";
var PIB_TOKEN = PropertiesService.getScriptProperties().getProperty("PIB_TOKEN");

// Tabs PIB cares about (must match SHEETS_SYNC_CONFIG keys)
var TRACKED_TABS = ["TASKS", "ITEMS", "LISTS", "RECURRING", "BUDGET"];

function onChange(e) {
  if (e.changeType !== "EDIT") return;  // Only care about cell edits
  
  var ss = SpreadsheetApp.getActive();
  var activeSheet = ss.getActiveSheet();
  var tabName = activeSheet.getName();
  
  if (TRACKED_TABS.indexOf(tabName) === -1) return;  // Not a tracked tab
  
  // Diff: compare current data against cached snapshot
  var changes = diffTab(activeSheet, tabName);
  if (changes.length === 0) return;
  
  // Queue changes to hidden sheet (never fails, even if webhook is down)
  var queue = ss.getSheetByName("_pib_queue");
  if (!queue) {
    queue = ss.insertSheet("_pib_queue");
    queue.hideSheet();
    queue.appendRow(["timestamp", "tab", "row_index", "row_data"]);
  }
  
  for (var i = 0; i < changes.length; i++) {
    queue.appendRow([
      new Date().toISOString(),
      tabName,
      changes[i].row_index,
      JSON.stringify(changes[i].row_data)
    ]);
  }
  
  // Update snapshot cache
  cacheTabSnapshot(activeSheet, tabName);
  
  // Try to flush
  flushQueue();
}

function diffTab(sheet, tabName) {
  var cache = CacheService.getDocumentCache();
  var oldSnapshot = cache.get("snapshot_" + tabName);
  
  var currentData = sheet.getDataRange().getValues();
  var headers = currentData[0];
  var currentJson = JSON.stringify(currentData);
  
  if (!oldSnapshot) {
    // First run: cache everything, no diff
    cache.put("snapshot_" + tabName, currentJson, 21600); // 6h TTL
    return [];
  }
  
  var oldData = JSON.parse(oldSnapshot);
  var changes = [];
  
  // Compare row by row (skip header row 0)
  for (var i = 1; i < currentData.length; i++) {
    var currentRow = JSON.stringify(currentData[i]);
    var oldRow = i < oldData.length ? JSON.stringify(oldData[i]) : null;
    
    if (currentRow !== oldRow) {
      // Build keyed object from headers
      var rowObj = {};
      for (var j = 0; j < headers.length; j++) {
        rowObj[headers[j]] = currentData[i][j];
      }
      changes.push({row_index: i, row_data: rowObj});
    }
  }
  
  return changes;
}

function cacheTabSnapshot(sheet, tabName) {
  var cache = CacheService.getDocumentCache();
  var data = sheet.getDataRange().getValues();
  cache.put("snapshot_" + tabName, JSON.stringify(data), 21600);
}

function flushQueue() {
  var queue = SpreadsheetApp.getActive().getSheetByName("_pib_queue");
  if (!queue || queue.getLastRow() <= 1) return;  // <= 1 because row 1 is header
  
  var data = queue.getDataRange().getValues();
  var options = {
    method: "post",
    contentType: "application/json",
    headers: {"Authorization": "Bearer " + PIB_TOKEN},
    muteHttpExceptions: true
  };
  
  var sent = [];
  for (var i = 1; i < data.length; i++) {  // Skip header
    options.payload = JSON.stringify({
      ts: data[i][0],
      tab: data[i][1],
      row_index: data[i][2],
      row_data: JSON.parse(data[i][3])
    });
    var resp = UrlFetchApp.fetch(PIB_WEBHOOK_URL, options);
    if (resp.getResponseCode() === 200) {
      sent.push(i + 1);  // Sheet rows are 1-indexed
    } else {
      break;
    }
  }
  for (var j = sent.length - 1; j >= 0; j--) {
    queue.deleteRow(sent[j]);
  }
}

// Time-driven trigger (every 5 min): re-snapshot + flush any stuck queue items
function scheduledSync() {
  var ss = SpreadsheetApp.getActive();
  for (var i = 0; i < TRACKED_TABS.length; i++) {
    var sheet = ss.getSheetByName(TRACKED_TABS[i]);
    if (sheet) cacheTabSnapshot(sheet, TRACKED_TABS[i]);
  }
  flushQueue();
}
```

### 9.2 Push Sync (Database → Sheets)

```python
# Synced tabs and their source queries
SHEETS_SYNC_CONFIG = {
    "TASKS": {
        "query": "SELECT id, title, status, assignee, due_date, energy, effort, domain FROM ops_tasks WHERE status NOT IN ('done','dismissed') ORDER BY due_date",
        "headers": ["ID", "Title", "Status", "Assignee", "Due", "Energy", "Effort", "Domain"],
    },
    "ITEMS": {
        "query": "SELECT id, name, type, category, phone, email, status FROM ops_items WHERE status='active' ORDER BY type, name",
        "headers": ["ID", "Name", "Type", "Category", "Phone", "Email", "Status"],
    },
    "LISTS": {
        "query": "SELECT list_name, item_text, quantity, unit, category, checked FROM ops_lists ORDER BY list_name, checked, added_at",
        "headers": ["List", "Item", "Qty", "Unit", "Category", "Done"],
    },
    "RECURRING": {
        "query": "SELECT id, title, frequency, assignee, next_due, domain FROM ops_recurring WHERE active=1 ORDER BY next_due",
        "headers": ["ID", "Title", "Frequency", "Assignee", "Next Due", "Domain"],
    },
    "BUDGET": {
        "query": "SELECT category, monthly_target, spent_this_month, remaining, pct_used FROM fin_budget_snapshot ORDER BY category",
        "headers": ["Category", "Target", "Spent", "Remaining", "% Used"],
    },
}

async def push_to_sheets(db, sheets_service, sheet_id: str):
    """Push database state to Google Sheets. Runs every 15 min."""
    for tab_name, config in SHEETS_SYNC_CONFIG.items():
        rows = await db.execute_fetchall(config["query"])
        values = [config["headers"]] + [[str(v) if v is not None else "" for v in row] for row in rows]
        sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"'{tab_name}'!A1",
            valueInputOption="RAW", body={"values": values}
        ).execute()
```

### 9.3 Webhook Handler (Sheets → Database)

```python
@app.post("/webhooks/sheets")
async def sheets_webhook(request: Request):
    """Handle edits from Google Apps Script onChange queue."""
    if not rate_limiter.check("sheets"):
        raise HTTPException(429, "Rate limited")
    
    payload = await request.json()
    # Validate auth token
    if payload.get("token") != SHEETS_WEBHOOK_TOKEN:
        raise HTTPException(401)
    
    # Route to appropriate handler based on tab
    tab = payload.get("tab")
    row_data = payload.get("data")
    
    if tab == "TASKS" and row_data.get("id"):
        await update_task_from_sheet(db, row_data)
    elif tab == "LISTS":
        await update_list_from_sheet(db, row_data)
    # ... other tabs
    
    # Audit log the conflict if timestamps overlap
    await log_sheet_edit(db, payload)
    return {"status": "ok"}
```

**Addition: Bootstrap Import**

```python
async def discover_sheets(sheets_service, sheet_id: str) -> dict:
    """Gene 1: DISCOVER step. Read actual sheet structure."""
    result = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    tabs = [s["properties"]["title"] for s in result["sheets"]]
    
    report = {"sheet_id": sheet_id, "tabs": {}}
    for tab in tabs:
        data = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=f"'{tab}'!A1:ZZ5").execute()
        headers = data.get("values", [[]])[0]
        sample_rows = data.get("values", [])[1:5]
        report["tabs"][tab] = {"headers": headers, "sample_rows": sample_rows, "row_count": len(sample_rows)}
    
    return report

async def propose_sheet_mapping(report: dict) -> dict:
    """Gene 1: PROPOSE step. Map discovered tabs to Five Shapes."""
    # Uses LLM to propose: which tabs → which shapes, which columns → which fields
    # Returns proposed_config for human confirmation
    ...

async def import_confirmed_sheets(db, sheets_service, confirmed_config: dict):
    """Gene 1: CONFIG → DETERMINISTIC. Import data using confirmed mapping."""
    for tab_name, mapping in confirmed_config["tab_mappings"].items():
        data = sheets_service.spreadsheets().values().get(...).execute()
        for row in data.get("values", [])[1:]:
            shaped = apply_mapping(row, mapping)
            await route_and_write(db, shaped)
```

---

## 10. BUILD ORDER — BOOTSTRAP FIRST

The 5-Minute Rule: "Every session should end with James taking a physical-world action within 5 minutes. Documentation alone is a hyperfocus trap."

### Phase 0: Operational (Sessions 1-2, ~12-16 hours total)

By end of Phase 0, the family can text PIB and get responses. Realistic: 2-3 work sessions of 6-8 hours each with a Claude Code instance. The scope is right; "Day 1" was aspirational — treat each Phase as a milestone, not a calendar day.

```
Hour 1:
  □ Python project init (FastAPI + aiosqlite + AsyncIOScheduler + httpx + anthropic)
  □ Structured logging (JSON to /opt/pib/logs/pib.jsonl)
  □ Full SQLite schema (all CREATE TABLE + FTS5 + id_sequences)
  □ Migration framework, config loader
  □ Database module with persistent-connection write queue
  □ Rate limiter middleware

Hour 2:
  □ ID generator (parameterized, allowlist-validated)
  □ Task state machine with guards
  □ Prefix parser (20 test cases)
  □ Micro-script generator
  □ Ingestion pipeline skeleton
  □ pytest config + conftest.py + first test (test_prefix_parser.py)

Hour 3:
  □ Twilio SMS adapter (webhook handler + send)
  □ Siri Shortcuts webhook adapter
  □ Confirmation sender
  □ whatNow() — full implementation

Hour 4:
  □ LLM integration: system prompt, tool definitions, conversation flow
  □ Context assembler: cross-domain summary + task assembler
  □ complete_task tool with reward selection + streak update
  □ Deterministic fallback handler (_deterministic_fallback for API outage)

Hour 5-6:
  □ Basic web chat (HTML/JS + SSE streaming)
  □ Cloudflare Tunnel + Access setup
  □ launchd plist for auto-start
  □ Seed data: members, household config
  □ Hourly backup cron + backup verification job
  □ Health probe endpoint (/health — read-only, no test writes)
  □ END-TO-END TEST: text "grocery: milk, eggs" → confirmation
```

**Phase 0 deliverable:** Family texts commands, gets responses. Web chat works. whatNow() returns the one task. Streaks track. Rewards fire.

### Phase 1: Calendar Intelligence (Sessions 3-4, ~12-16 hours total)

```
Hour 1-2:
  □ Google Calendar adapter (incremental sync)
  □ Calendar source discovery (Gene 1: discover + propose)
  □ Source classification setup (Gene 2: four-label vocabulary)

Hour 3-4:
  □ Classification pipeline (noise → dedup → type → member → impact)
  □ Privacy-filtered context assembly
  □ Custody date math (DST-aware, 20+ test cases including spring forward + fall back)
  □ Daily state computation

Hour 5-6:
  □ Conflict detection
  □ Morning digest: assemble + compose + deliver
  □ Sleep quality check in morning digest
  □ Proactive trigger engine + guardrails
```

**Phase 1 deliverable:** PIB knows the schedule. Morning digest by iMessage. Conflicts detected. "Who has Charlie Thursday?" answered deterministically.

### Phase 2: Console + Scoreboard (Sessions 5-6, ~12-16 hours total)

```
Hour 1-2:
  □ Dashboard: today view (stream carousel + progress dots + radar) 🆕
  □ Per-actor views (James: stream carousel. Laura: compressed. Charlie: full-screen child.) 🆕
  □ Endowed progress (2+ dots at day start) 🆕
  □ Keyboard navigation (← → Enter Esc) 🆕
  □ iMessage adapter (BlueBubbles)
  □ Apple Reminders adapter

Hour 3-4:
  □ Scoreboard page (/scoreboard)
  □ Neuroprosthetic Layers panel in scoreboard (Section 5.5) 🆕
  □ Behavioral mechanics in console (reward display, streak counter)
  □ Coach protocol loading
  □ Chat quick chips (Step 7 — CONSOLE in 8-step wiring) 🆕

Hour 5-6:
  □ Proactive triggers: paralysis detection, post-meeting capture
  □ Energy state tracking (meds, sleep, focus mode)
  □ Health probe + Healthchecks.io
  □ END-TO-END: full day simulation with all actors
```

**Phase 2 deliverable:** Full interface with stream carousel, progress dots, endowed progress, radar, glow animation, keyboard navigation. Scoreboard with neuroprosthetic layers on TV. Chat quick chips active. ADHD mechanics active. Proactive messaging working. Charlie full-screen privacy enforced.

### Phase 3: Finance + Memory + Polish (Weeks 2-4)

```
Week 2:
  □ Bank CSV import + merchant rules + budget snapshot
  □ Financial context in assemblers and digest
  □ Budget alerts, bill reminders
  □ Memory system: save/recall/dedup/auto-promote
  □ Gmail adapter with whitelist + triage

Week 3:
  □ Google Sheets bootstrap import (The Loop)
  □ Push sync + webhook pull
  □ CRM gap detection
  □ Weekly review digest
  □ Entity lookup assembler

Week 4:
  □ Gamification tuning (reward distribution, streak feel)
  □ Coach protocol refinement from real usage
  □ macOS update procedure documentation
  □ Full validation suite
  □ Family onboarding guide
```

---

## 11. SUCCESS CRITERIA

### Outcome Metrics (what "working" means)

| Metric | Baseline | Target | How to measure |
|---|---|---|---|
| Laura's reminders to James per week | 8-12 | <2 | Weekly self-report |
| Functional Autonomy Index (tasks completed / tasks that needed escalation) | Unknown | ≥0.80 | `SELECT COUNT(completed) / COUNT(*) FROM ops_tasks WHERE created_at > date('now','-7 days')` |
| Morning digest delivery rate | 0% | 100% | `SELECT COUNT(*) FROM mem_precomputed_digests WHERE delivered=1` |
| Task capture latency (text → task in DB) | N/A | <10 seconds | Audit log timestamps |
| whatNow() accuracy (does James agree with the selection?) | N/A | ≥80% | Weekly review: "Was PIB's #1 pick right?" |

### Technical Criteria (what "reliable" means)

1. "grocery: milk, eggs, bread" → 3 list items + confirmation in <10 seconds
2. "Who has Charlie Thursday?" → deterministic custody answer, no LLM guess
3. "Can we afford a babysitter Saturday?" → checks schedule + Child Care budget
4. Morning digest by 6:30 AM every day, includes sleep quality check
5. 100 consecutive recurring spawns → exactly 100 tasks, 0 duplicates
6. Memory persists across days — fact saved Monday, recalled Wednesday
7. "Undo that" reverses last LLM operation
8. Every LLM write has confidence score, undo entry, daily activity log
9. Proactive messages respect: quiet hours, daily limits, focus mode, in-meeting, cooldowns
10. Sheets edit by Laura → reflected in SQLite within 60 seconds
11. Laura's work calendar content never appears in any task, memory, or message
12. System runs unattended 30 days — health probe green
13. Anthropic API outage → Layer 1 continues, template fallbacks activate
14. Scoreboard displays on kitchen TV, readable from 10 feet, auto-refreshes

### ADHD Scorecard Targets

| Subsystem | Current | v5 Target | Key Mechanism |
|---|---|---|---|
| Executive Function (Scheduler) | 80-85% | 90%+ | whatNow() externalizes PFC |
| Working Memory (RAM) | 70-75% | 85%+ | Everything captured + persisted + cross-referenced |
| Task Initiation (Launcher) | 65-70% | 85%+ | Micro-scripts + variable rewards + energy matching + Zeigarnik |
| Emotional Regulation | 25-30% | 50%+ | Coach protocols + never-guilt + momentum-check + celebrate |
| Decision Fatigue | 85-90% | 95%+ | whatNow() = ONE task, not choices. Binary: do or skip. |
| Hyperfocus | 35-40% | 60%+ | Velocity cap + paralysis detection + calendar awareness |

---

## 12. OPERATIONAL RUNBOOK

### macOS Update Procedure

1. Time Machine backup (verify)
2. SQLite backup: `cp pib.db pib-pre-update-$(date +%Y%m%d).db`
3. Stop PIB: `launchctl unload com.pib.runtime.plist`
4. Apply update
5. After reboot: verify Full Disk Access, test AppleScript, test chat.db, start PIB, check /health, send test SMS
6. If anything fails: restore from Time Machine

### Recovery Matrix

| Failure | Detection | Recovery |
|---|---|---|
| PIB crash | launchd auto-restart | Check logs, fix, auto-restarts |
| SQLite corruption | Health probe | Restore from hourly backup |
| BlueBubbles down | Health probe | Restart, re-sign Messages |
| Cloudflare Tunnel | External monitor | Restart cloudflared |
| Anthropic API | LLM calls fail | Template fallbacks, Layer 1 continues |
| Google OAuth expired | Adapter failures | Re-run setup_google_oauth.py |
| Full Disk Access revoked | Adapter failures | Re-enable in System Settings |

### Cron Schedule

```yaml
# Fast polls
- "*/5 * * * *"     reminders_poll, imessage_poll_backup
# Calendar
- "*/15 * * * *"    calendar_incremental_sync
- "0 2 * * *"       calendar_full_sync
- "30 5 * * *"      compute_daily_states (today + 7 days)
- "*/5 6-20 * * *"  calendar_volatile_sync (school feeds)
# Tasks
- "0 6 * * *"       recurring_spawn
- "0 17 * * *"      escalation_check
- "*/15 * * * *"    entity_cache_refresh
# Finance
- "0 7 * * *"       check_bank_imports
- "15 7 * * *"      refresh_budget_snapshot
# Sheets
- "*/15 * * * *"    push_to_sheets
# Proactive
- "0 6 * * *"       morning_digest (compose at delivery time)
- "*/30 7-22 * * *" proactive_trigger_scan
- "0 20 * * 0"      weekly_review
# Memory
- "0 */6 * * *"     auto_promote_session_facts
- "0 3 * * 0"       memory_confidence_decay
- "0 7 * * 1"       weekly_memory_review_digest
# System
- "*/30 * * * *"    health_probe
- "0 * * * *"       sqlite_backup (hourly)
- "30 * * * *"      backup_verify (restore to /tmp, run integrity_check, delete)
- "0 4 * * *"       dead_letter_retry
- "0 3 * * *"       cleanup_expired (audit>90d, idempotency>30d, undo>7d)
- "0 6 * * 1"       feed_health_check + source_discovery_scan (Gene 9)
- "0 2 * * 0"       fts5_rebuild (rebuild all FTS5 indexes to fix silent staleness)
- "0 5 * * *"       db_size_monitor (warn if >500MB, VACUUM if fragmentation >30%)
- "*/15 * * * *"    approval_queue_expiry (expire pending approvals past auto_expire_at)
```

**FTS5 Rebuild** — FTS5 content= tables go stale if rows are inserted/updated/deleted without corresponding FTS operations. Weekly rebuild catches any drift:
```python
async def fts5_rebuild(db):
    for table in ["mem_long_term_fts", "ops_tasks_fts", "ops_items_fts"]:
        await db.execute(f"INSERT INTO {table}({table}) VALUES('rebuild')")
```

**Backup Verification** — An unverified backup is not a backup:
```python
async def backup_verify():
    latest = max(glob("/opt/pib/data/backups/*.db"))
    shutil.copy(latest, "/tmp/pib_verify.db")
    async with aiosqlite.connect("/tmp/pib_verify.db") as db:
        result = await db.execute_fetchone("PRAGMA integrity_check")
        if result[0] != "ok":
            await alert("Backup integrity check FAILED", severity="critical")
    os.remove("/tmp/pib_verify.db")
```

**DB Size Monitoring:**
```python
async def db_size_monitor(db):
    size_mb = os.path.getsize("/opt/pib/data/pib.db") / (1024 * 1024)
    page_count = (await db.execute_fetchone("PRAGMA page_count"))[0]
    free_pages = (await db.execute_fetchone("PRAGMA freelist_count"))[0]
    fragmentation = free_pages / page_count if page_count else 0
    if size_mb > 500:
        await alert(f"Database size: {size_mb:.0f}MB — consider archiving old audit logs")
    if fragmentation > 0.30:
        await db.execute("VACUUM")
        log.info(f"VACUUM complete. Was {fragmentation:.0%} fragmented.")
```

**Health Probe** — READ-ONLY queries on production tables. Never inserts test data:
```python
@app.get("/health")
async def health_probe():
    """External monitoring endpoint (Healthchecks.io). Pure reads, no writes."""
    checks = {}
    
    # DB connectivity (read-only)
    try:
        row = await db.execute_fetchone("SELECT COUNT(*) as c FROM common_members WHERE active=1")
        checks["db"] = {"ok": True, "members": row["c"]}
    except Exception as e:
        checks["db"] = {"ok": False, "error": str(e)}
    
    # Source freshness (read-only)
    for source_name, max_stale_minutes in [("calendar", 30), ("reminders", 15)]:
        row = await db.execute_fetchone(
            "SELECT MAX(last_synced) as ls FROM cal_sources" if source_name == "calendar"
            else "SELECT MAX(fetched_at) as ls FROM cal_raw_events WHERE source_id LIKE ?",
            [f"%{source_name}%"] if source_name != "calendar" else [])
        if row and row["ls"]:
            age = (datetime.utcnow() - datetime.fromisoformat(row["ls"])).total_seconds() / 60
            checks[source_name] = {"ok": age < max_stale_minutes, "age_minutes": round(age, 1)}
        else:
            checks[source_name] = {"ok": False, "error": "no data"}
    
    # Write queue health (in-memory check)
    checks["write_queue"] = {"ok": write_queue._queue.qsize() < 100, "pending": write_queue._queue.qsize()}
    
    all_ok = all(c.get("ok", False) for c in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "healthy" if all_ok else "degraded", "checks": checks}
    )
```

**Approval Queue Auto-Expiry:**
```python
async def expire_approvals(db):
    """Expire pending approvals past their auto_expire_at. Notify if not yet notified."""
    expired = await db.execute_fetchall(
        "SELECT * FROM mem_approval_queue WHERE status='pending' AND auto_expire_at < datetime('now')")
    for row in expired:
        await db.execute(
            "UPDATE mem_approval_queue SET status='expired', decided_at=datetime('now') WHERE id=?",
            [row["id"]])
        if not row["expiry_notification_sent"]:
            await notify_expiry(row)
            await db.execute(
                "UPDATE mem_approval_queue SET expiry_notification_sent=1 WHERE id=?", [row["id"]])
```

### Hardware Failure Plan

The Mac Mini is a single point of failure. When it dies (not if), the family needs to function.

**48-Hour Survival Mode (no PIB):**
- Google Sheets mirror has current tasks, lists, schedule, budget (pushed every 15 min)
- Laura's phone has Google Calendar (already synced independently)
- Twilio number forwards to James's phone when PIB doesn't answer (configured in Twilio console: "if no webhook response in 30 seconds, forward to +1-xxx-xxx-xxxx")
- Printed emergency sheet on fridge: WiFi password, alarm code, vet number, pediatrician, custody schedule
- PIB posts this sheet as a recurring task: "Update fridge emergency sheet" (quarterly)

**Recovery (new Mac Mini):**
1. Order Mac Mini (same day Apple Store or next-day delivery)
2. Restore from Time Machine backup (full environment, all config)
3. Re-sign BlueBubbles → Messages.app (requires manual Apple ID login)
4. Verify Cloudflare Tunnel reconnects (usually automatic after restore)
5. Run `/health` endpoint → verify all adapters green
6. Total downtime: 24-48 hours. Data loss: ≤1 hour (hourly backups to external drive + cloud)

**Cloud backup (belt + suspenders):**
Daily encrypted SQLite backup uploaded to Google Drive via service account. Separate from Time Machine. Survives fire/theft/drive failure.

```python
# Cron: "0 4 * * *" — daily encrypted backup to Google Drive
async def cloud_backup():
    import subprocess
    db_path = "/opt/pib/data/pib.db"
    backup_path = f"/tmp/pib-backup-{date.today().isoformat()}.db.enc"
    
    # SQLite online backup (consistent snapshot)
    subprocess.run(["sqlite3", db_path, f".backup /tmp/pib-backup-raw.db"])
    
    # Encrypt with age (simpler than GPG, no key management headaches)
    subprocess.run(["age", "-r", BACKUP_PUBLIC_KEY, "-o", backup_path, "/tmp/pib-backup-raw.db"])
    
    # Upload to Google Drive backup folder
    await upload_to_drive(backup_path, folder_id=BACKUP_FOLDER_ID)
    
    os.remove("/tmp/pib-backup-raw.db")
    os.remove(backup_path)
```

### Identity Stack Setup Checklist

Every account PIB needs, which tier/plan, and where credentials live.

```
ACCOUNTS (in setup order):

1. Apple ID — pib@yourdomain.com (or dedicated iCloud account)
   □ Create at appleid.apple.com
   □ Enable iMessage + FaceTime
   □ Sign into Mac Mini → Messages.app
   □ RISK: Apple may flag headless usage. Mitigation: occasional manual sign-in.

2. Google Workspace — pib@yourdomain.com
   □ Plan: Google Workspace Starter ($7/user/month) — needed for:
     - Apps Script time-driven triggers (free accounts can't reliably)
     - Google Calendar API with domain-wide delegation
     - Gmail API for push notifications
   □ Enable APIs: Calendar, Sheets, Gmail, Drive
   □ Create service account for server-to-server auth
   □ Download service account key → /opt/pib/config/google-sa-key.json
   □ Set up OAuth for user-facing consent (Cloudflare Access login)

3. Twilio
   □ Create account at twilio.com
   □ Buy local number (Atlanta area code: 404/678/470)
   □ Configure webhook: POST → https://pib.yourdomain.com/webhooks/twilio
   □ Configure fallback: forward to James's phone after 30s timeout
   □ Cost: ~$1.50/month number + $0.0079/SMS

4. Cloudflare
   □ Add domain to Cloudflare (free plan sufficient)
   □ Create Tunnel: cloudflared tunnel create pib
   □ Configure Access: Google OAuth, allow household emails
   □ Routes: /api/*, /webhooks/*, /dashboard, /scoreboard, /health

5. Anthropic
   □ API account at console.anthropic.com
   □ Generate API key → /opt/pib/config/.env (never in code)
   □ Set up billing alerts at $50, $75, $100/month

6. BlueBubbles
   □ Install on Mac Mini from bluebubbles.app
   □ Configure shared secret for webhook auth
   □ Webhook URL: http://localhost:3141/webhooks/bluebubbles
   □ RISK: Breaks on macOS updates. Recovery: re-sign Messages.app.

7. Healthchecks.io (free tier)
   □ Create check for https://pib.yourdomain.com/health
   □ Alert via email + SMS when probe fails

CREDENTIAL STORAGE:
All secrets in /opt/pib/config/.env (chmod 600, owned by pib user):
  ANTHROPIC_API_KEY=sk-ant-...
  TWILIO_ACCOUNT_SID=AC...
  TWILIO_AUTH_TOKEN=...
  GOOGLE_SA_KEY_PATH=/opt/pib/config/google-sa-key.json
  BLUEBUBBLES_SECRET=...
  CLOUDFLARE_TUNNEL_TOKEN=...
  BACKUP_PUBLIC_KEY=age1...
  PIB_SHEETS_WEBHOOK_TOKEN=...

KEY ROTATION SCHEDULE (added to cron: quarterly reminder):
  - Anthropic API key: rotate quarterly
  - Google OAuth refresh token: auto-refreshes (monitor for expiry)
  - Twilio auth token: rotate annually
  - BlueBubbles secret: rotate after macOS updates
  - Cloudflare tunnel token: rotate annually
```

### Monthly Operating Cost

Tracked in `pib_config` and surfaced in the `/dashboard` console:

```
MONTHLY COST ESTIMATE:
  Anthropic API (Sonnet ~90% + Opus ~10%)     $40-50
  Google Workspace Starter                      $7
  Twilio (number + ~200 SMS/month)             $3
  Cloudflare (free tier)                        $0
  Healthchecks.io (free tier)                   $0
  iCloud (for Apple ID, 50GB)                   $1
  Electricity (Mac Mini, ~8W idle)              $2
  ─────────────────────────────────────────
  TOTAL                                        $53-63/month

COST MONITORING:
  - Anthropic: billing alerts at $50/$75/$100
  - Twilio: billing alerts at $10/$25
  - PIB tracks its own API spend via response headers (x-usage)
    and logs to pib_config: "monthly_api_spend_estimate"
  - Monthly cost summary in weekly review digest
```

```python
# Track API spend per request
async def track_api_cost(response_headers: dict, model: str):
    input_tokens = int(response_headers.get("x-usage-input-tokens", 0))
    output_tokens = int(response_headers.get("x-usage-output-tokens", 0))
    
    # Approximate cost (update when pricing changes)
    costs = {
        "sonnet": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
        "opus":   {"input": 15.0 / 1_000_000, "output": 75.0 / 1_000_000},
    }
    tier = "opus" if "opus" in model else "sonnet"
    cost = (input_tokens * costs[tier]["input"]) + (output_tokens * costs[tier]["output"])
    
    # Accumulate in config
    month_key = f"api_spend_{date.today().strftime('%Y_%m')}"
    current = float(get_config(month_key, "0.0"))
    set_config(month_key, str(current + cost))
```

### Model Upgrade Procedure

When Anthropic releases new models (happens ~quarterly):

```
1. UPDATE CONFIG (not code):
   UPDATE pib_config SET value='claude-sonnet-4-5-YYYYMMDD' WHERE key='anthropic_model_sonnet';
   UPDATE pib_config SET value='claude-opus-NEW' WHERE key='anthropic_model_opus';

2. TEST (before deploying to production):
   □ Run test suite — all tools still return expected shapes
   □ Send 10 representative queries, compare quality
   □ Check token usage — new models may have different pricing
   □ Verify streaming still works (API changes occasionally)
   □ Update cost estimates in pib_config if pricing changed

3. ROLLBACK (if new model degrades quality):
   UPDATE pib_config SET value='claude-sonnet-4-5-20250929' WHERE key='anthropic_model_sonnet';
   — takes effect on next request, no restart needed

4. DEPRECATION MONITOR:
   □ Proactive trigger: weekly check of Anthropic status page
   □ If API returns "model not found" → auto-fallback to previous model ID stored in
     pib_config key "anthropic_model_sonnet_previous"
```

### Migration Framework

Up/down migrations stored in `meta_migrations` table (defined in schema). File convention:

```
/opt/pib/migrations/
├── 001_initial_schema.sql      # Bootstrap — all CREATE TABLE statements
├── 002_add_energy_states.sql
├── 003_add_pib_config.sql
└── ...
```

```python
import hashlib

async def migrate_up(db, target_version: int = None):
    """Apply pending migrations in order."""
    current = await db.execute_fetchone("SELECT MAX(version) as v FROM meta_migrations WHERE applied_at IS NOT NULL")
    current_version = current["v"] or 0
    
    migration_files = sorted(glob("/opt/pib/migrations/*.sql"))
    for f in migration_files:
        version = int(os.path.basename(f).split("_")[0])
        if version <= current_version:
            continue
        if target_version and version > target_version:
            break
        
        content = open(f).read()
        # Split on "-- DOWN" marker
        parts = content.split("-- DOWN")
        up_sql = parts[0].strip()
        down_sql = parts[1].strip() if len(parts) > 1 else "-- no rollback defined"
        checksum = hashlib.sha256(up_sql.encode()).hexdigest()
        
        await db.executescript(up_sql)
        await db.execute(
            "INSERT INTO meta_migrations (version, name, up_sql, down_sql, applied_at, checksum) "
            "VALUES (?, ?, ?, ?, datetime('now'), ?)",
            [version, os.path.basename(f), up_sql, down_sql, checksum])
        log.info(f"Migration {version} applied: {os.path.basename(f)}")

async def migrate_down(db, target_version: int):
    """Rollback migrations down to target version."""
    migrations = await db.execute_fetchall(
        "SELECT * FROM meta_migrations WHERE version > ? AND applied_at IS NOT NULL "
        "ORDER BY version DESC", [target_version])
    for m in migrations:
        await db.executescript(m["down_sql"])
        await db.execute(
            "UPDATE meta_migrations SET rolled_back_at = datetime('now') WHERE version = ?",
            [m["version"]])
        log.info(f"Migration {m['version']} rolled back: {m['name']}")
```

Migration file format:
```sql
-- 002_add_energy_states.sql
-- UP
CREATE TABLE IF NOT EXISTS pib_energy_states (...);
CREATE INDEX ...;
INSERT INTO pib_config (key, value) VALUES ('velocity_cap_default', '15');

-- DOWN
DROP TABLE IF EXISTS pib_energy_states;
DELETE FROM pib_config WHERE key = 'velocity_cap_default';
```

---

### 13.1 Project Layout

```
/opt/pib/
├── src/pib/           # Source code
│   ├── __init__.py
│   ├── db.py          # WriteQueue, migrations
│   ├── engine.py      # whatNow(), compute_energy_level
│   ├── ingest.py      # Pipeline, adapters, prefix parser
│   ├── llm.py         # System prompt, tools, conversation flow
│   ├── proactive.py   # Triggers, guardrails
│   ├── memory.py      # Dedup, supersession, auto-promote
│   ├── sheets.py      # Push sync, webhook handler, import
│   ├── custody.py     # who_has_child, daily state
│   ├── rewards.py     # Variable-ratio, streaks, velocity
│   └── web.py         # FastAPI app, dashboard, scoreboard
├── tests/
│   ├── conftest.py    # Shared fixtures: in-memory DB, seed data
│   ├── test_what_now.py
│   ├── test_custody.py         # 20+ cases including DST
│   ├── test_state_machine.py
│   ├── test_prefix_parser.py
│   ├── test_ingest_pipeline.py
│   ├── test_memory_dedup.py
│   ├── test_rewards.py
│   ├── test_energy.py
│   ├── test_streaks.py
│   └── test_privacy_fence.py   # Invariant 5: privileged data never leaks
├── pyproject.toml
└── pytest.ini
```

### 13.2 pytest Configuration

```ini
# pytest.ini
[pytest]
testpaths = tests
asyncio_mode = auto
markers =
    unit: Pure function tests (no DB, no network)
    integration: Database tests (in-memory SQLite)
    e2e: End-to-end with real adapters
```

```toml
# pyproject.toml (relevant section)
[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["src/pib"]
```

### 13.3 Test Fixtures

```python
# tests/conftest.py
import pytest
import aiosqlite
from pib.db import apply_migrations

@pytest.fixture
async def db():
    """In-memory SQLite database with full schema + seed data."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await apply_migrations(conn)
        await seed_test_data(conn)
        yield conn

@pytest.fixture
def snapshot(db):
    """Pre-loaded DBSnapshot for whatNow() tests."""
    return DBSnapshot(
        tasks=[...],  # Standard test task set
        daily_state=mock_daily_state(),
        energy_state=mock_energy_state(),
        members=SEED_MEMBERS,
        streaks={"m-james": {"current_streak": 5, "best_streak": 12}},
    )
```

### 13.4 Critical Test Cases

```python
# Custody DST — 20 cases minimum
@pytest.mark.parametrize("query_date,expected_parent", [
    ("2026-03-08", "m-james"),    # Day before spring forward
    ("2026-03-09", "m-james"),    # Spring forward (23h day)
    ("2026-11-01", "m-laura-ex"), # Day before fall back
    ("2026-11-02", "m-james"),    # Fall back (25h day)
])
async def test_custody_dst(query_date, expected_parent, custody_config):
    assert who_has_child(date.fromisoformat(query_date), custody_config) == expected_parent

# ─── PRIVACY FENCE — Invariant 5 (comprehensive) ───

# Canary: distinctive string that should NEVER appear in any output
PRIVACY_CANARY = "CANARY_XJ7_PRIVILEGED_LEAK_DETECTOR"

@pytest.fixture
async def db_with_privileged_events(db):
    """Seed privileged calendar events with canary strings."""
    await db.execute("""
        INSERT INTO cal_classified_events 
        (id, source_id, event_date, start_time, end_time, title, description,
         privacy, title_redacted, for_member_ids)
        VALUES 
        ('priv-1', 'laura-work-cal', '2026-03-03', '14:00', '16:00',
         'Johnson v. Johnson Deposition ' || ?,
         'Prepare exhibits A-F, witness list, ' || ?,
         'privileged', 'Laura — Meeting', '["m-laura"]'),
        ('priv-2', 'laura-work-cal', '2026-03-04', '09:00', '10:00',
         'Smith Custody Mediation ' || ?,
         'Client prep call with guardian ad litem ' || ?,
         'redacted', 'Laura — unavailable', '["m-laura"]'),
        ('full-1', 'family-cal', '2026-03-03', '18:00', '19:00',
         'Family Dinner', 'Pick up pasta',
         'full', 'Family Dinner', '["m-james","m-laura"]')
    """, [PRIVACY_CANARY] * 4)
    return db

async def test_privileged_title_never_in_context(db_with_privileged_events):
    """No privileged event title appears in ANY assembled context."""
    context = await build_calendar_context(
        db_with_privileged_events, DateRange("2026-03-01", "2026-03-07"), "m-james")
    assert "Johnson" not in context
    assert "Deposition" not in context
    assert "Smith Custody" not in context
    assert "guardian ad litem" not in context
    assert PRIVACY_CANARY not in context
    # Full events DO appear
    assert "Family Dinner" in context

async def test_privileged_description_never_in_context(db_with_privileged_events):
    """No privileged event DESCRIPTION appears in any context."""
    context = await build_calendar_context(
        db_with_privileged_events, DateRange("2026-03-01", "2026-03-07"), "m-james")
    assert "exhibits" not in context
    assert "witness list" not in context
    assert "guardian" not in context

async def test_canary_never_in_any_output(db_with_privileged_events):
    """Canary string must not appear in ANY system output path."""
    # Calendar context
    cal_ctx = await build_calendar_context(
        db_with_privileged_events, DateRange("2026-03-01", "2026-03-07"), "m-james")
    assert PRIVACY_CANARY not in cal_ctx
    
    # Cross-domain summary
    summary = await build_cross_domain_summary(db_with_privileged_events)
    assert PRIVACY_CANARY not in summary
    
    # Full assembled context (all assemblers)
    full_ctx = await assemble_all(
        db_with_privileged_events, "m-james",
        QueryRelevance(assemblers=["schedule","tasks","financial","coverage"], matched_entities=[]))
    assert PRIVACY_CANARY not in str(full_ctx)
    
    # Morning digest
    digest = await compose_morning_digest(db_with_privileged_events, "m-james")
    assert PRIVACY_CANARY not in str(digest)

async def test_tool_results_filter_privileged(db_with_privileged_events):
    """Tool call results (query_schedule, etc.) also filter privileged content."""
    result = await execute_tool(
        db_with_privileged_events, "query_schedule",
        {"start_date": "2026-03-01", "end_date": "2026-03-07"},
        "m-james")
    result_str = json.dumps(result)
    assert PRIVACY_CANARY not in result_str
    assert "Johnson" not in result_str
    assert "Laura — Meeting" in result_str or "Laura — unavailable" in result_str

async def test_privileged_data_filtered_for_all_actors(db_with_privileged_events):
    """Privacy applies regardless of which actor is requesting."""
    for member_id in ["m-james", "m-laura", "m-charlie"]:
        context = await build_calendar_context(
            db_with_privileged_events, DateRange("2026-03-01", "2026-03-07"), member_id)
        assert PRIVACY_CANARY not in context

# whatNow() determinism
async def test_what_now_is_deterministic(snapshot):
    """Same inputs MUST produce same output. No randomness in task selection."""
    result1 = what_now("m-james", snapshot)
    result2 = what_now("m-james", snapshot)
    assert result1.the_one_task["id"] == result2.the_one_task["id"]
```

### 13.5 Date Format Reference (for CHECK constraints)

All `TEXT` date/datetime columns use ISO 8601. The CHECK constraint `date(col) IS NOT NULL` validates format. Here's the cheat sheet for CLI/manual inserts:

```
Date only:     2026-03-15              → CHECK passes
Datetime UTC:  2026-03-15T14:30:00Z    → CHECK passes (date() extracts date part)
Datetime tz:   2026-03-15T10:30:00-04:00 → CHECK passes
Time only:     14:30                   → CHECK FAILS (not a date)
US format:     03/15/2026              → CHECK FAILS (SQLite doesn't parse this)
Empty string:  ""                      → CHECK FAILS
NULL:          NULL                    → CHECK passes (IS NULL OR ... pattern)
```

Always use `YYYY-MM-DD` for dates and `YYYY-MM-DDTHH:MM:SSZ` for datetimes.

---

## APPENDIX: SEED DATA

```python
MEMBERS = [
    {"id": "m-james", "display_name": "James", "role": "parent",
     "can_be_assigned_tasks": 1, "can_receive_messages": 1,
     "preferred_channel": "imessage", "view_mode": "carousel",
     "digest_mode": "full", "velocity_cap": 15,
     "energy_markers": '{"peak_hours":["09:00-12:00"],"crash_hours":["14:00-16:00"]}',
     "medication_config": '{"name":"Adderall","typical_dose_time":"07:30","peak_onset_minutes":60,"peak_duration_minutes":240,"crash_onset_minutes":300}'},
    {"id": "m-laura", "display_name": "Laura", "role": "parent",
     "can_be_assigned_tasks": 1, "can_receive_messages": 1,
     "preferred_channel": "imessage", "view_mode": "compressed",
     "digest_mode": "compressed", "velocity_cap": 20},
    {"id": "m-charlie", "display_name": "Charlie", "role": "child",
     "is_adult": 0, "age": 6, "view_mode": "child",
     "capabilities": '{"can_stay_home_alone":false,"needs_car_seat":false}'},
    {"id": "m-baby", "display_name": "Baby Girl", "role": "child",
     "is_adult": 0, "expected_arrival": "2026-05-15",
     "capabilities": '{"needs_constant_supervision":true}'},
]

CAPTAIN_ITEM = {
    "id": "i-captain", "name": "Captain", "type": "pet",
    "category": "household", "domain": "household",
    "metadata": '{"species":"dog","breed":"unknown","vet":"Peachtree Vet","meds_monthly":true}'
}

COACH_PROTOCOLS = [...]  # See Section 5.4

LIFE_PHASES = [
    {"id": "phase-pre-baby", "name": "Pre-Baby Prep", "status": "active",
     "start_date": "2026-02-01", "end_date": "2026-05-15",
     "description": "Preparing for baby arrival. Nesting mode.",
     "overrides": '{"suppress_crm_nudges":false,"max_new_tasks_per_day":8}'},
    {"id": "phase-newborn", "name": "Newborn Survival", "status": "pending",
     "start_date": "2026-05-15", "end_date": "2026-08-15",
     "description": "First 3 months. Survival mode.",
     "overrides": '{"suppress_crm_nudges":true,"digest_mode":"minimal","velocity_cap_override":5,"max_proactive_per_day":2}'},
    {"id": "phase-infant", "name": "Infant", "status": "pending",
     "start_date": "2026-08-15", "end_date": "2027-05-15",
     "description": "3-12 months. Restore velocity, add pediatrician recurring.",
     "overrides": '{"velocity_cap_override":10,"max_proactive_per_day":4}'},
    {"id": "phase-toddler", "name": "Toddler", "status": "pending",
     "start_date": "2027-05-15", "end_date": "2029-05-15",
     "description": "12-36 months. Childproofing, nap tracking, routine adjustments.",
     "overrides": '{}'},
]

PIB_CONFIG_SEED = [
    # Model management
    {"key": "anthropic_model_sonnet", "value": "claude-sonnet-4-5-20250929", "description": "Default model for routine queries"},
    {"key": "anthropic_model_opus", "value": "claude-opus-4-6", "description": "Escalation model for complex synthesis"},
    {"key": "anthropic_model_sonnet_previous", "value": "claude-sonnet-4-5-20250514", "description": "Fallback if current model deprecated"},
    {"key": "anthropic_model_opus_previous", "value": "claude-opus-4-5-20250918", "description": "Fallback if current model deprecated"},
    
    # Cost tracking
    {"key": "monthly_api_budget_alert", "value": "75.00", "description": "Alert when monthly API spend exceeds this"},
    
    # Charlie gamification
    {"key": "charlie_star_milestone_25", "value": "Pick Friday movie", "description": "Reward at 25 stars"},
    {"key": "charlie_star_milestone_50", "value": "Choose weekend activity", "description": "Reward at 50 stars"},
    {"key": "charlie_star_milestone_100", "value": "Special outing with parent", "description": "Reward at 100 stars"},
    
    # Household
    {"key": "household_timezone", "value": "America/New_York", "description": "Atlanta timezone for all date math"},
    {"key": "emergency_contacts", "value": '{"vet":"Peachtree Vet (404) 555-0111","pediatrician":"Dr. Chen (404) 555-0222","poison_control":"1-800-222-1222"}'},
    
    # Key rotation reminders (dates of last rotation)
    {"key": "last_rotated_anthropic_key", "value": "2026-02-27", "description": "Quarterly rotation"},
    {"key": "last_rotated_twilio_token", "value": "2026-02-27", "description": "Annual rotation"},
]

# Role-based visibility matrix (enforced at read layer)
ROLE_VISIBILITY = {
    "parent":      {"tasks", "schedule", "finance", "health", "custody", "memory", "household"},
    "child":       {"scoreboard"},
    "coparent":    {"custody", "child_schedule", "handoff_tasks"},
    "nanny":       {"assigned_tasks", "child_schedule", "pet_care", "emergency_contacts"},
    "babysitter":  {"assigned_tasks", "child_schedule", "pet_care", "emergency_contacts"},
    "grandparent": {"household_schedule", "child_info", "meal_preferences", "emergency_contacts"},
    "dog_walker":  {"pet_care"},
    "other":       {"assigned_tasks"},
}
```

---

*Built to pass this test: "Does this reduce the executive function cost for someone whose PFC is running at 70-80% capacity?" If it adds complexity the user has to manage, it fails. If it adds complexity the SYSTEM manages on the user's behalf, it passes.*
