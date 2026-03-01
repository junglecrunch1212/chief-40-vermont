# PIB v5 Console → Backend API Contract

Every endpoint the wired console calls. Backend must return these shapes exactly.
All endpoints relative to same origin (Express serves both API and static console).

---

## SHELL (sidebar)

### `GET /api/tasks?filter=inbox`
Returns inbox count for nav badge.
```json
{ "tasks": [{ "id": "t-010", ... }] }
```

### `GET /api/custody/today`
```json
{ "text": "Charlie with James today", "with": "m-james", "overnight": "m-james" }
```

### `GET /api/health`
Polled every 5 minutes for sidebar health pulse + Settings health tab.
```json
{
  "status": "healthy",
  "uptime": 482,
  "checks": {
    "database": { "ok": true },
    "bluebubbles": { "ok": true, "age": 2.1 },
    "calendar_sync": { "ok": true, "age": 8.3 },
    "twilio": { "ok": true },
    "write_queue": { "ok": true, "pending": 0 },
    "sheets_sync": { "ok": true, "age": 4.7 }
  },
  "backups": { "hourly": "12:00 PM", "daily": "4:00 AM" },
  "dbSize": "148 MB",
  "keyRotation": { "anthropic": "43 days ago", "twilio": "43 days" }
}
```

---

## TODAY — James (TodayJames)

### `GET /api/today-stream?member=m-james`
Server builds unified stream: endowed items + calendar events + tasks sorted by whatNow().
```json
{
  "stream": [
    { "id": "endowed-1", "type": "endowed", "title": "Woke up", "label": "Woke up ✓", "state": "done" },
    { "id": "endowed-2", "type": "endowed", "title": "Opened PIB", "label": "Opened PIB ✓", "state": "done" },
    { "id": "cal-07:30", "type": "calendar", "title": "Medication window", "time": "07:30", "end": "07:45", "label": "07:30 Medication window", "state": "done" },
    { "id": "t-003", "type": "task", "title": "Pay electric bill", "label": "Pay electric bill", "state": "done",
      "task": { "id": "t-003", "domain": "finance", "effort": "tiny", "points": 1, "micro": null } },
    { "id": "t-001", "type": "task", "title": "Call roofer", "label": "Call roofer", "state": "pending", "urgent": true,
      "task": { "id": "t-001", "domain": "household", "effort": "small", "points": 3, "micro": "Pick up phone → call Dan..." } },
    { "id": "cal-15:30", "type": "calendar", "title": "Charlie pickup", "time": "15:30", "end": "16:00", "label": "15:30 Charlie pickup", "state": "pending" }
  ],
  "activeIdx": 4,
  "energy": {
    "level": "high", "sleep": "great", "meds": true, "meds_at": "7:32 AM",
    "completions": 6, "cap": 15, "focus": false
  },
  "streak": { "current": 12, "best": 18, "grace": 2 },
  "summary": "Charlie's with you today. Laura's in depositions until 4."
}
```

### `POST /api/tasks/{id}/complete`
Server rolls reward dice (60/25/10/5 distribution), updates streak, logs undo.
```json
// Request
{ "member": "m-james" }

// Response
{
  "reward_tier": "warm",
  "reward_message": "That's momentum. Keep it rolling.",
  "streak": { "current": 13, "best": 18, "grace": 2 },
  "next_active_idx": 5,
  "receipt_id": "rcpt-2743"
}
```

### `POST /api/tasks/{id}/skip`
```json
// Request
{ "reschedule_date": "2026-02-28" }   // optional

// Response
{ "ok": true, "receipt_id": "rcpt-2744" }
```

---

## TODAY — Laura (TodayLaura)

### `GET /api/decisions?member=m-laura`
```json
{
  "decisions": [
    { "id": "d-001", "title": "Approve babysitter for Saturday", "detail": "$85 · Megan · 5–10 PM", "status": "pending" },
    { "id": "d-002", "title": "Charlie field trip: sign permission form", "detail": "Zoo trip · Due Thursday", "status": "pending" }
  ]
}
```

### `POST /api/approvals/{id}/decide`
```json
// Request
{ "decision": "approved" }   // or "rejected"

// Response
{ "ok": true, "receipt_id": "rcpt-2745" }
```

### `GET /api/tasks?assignee=m-laura&status=ready`
```json
{ "tasks": [{ "id": "t-006", "title": "Schedule pediatrician", "domain": "health", ... }] }
```

### `GET /api/household-status`
```json
{
  "items": [
    { "icon": "✅", "text": "James: 6 tasks done — energy high", "color": "var(--tx2)" },
    { "icon": "⭐", "text": "Charlie: 2/5 chores done", "color": "var(--tx2)" },
    { "icon": "⚠️", "text": "Dining budget at 82% — $54 remaining", "color": "var(--warn)" },
    { "icon": "🐕", "text": "Captain: walked ✓ · fed ✓ · next walk 6 PM", "color": "var(--tx2)" },
    { "icon": "👶", "text": "Baby arrival: 77 days", "color": "var(--pink)" }
  ]
}
```

---

## TODAY — Charlie (TodayCharlie)

### `GET /api/chores?member=m-charlie`
```json
{
  "chores": [
    { "id": "ch-1", "title": "Made bed", "done": true, "stars": 2 },
    { "id": "ch-2", "title": "Put dishes in sink", "done": true, "stars": 1 },
    { "id": "ch-3", "title": "Put away backpack", "done": false, "stars": 2 }
  ]
}
```

### `POST /api/chores/{id}/toggle`
```json
{ "ok": true, "done": true, "stars_today": 3, "stars_week": 26 }
```

### `GET /api/scoreboard?member=m-charlie`
```json
{ "weekStars": 24, "streak": { "current": 4, "best": 7, "grace": 1 }, "nextMilestone": "Pick Friday movie", "nextMilestoneTarget": 25 }
```

---

## TASKS PAGE

### `GET /api/tasks?filter={all|mine|inbox|overdue|waiting|done}`
Server handles filtering, sorting by whatNow() score.
```json
{
  "tasks": [{
    "id": "t-001", "title": "Call roofer about leak estimate",
    "status": "ready", "assignee": "m-james", "due": "2026-02-27",
    "energy": "medium", "effort": "small", "domain": "household",
    "points": 3, "score": 740
  }]
}
```

---

## SCHEDULE PAGE

### `GET /api/schedule?date=2026-02-27`
Server applies privacy filtering (Laura's work calendar → redacted if viewer ≠ Laura).
```json
{
  "events": [
    { "time": "07:30", "end": "07:45", "title": "Medication window", "member": "m-james", "type": "routine" },
    { "time": "09:00", "end": "10:00", "title": "Laura — partner call", "member": "m-laura", "type": "calendar" }
  ],
  "custody": "👦 Custody: Charlie with James · Overnight: James"
}
```

---

## LISTS PAGE

### `GET /api/lists/{list_name}`
```json
{
  "items": [
    { "id": "g1", "text": "Whole milk (gallon)", "done": false },
    { "id": "g2", "text": "Eggs (18 ct)", "done": false }
  ],
  "available_lists": [
    { "id": "grocery", "label": "🛒 Grocery" },
    { "id": "honey-do", "label": "🔨 Honey-Do" },
    { "id": "packing", "label": "👶 Baby Packing" }
  ]
}
```

### `POST /api/lists/{list_name}/items`
```json
// Request
{ "text": "Oat milk" }

// Response
{ "id": "g8", "text": "Oat milk", "done": false }
```

### `POST /api/lists/{list_name}/items/{id}/toggle`
```json
{ "ok": true, "done": true }
```

---

## CHAT PAGE

### `POST /api/chat/send`
```json
{ "message": "Who has Charlie today?", "session_id": "sess-1234567890" }
```

### `GET /api/chat/stream?session_id=sess-1234567890` (SSE)
Server-Sent Events stream. Each event:
```
data: {"token": "Charlie"}
data: {"token": " is"}
data: {"token": " with"}
...
data: {"done": true}
```
Or non-streaming fallback:
```
data: {"content": "Charlie is with you today. Drop-off was at 8:15, pickup at 3:30."}
```

### `GET /api/chat/history?session_id=sess-1234567890`
```json
{
  "messages": [
    { "role": "user", "content": "Who has Charlie today?", "ts": "9:15 AM" },
    { "role": "assistant", "content": "Charlie is with you today...", "ts": "9:15 AM" }
  ]
}
```

---

## SCOREBOARD PAGE

### `GET /api/scoreboard`
Polled every 60 seconds.
```json
{
  "cards": [
    { "id": "m-james", "name": "James", "emoji": "💪", "done": 6, "wk": 840,
      "streak": { "current": 12, "best": 18, "grace": 2 } },
    { "id": "m-laura", "name": "Laura", "emoji": "⚖️", "done": 2, "wk": 540,
      "streak": { "current": 8, "best": 14, "grace": 2 } },
    { "id": "m-charlie", "name": "Charlie", "emoji": "🌟", "done": 2, "wk": 24, "star": true,
      "streak": { "current": 4, "best": 7, "grace": 1 } }
  ],
  "layers": [
    { "name": "Memory", "score": 58 }, { "name": "Time", "score": 26 },
    { "name": "Initiation", "score": 26 }, { "name": "Attention", "score": 9 },
    { "name": "Transition", "score": 17 }, { "name": "Emotional", "score": 21 },
    { "name": "Proactive", "score": 39 }
  ],
  "overallScore": 28,
  "rewardHistory": [
    { "tier": "simple", "msg": "Done.", "ts": "2:22 PM" },
    { "tier": "warm", "msg": "Solid. You're in a groove.", "ts": "1:45 PM" }
  ],
  "domainWins": [
    { "d": "Household", "n": 12, "trend": "↑" },
    { "d": "Health", "n": 8, "trend": "↑" },
    { "d": "Finance", "n": 3, "trend": "→", "warn": "⚠️ 6 deferrals" }
  ],
  "captain": { "walked": true, "fed": true, "nextWalk": "6:00 PM" },
  "familyTotal": { "points": 1404, "record": true },
  "chores": [
    { "id": "ch-1", "title": "Made bed", "done": true, "stars": 2 },
    { "id": "ch-2", "title": "Put dishes in sink", "done": true, "stars": 1 }
  ]
}
```

---

## PEOPLE PAGE

### `GET /api/people/contacts`
```json
{
  "contacts": [
    { "id": "p1", "name": "Dan (Roofer)", "type": "vendor", "last": "2026-02-10", "days": 17, "ghost": true, "phone": "(404) 555-0142" }
  ]
}
```

### `GET /api/people/comms?limit=20`
```json
{
  "comms": [
    { "person": "Dan (Roofer)", "ch": "SMS", "dir": "out", "msg": "Hey Dan, checking on...", "ts": "Feb 27, 9:42 AM" }
  ]
}
```

### `GET /api/people/observations`
```json
{
  "observations": [
    { "person": "Dan (Roofer)", "note": "Tends to ghost after estimates...", "ts": "2026-02-12" }
  ]
}
```

### `GET /api/people/autonomy-tiers`
```json
{
  "tiers": [
    { "action": "Read calendar", "level": "Autonomous", "desc": "Do it, log receipt" },
    { "action": "Send iMessage reminder", "level": "Autonomous", "desc": "Within quiet hours policy" },
    { "action": "Delete task/record", "level": "Blocked", "desc": "Not permitted" }
  ]
}
```

---

## SETTINGS PAGE

### `GET /api/costs`
```json
{
  "total": "$54.12",
  "items": [
    { "name": "Anthropic API", "amt": "$41.27", "note": "Feb to date" },
    { "name": "Google Workspace", "amt": "$7.00" }
  ],
  "apiSpend": "$41.27", "apiThreshold": "$75.00", "apiPct": 55,
  "smsCount": 189, "imessageCount": "~420", "webChatCount": "~85", "nudgeCount": "~62"
}
```

### `GET /api/config/models`
```json
{
  "models": [
    { "key": "anthropic_model_sonnet", "tier": "Routine (Sonnet)", "val": "claude-sonnet-4-5-20250929", "pct": "~90% of requests" },
    { "key": "anthropic_model_opus", "tier": "Complex (Opus)", "val": "claude-opus-4-6", "pct": "~10% of requests" }
  ]
}
```

### `GET /api/sources`
```json
{
  "sources": [
    { "id": "laura-work-cal", "type": "Google Calendar", "name": "Laura's Work Calendar", "relevance": "blocks_member", "privacy": "privileged", "authority": "authoritative" }
  ]
}
```

### `GET /api/phases`
```json
{
  "phases": [
    { "id": "ph-1", "name": "Pre-Baby Prep", "status": "active", "start": "Feb 1", "end": "May 15", "desc": "Nesting mode. velocity_cap: 12", "cap": 12 }
  ]
}
```

### `GET /api/config`
```json
{
  "config": [
    { "key": "anthropic_model_sonnet", "val": "claude-sonnet-4-5-20250929", "desc": "Routine queries" },
    { "key": "household_timezone", "val": "America/New_York", "desc": "Atlanta" }
  ]
}
```

### `POST /api/config/{key}`
```json
// Request
{ "value": "America/Chicago" }

// Response
{ "ok": true, "key": "household_timezone", "value": "America/Chicago" }
```

### `GET /api/budget`
```json
{
  "categories": [
    { "cat": "Groceries", "target": 800, "spent": 612, "icon": "🛒" },
    { "cat": "Dining", "target": 300, "spent": 246, "icon": "🍽️", "warn": true }
  ]
}
```

---

## Standalone Routes

### `#scoreboard` or `#/scoreboard`
Renders ScoreboardPage full-screen with dark background (#1A1714), no sidebar.
For TV display. Uses same `GET /api/scoreboard` with 60s polling.

---

## Error Handling

All endpoints return standard error shape on failure:
```json
{ "error": "not_found", "message": "Task t-999 not found" }
```

Console implements Layer 1 degradation: on API failure, shows last-known data with
amber "⚠️ Showing cached data — connection to backend lost" banner.

## Auth

No auth tokens in v5 — single-household, local network. Express serves console
and API on same port. Future: add bearer token for remote access.
