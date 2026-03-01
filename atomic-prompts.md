# Comms Domain Integration — Atomic Prompt Sequence

## How to Use This

Each prompt is one unit of work. Run them in order. After each, verify the acceptance criteria before moving to the next. If one fails, redo only that one — nothing downstream is affected until you explicitly depend on it.

**Estimated total:** 16 prompts, ~3-4 hours with verification. Compare to the 2 monolithic prompts which would have taken ~2 hours but produced unverifiable output.

**Files required in context for all prompts:**
- `pib-v5-build-spec.md` (the existing build spec)
- `pib-comms-domain-spec.md` (Section 14)
- `comms-integration-analysis.md` (original analysis)
- `voice-intelligence-analysis.md` (voice corpus analysis)

---

## PHASE A: STANDALONE ADDITIONS (no existing files modified)

These create new files. Nothing existing is touched. Zero risk of content drift.

---

### Prompt A1: Section 14 Append

```
Append the contents of pib-comms-domain-spec.md to the end of pib-v5-build-spec.md 
as Section 14. 

Do not modify any existing content in the build spec. This is a pure append 
operation. Add a "---" horizontal rule separator before the new section, consistent 
with how all other sections are separated.

Verify the section numbering is 14 (the current last section is 13).

Output: the updated pib-v5-build-spec.md with Section 14 appended.
```

**Accept when:** Section 14 is present and complete. Sections 1-13 are byte-identical to the original. Verify by diffing everything above the `---` separator — it should be zero changes.

---

### Prompt A2: Migration Files

```
From the schema definitions in Section 14.1 Step 1 of pib-v5-build-spec.md, 
produce two standalone SQL migration files:

FILE 1: migrations/003_comms_enhancement.sql
- Header comment with migration name, date, description
- -- up_sql: section containing all ALTER TABLE ops_comms ADD COLUMN statements 
  and all new CREATE INDEX statements from Section 14.1
- -- down_sql: section with the SQLite table rebuild pattern to remove added columns, 
  plus DROP INDEX for each new index
- Checksum placeholder: -- checksum: {SHA256 of up_sql section}

FILE 2: migrations/004_voice_intelligence.sql  
- Header comment
- -- up_sql: CREATE TABLE cos_voice_corpus and cos_voice_profiles with all columns, 
  constraints, and indexes from Section 14.1
- -- down_sql: DROP TABLE IF EXISTS for both tables and their indexes
- Checksum placeholder

Both files must be valid SQLite SQL. Every statement must end with a semicolon. 
Use IF NOT EXISTS / IF EXISTS guards on all CREATE/DROP operations.

Output: two files.
```

**Accept when:** Both files parse as valid SQL. Running `up_sql` against a fresh database with the existing schema succeeds. Running `down_sql` after `up_sql` returns the database to its pre-migration state. Test with: `sqlite3 :memory: < 001_initial_schema.sql < 003_comms_enhancement.sql` then verify columns exist.

---

### Prompt A3: Apple Voice Notes Adapter Spec

```
Design the Apple Voice Notes adapter for PIB v5. This source is not covered in 
Section 14 and must be designed from scratch following the existing adapter protocol 
pattern (Section 6.1 of the build spec).

Produce a single specification document: apple-voice-notes-adapter.md

Cover:
1. SOURCE DESCRIPTION: Apple Voice Memos recorded on iPhone sync to iCloud and 
   appear on the Mac Mini at ~/Library/Group Containers/
   group.com.apple.VoiceMemos.shared/Recordings/ as .m4a files. New recordings 
   appear within 1-5 minutes of iCloud sync.

2. ADAPTER DESIGN:
   - File system watcher using watchdog (Python) on the Recordings directory
   - On new .m4a file detected: debounce 10 seconds (iCloud may still be writing), 
     verify file size is stable, then process
   - Transcription: Whisper API (OpenAI) as primary. Specify fallback to local 
     whisper.cpp (already viable on Apple Silicon Mac Mini, ~1GB model). 
     Cost comparison: Whisper API ~$0.006/min vs local = free but slower (~2x realtime)
   - Config key: voice_notes_transcription_engine = "whisper_api" | "whisper_local"

3. INGESTION:
   - IngestEvent with source="apple_voice_notes", comm_type="recording_summary"
   - Idempotency key: SHA256(voice_memo:{filename}:{file_size}:{mtime})
     Use file_size in the key because mtime alone can be unreliable with iCloud sync
   - Text = transcription result. Subject = filename (which Apple sets to date/time)
   - member_id = "m-james" (only James records voice notes)

4. FOUR LABELS (Gene 2):
   - relevance: awareness
   - ownership: member (James)
   - privacy: full
   - authority: hybrid

5. PIPELINE INTEGRATION:
   - Transcription text enters the async extraction worker (Section 14.2) like 
     any other comm — tasks, events, entities can be proposed
   - Transcription text ALSO feeds cos_voice_corpus as a voice sample with 
     channel="voice_note". This is valuable: spoken style reveals explanation 
     patterns, reasoning chains, and vocabulary that messaging doesn't capture
   - Original .m4a file is NOT stored in SQLite. Only the transcription text. 
     The file remains in Apple's Voice Memos directory as the source of truth

6. LAYER DEGRADATION:
   - Layer 2 (Enhanced): Whisper API available → full transcription + extraction
   - Layer 1.5: Whisper API down, local whisper available → slower transcription, 
     still works
   - Layer 1 (Core): Both unavailable → file logged in ops_comms with 
     body_snippet="[Voice note — transcription pending]", 
     extraction_status="pending". Retried on next cron cycle.

7. SIRI INTEGRATION:
   - "Hey Siri, record a voice note" → Apple Voice Memos → iCloud sync → 
     Mac Mini filesystem watcher → auto-ingested
   - Zero new infrastructure. The Siri Shortcut for PIB capture is separate — 
     that sends text via webhook. This catches audio recordings natively.

8. RISKS:
   - iCloud sync delay (1-5 min, occasionally longer)
   - Voice Memos directory path may change with macOS updates
   - Whisper transcription quality varies with background noise
   - Cost: Whisper API at 10 notes/day × 2 min avg = $0.12/day = ~$3.60/month

9. ADAPTER PROTOCOL IMPLEMENTATION:
   - init(): Start watchdog observer on Recordings directory
   - poll(): List .m4a files modified in last hour, check against idempotency keys
   - ping(): Verify directory exists and is readable
   - send(): N/A — voice notes are inbound only
   - register_webhooks(): N/A — filesystem watcher, not webhook

Do NOT include code. This is a spec document. Code comes at build time.
```

**Accept when:** The spec is self-contained, follows all nine Genes, and the adapter protocol is complete. Verify that the idempotency key pattern is collision-resistant. Verify the layer degradation path doesn't lose data.

---

## PHASE B: BUILD SPEC SECTION EDITS (targeted, one section at a time)

Each prompt modifies ONE section of the build spec. The edit instructions are specific enough to be mechanically applied. After each, diff the output against the previous version — only the targeted section should have changes.

---

### Prompt B1: Section 2 — Nine Genes Updates

```
Edit ONLY Section 2 of pib-v5-build-spec.md. Do not modify any other section.

Make these specific additions:

GENE 2 (The Vocabulary / Four Labels):
In the source classification table, add these rows:

| Source | Relevance | Ownership | Privacy | Authority |
| whatsapp | awareness | member | full | hybrid |
| outlook_laura_work | blocks_member | member | privileged | human_managed |
| apple_voice_notes | awareness | member | full | hybrid |
| manual_capture | awareness | shared | full | human_managed |

Add a note after the Outlook row: "Mirrors work calendar treatment exactly. 
Content NEVER enters context. PIB stores only: sender name, timestamp, 
subject line (redacted if contains client names), read/unread status."

GENE 3 (Five Shapes):
After the existing shape examples, add a subsection "Comms → Shape Extraction":
- message "Can you call the plumber?" → TASK (title: Call plumber, assignee: james)
- message "Dinner Friday at 7" → EVENT PROPOSAL (not written to calendar — Invariant 3)
- message "Electric bill was $142" → BILL awareness (amount update, not auto-paid)
- message "New pediatrician Dr. Park (404) 555-0300" → ENTITY upsert to ops_items
- message "Add milk, eggs, bread" → LIST ITEMS on grocery list
- message "Piano lessons every Tuesday 4pm" → RECURRING PROPOSAL (queued for approval)
Note: "ALL extractions are proposals. Gene 1 CONFIRM gate governs. 
Nothing auto-creates. See Section 14.2."

GENE 5 (whatNow):
Add one paragraph: "Comms marked needs_response=1 with urgency='urgent' or 
'timely' generate response tasks (type: 'response') that enter whatNow() sort 
via the task_ref bridge on ops_comms. This means 'Reply to Dan about the roof' 
competes fairly in the deterministic sort alongside 'Pay electric bill' — 
no separate mental tracking required."

GENE 6 (Write Layer):
Add to the write path inventory: "Draft-approve-send cycle for CoS-drafted 
responses. Draft generated → user approves/edits/rejects → approved draft 
sent via channel's outbound handler (BlueBubbles, Gmail API, Twilio). 
Non-household recipients require confirm gate. See Section 14.1 Step 3."

GENE 8 (Growth Rule):
Add after the abstract 8-step description: "For a complete worked example 
of the Growth Rule applied to a major new domain, see Section 14 
(Comms Domain), which walks through all 8 steps with code, schema, 
and architectural proofs."

Output: the modified Section 2 only (from its "## 2." heading to the "---" 
before Section 3). I will splice it into the full document myself.
```

**Accept when:** Only Section 2 content has changed. Each Gene addition is in the correct subsection. No existing content removed or rephrased. The new rows parse correctly in the classification table.

---

### Prompt B2: Section 3 — Schema Updates

```
Edit ONLY Section 3 of pib-v5-build-spec.md. Do not modify any other section.

Make these specific additions:

1. IN THE ops_comms TABLE DEFINITION (3.8):
   Add all new columns after the existing column list. Use the exact column 
   definitions from Section 14.1 Step 1 (the ALTER TABLE statements). 
   Integrate them as regular column definitions in the CREATE TABLE block — 
   the migration files handle the ALTER TABLE mechanics separately.
   
   Add the four new indexes (idx_comms_inbox, idx_comms_batch, idx_comms_drafts, 
   idx_comms_extraction) after the existing ops_comms indexes.

2. NEW TABLE SECTION — add after the existing "#### mem_* and pib_* Tables" block:

   #### cos_* Tables (Voice Intelligence)
   
   Add the complete CREATE TABLE statements for cos_voice_corpus and 
   cos_voice_profiles from Section 14.1 Step 1, with all columns, constraints, 
   and indexes. Include a brief rationale paragraph before each table:
   
   cos_voice_corpus: "Raw outbound message samples, dimensionally labeled. 
   Accumulates passively — every approved draft or direct reply adds a row. 
   No user effort required. Labels come from existing ops_items and 
   pib_energy_states data at write time."
   
   cos_voice_profiles: "Synthesized voice descriptions at hierarchical scope 
   levels. Rebuilt weekly from corpus by LLM. Resolution at draft time: 
   person > channel_x_type > person_type > domain > channel > baseline. 
   Narrow scopes override broad."

3. IN common_source_classifications SEED DATA:
   Add rows for: whatsapp, outlook, apple_voice_notes, manual_capture
   with the Four Label values from Prompt B1's Gene 2 additions.

4. IN pib_config SEED DATA:
   Add all comms config keys from Section 14.1 Step 1 config block 
   (comms_batch_morning_start through voice_profile_min_person).
   Also add: voice_notes_transcription_engine = "whisper_api"

5. IN meta_migrations REGISTRY:
   Add entries for migration 003 (comms_enhancement) and 004 (voice_intelligence).
   Reference the migration files from Prompt A2.

6. IN common_id_sequences:
   Verify the 'c' prefix is registered for comms IDs. If not present, add it.

Output: the modified Section 3 only.
```

**Accept when:** The ops_comms CREATE TABLE now includes all new columns inline. cos_* tables are present with complete DDL. Config seeds are present. Source classifications include all four new sources. Verify no existing table definitions were altered.

---

### Prompt B3: Section 6 — Ingestion Updates

```
Edit ONLY Section 6 of pib-v5-build-spec.md. Do not modify any other section.

Make these specific additions:

1. ADAPTER INVENTORY TABLE (6.1 or 6.2):
   Add rows:
   | apple_voice_notes | Filesystem watcher (watchdog) + Whisper transcription | Layer 2 | Phase 3b | See apple-voice-notes-adapter.md |
   | whatsapp | WhatsApp Business API / Web bridge | Layer 3 | Phase 4 (deferred) | ToS risk — see Section 14.1 Step 2 |
   | outlook | Microsoft Graph API (metadata only) | Layer 3 | Phase 4 (deferred) | Privacy: privileged. Content never stored. |
   | manual_capture | HTTP POST /api/comms/capture | Layer 1 | Phase 3b | Meeting notes, call transcripts, recordings |

2. IDEMPOTENCY KEY PATTERNS (6.2):
   Add to the existing pattern table:
   | whatsapp | SHA256(whatsapp:{messageId}) |
   | outlook | SHA256(outlook:{messageId}) |
   | apple_voice_notes | SHA256(voice_memo:{filename}:{file_size}:{mtime}) |
   | manual_capture | SHA256(capture:{ts}:{title[:50]}) |

3. PIPELINE STAGES (6.3):
   After Stage 6 (Route + Write), add:
   "Stage 6.5 — Extraction Queueing (deterministic, <1ms): For comms, set 
   extraction_status='pending'. The async extraction worker (Section 14.2) 
   picks these up independently. This keeps the hot ingestion path fast — 
   no LLM calls in-line."
   
   In Stage 8 (Confirm + Emit), add:
   "For outbound comms that are sent or marked responded, emit to the voice 
   collection listener which writes to cos_voice_corpus. This is fire-and-forget — 
   collection failure never blocks the pipeline. See Section 14.3."

4. Add a brief note referencing apple-voice-notes-adapter.md for the full 
   Voice Notes adapter design, rather than duplicating the spec inline.

Output: the modified Section 6 only.
```

**Accept when:** Four new adapters in the inventory. Four new idempotency patterns. Stage 6.5 documented. Stage 8 enhancement documented. No existing adapter descriptions modified.

---

### Prompt B4: Section 7 — Context + CoS Updates

```
Edit ONLY Section 7 of pib-v5-build-spec.md. Do not modify any other section.

Make these specific additions:

1. RELEVANCE DETECTION (7.1):
   Add to the keyword trigger sets:
   COMMS_TRIGGERS = {"message", "messages", "email", "emails", "reply", 
   "respond", "responded", "draft", "inbox", "unread", "text", "texted", 
   "called", "voicemail", "whatsapp", "imessage", "wrote", "sent", 
   "received", "heard from", "reach out", "voice note", "recording"}
   
   In the analyze_relevance() description, add "comms" to the list of 
   possible assembler returns.

2. ASSEMBLER REGISTRY (7.1):
   Add comms_assembler to the assembler list. Brief description:
   "Returns inbox summary: pending response count, batch status, pending 
   drafts, recent comms from matched entities. ~100-200 tokens. 
   Full spec: Section 14.1 Step 4."

3. TOKEN BUDGET (7.2):
   Add a note: "Comms context adds ~100-200 tokens to assembled_context. 
   Voice profile injection and draft generation use SEPARATE LLM calls 
   with their own context windows — they do not compete with the 
   conversation context budget."

4. TOOL DEFINITIONS (7.7):
   Add four new tools to the tool inventory:
   
   | search_comms | Search ops_comms by person, channel, date range, urgency, keyword | Returns matching comms with summary |
   | draft_response | Generate CoS draft for a specific comm using resolved voice profile | Triggers voice profile resolution → LLM draft → stores in draft_response |
   | approve_draft | Approve and send a pending draft, optionally with edits | Transitions draft through approved → sending → sent |
   | capture_comm | Create manual capture entry (meeting note, transcript, etc.) | Writes to ops_comms, triggers async extraction |

5. COACH PROTOCOLS (7.5):
   Add four protocols:
   - "Batch, Don't Interrupt": Non-urgent comms batch into review windows. 
     Never real-time notify for normal messages.
   - "Draft Tone Match": Always match resolved voice profile. When uncertain, 
     err shorter and more casual.
   - "Extraction Humility": Present extractions as proposals. 
     "I spotted a possible task" never "I've added a task."
   - "Batch Completion Celebration": Celebrate batch review completion 
     like task completion. Feeds variable-ratio reward system.

Output: the modified Section 7 only.
```

**Accept when:** COMMS_TRIGGERS present in relevance detection. Assembler registered. Token budget note present. Four new tools in inventory. Four new coach protocols. No existing tools or protocols modified.

---

### Prompt B5: Section 8 — Proactive Engine Updates

```
Edit ONLY Section 8 of pib-v5-build-spec.md. Do not modify any other section.

Make these specific additions:

1. TRIGGER LIST (8.1):
   Add six new triggers to the proactive trigger inventory:
   
   | comm_batch_morning | priority 4 | cooldown 1440min | Fires during configured morning window when pending morning-batch comms exist | Stream card |
   | comm_batch_midday | priority 5 | cooldown 1440min | Fires during midday window | Stream card |
   | comm_batch_evening | priority 5 | cooldown 1440min | Fires during evening window | Stream card |
   | comm_urgent_inbound | priority 2 | cooldown 60min | Urgent comm with needs_response, received in last hour | Direct iMessage (bypasses batching) |
   | comm_draft_stale | priority 6 | cooldown 480min | Draft pending for 4+ hours | Nudge |
   | comm_response_overdue | priority 5 | cooldown 1440min | needs_response comm pending 48+ hours | Nudge with easiest-first suggestion |

2. GUARDRAILS NOTE (8.2):
   Add one sentence: "All comms triggers respect existing guardrails 
   (quiet hours, focus mode, daily limits, in-meeting check, cooldowns) 
   without modification. The urgent bypass trigger (comm_urgent_inbound) 
   still respects quiet hours — urgency overrides batching, not sleep."

Output: the modified Section 8 only.
```

**Accept when:** Six triggers present in inventory with correct priorities and cooldowns. Guardrail note present. No existing triggers modified.

---

### Prompt B6: Section 5 — Console Updates

```
Edit ONLY Section 5 of pib-v5-build-spec.md. Do not modify any other section.

Make these specific additions:

1. SHELL (5.7):
   Add to the nav items array, positioned after Chat and before Scoreboard:
   { id: "comms", icon: "📨", label: "Comms", badge: commsNeedsResponse }
   
   Add route: case "comms": return <CommsInboxPage />

2. DESIGN SYSTEM (5.6):
   In the Domain Color Map table, add:
   | comms | Blue | --info |
   
   Add note: "Comms cards use --err border for urgent, --warn for timely, 
   --pink border for draft-pending cards (matching active-task glow — 
   'this needs your attention'). Extraction badges use --teal background."

3. NEW SUBSECTION — 5.X Comms Inbox Page:
   Add the wireframe from Section 14.1 Step 7 (the ASCII box layout).
   Add the filter bar spec, batch review carousel mode description, 
   and component list (CommsCard, CommsBatchBar, CommsDraftReview, 
   CommsExtractionBadge, CommsReplyComposer).
   
   Reference the full component specs in the console implementation prompt 
   rather than duplicating React code in the build spec. The build spec 
   defines WHAT the page does and how it looks; implementation details 
   live in the code.

4. SETTINGS (existing Settings subsection):
   Add: "Comms Settings panel: batch window timing, extraction toggle + 
   confidence threshold, CoS drafting toggle with sample progress indicator, 
   per-source connection status. Voice Profiles panel: read-only display of 
   synthesized profiles with scope, sample count, confidence, and style 
   summary. Builds user trust in drafting before they enable it."

Output: the modified Section 5 only.
```

**Accept when:** Nav item present. Domain color mapped. Comms page wireframe present. Settings panels described. No existing page descriptions modified.

---

### Prompt B7: Section 9 — Build Phase Updates

```
Edit ONLY Section 9 of pib-v5-build-spec.md. Do not modify any other section.

Restructure Phase 3 into sub-phases. Keep Phase 0, 1, 2 untouched.

Phase 3a: (existing Phase 3 scope — whatever is currently specified)
  Rename to "Phase 3a: [existing name]" and keep all existing content.

Phase 3b: Comms Inbox MVP
  - ops_comms schema enhancement (migration 003)
  - CommsInboxPage in console (read + filter + mark responded)
  - Enhanced Gmail adapter (full body storage, thread tracking)  
  - Enhanced iMessage adapter (conversation threading)
  - Apple Voice Notes adapter (filesystem watcher + Whisper transcription)
  - Manual capture endpoint (/api/comms/capture)
  - Batch window assignment (deterministic)
  - Comm batch triggers in proactive engine
  - Stream card for comm batches in Today page
  - Depends on: Phase 2 (ingestion pipeline operational)

Phase 3c: Extraction + Voice Intelligence
  - Voice intelligence schema (migration 004)
  - Async extraction worker
  - Extraction approval UI in Comms Inbox
  - Voice corpus collection (passive, zero-effort)
  - Voice profile synthesis (weekly cron)
  - Draft generation after voice profile threshold met
  - Draft approve/edit/reject/send flow
  - Depends on: Phase 3b (Comms Inbox operational)

Phase 4: add to existing Phase 4 scope:
  - WhatsApp adapter evaluation (if stable, ToS-compliant API exists)
  - Outlook adapter (Laura's work, metadata only, privileged)
  - CoS proactive overnight drafting (drafts queued for morning review)
  - Extended voice profiles (cross-dimensional, per-person for top contacts)

Output: the modified Section 9 only.
```

**Accept when:** Phase 3 is split into 3a/3b/3c with clear scopes and dependencies. Phase 4 has comms additions. Phases 0-2 are untouched.

---

### Prompt B8: Sections 10, 11, 12, 13 — Testing, Criteria, Ops, Privacy

```
Edit Sections 10, 11, 12, and 13 of pib-v5-build-spec.md. Do not modify any 
other section. These are small additions to each — grouped into one prompt 
because each change is 5-15 lines.

SECTION 10 (Testing):
Add comms test cases to the test inventory:
- Inbound iMessage → appears in Comms Inbox within 30 seconds
- Apple Voice Note recorded → transcribed → appears in inbox within 2 minutes
- Extraction proposes task from "Can you call the plumber?" with confidence ≥ 0.7
- Approved draft sends via correct channel within 5 seconds
- Draft send failure → send_failed state → retry visible → dead letter logged
- Voice profile baseline emerges after 15 outbound messages
- Batch review completion triggers reward message
- Snoozed message reappears at snoozed_until time
- Manual capture with extraction → proposals appear in inbox

SECTION 11 (Success Criteria):
Add to the outcome metrics table:
| Comm response latency | Unknown | <24h for timely, <4h for urgent | ops_comms timestamps |
| Batch review completion rate | 0% | >80% of daily batches reviewed | batch status tracking |
| Draft acceptance rate | N/A | >60% after month 2 | approved / (approved + rejected) |
| Voice profile accuracy | N/A | "Sounds like me" >80% | Monthly self-review |

Add to technical criteria:
15. Inbound iMessage → Comms Inbox within 30 seconds
16. Apple Voice Note → transcribed and visible within 2 minutes
17. Laura's Outlook content NEVER appears in any context, summary, or draft
18. Extraction proposes task with confidence ≥ 0.7 for explicit requests
19. Comm batch stream card appears at configured window time

Add to ADHD Scorecard: "Comms domain improves Memory (+15-20 points: 
every comm captured, 'did I respond?' is a query not a memory task) and 
Proactive (+10-15 points: batch nudges, overdue detection, draft generation)."

SECTION 12 (Operational Runbook):
Add to cron schedule:
| 0 3 * * 0 | synthesize_all_profiles | Weekly voice profile rebuild |
| 0 4 1 * * | voice_corpus_cleanup | Monthly: prune samples > 6 months |
| 0 */4 * * * | retry_failed_extractions | Re-attempt failed extractions |
| 0 22 * * * | expire_stale_drafts | Expire drafts pending > 24 hours |

Add to health checks:
| comms_freshness | Latest non-capture comm < 30 min old | Adapter may be down |
| extraction_backlog | Pending extractions < 20 and < 1 hour old | Worker may be stuck |
| draft_delivery | send_failed count < 5 | Channel outbound may be broken |

Add to backup verification: cos_voice_corpus, cos_voice_profiles

SECTION 13 (Canary / Privacy):
Add canary tests:
- "Laura's Outlook email body NEVER appears in assembled context, 
  draft responses, voice corpus, or extraction proposals."
- "Privileged comm content from work sources is never used as 
  voice training data — hard filter at collection time."
- "Apple Voice Note transcriptions are stored with privacy='full' 
  and never leak into Laura's work context."
- "Voice corpus samples are never included in non-draft LLM calls — 
  they only appear in the draft generation prompt and the weekly 
  synthesis prompt."

Output: the modified Sections 10, 11, 12, and 13 only.
```

**Accept when:** All test cases, success criteria, cron entries, health checks, and canary tests are present. No existing entries in any of these sections have been modified or removed.

---

## PHASE C: CONSOLE IMPLEMENTATION (new files, then small edits to existing)

---

### Prompt C1: CommsCard Component

```
Build CommsCard.jsx — the atomic message card component for the Comms Inbox.

Reference the full component spec in the console implementation prompt 
(pib-comms-domain-spec.md Section 14.1 Step 7 for wireframe, Section 14.4 
for API contract).

Props:
  comm: object (single comm from GET /api/comms/inbox response)
  onAction: (commId, action, payload?) => void  
  compact: boolean (true in batch carousel mode)

The card must render:
- Urgency indicator (left border: --err red for urgent, --warn yellow for 
  timely, transparent for normal, --info blue dashed for fyi)
- Channel icon (iMessage=💬, Email=📧, SMS=📱, Voice Note=🎙️, 
  Meeting Note=📝, Capture=📎)
- From name, channel, relative time
- Body snippet (max 3 lines, CSS line-clamp)
- Extraction badges (if extracted_items has items) with approve/reject buttons
- Draft card (if draft_status='pending') with edit/send/reject buttons
- Action bar: Snooze, Mark Responded, Tag, Reply

Use only Tailwind utility classes + inline style for CSS variables. 
No localStorage. Match the existing design system (12px radius, subtle shadows, 
hover transitions).

Output: one complete CommsCard.jsx file.
```

**Accept when:** Component renders with mock data. All urgency states visually distinct. Actions call onAction with correct parameters. No console errors.

---

### Prompt C2: Supporting Components

```
Build these three supporting components for the Comms Inbox.
Each is extracted from CommsCard for reuse and clarity.

1. CommsDraftReview.jsx
   Props: draft (string), draftStatus (string), channel (string), 
          onApprove(editedBody?), onReject(), onEdit()
   Renders: draft text in italic, channel indicator, Edit/Send/Reject buttons.
   Edit mode: inline textarea replaces draft text. Save button calls 
   onApprove with edited text.
   Pink left border (--pink) matching active-task glow pattern.

2. CommsExtractionBadge.jsx
   Props: extraction (object with type, data, confidence, approved), 
          onApprove(), onReject()
   Renders: type icon (📋 task, 📅 event, 💰 bill, 👤 entity, 📝 list, 🔄 recurring)
   + title + confidence indicator + approve/reject icon buttons.
   Teal background (--teal). Approved state: green checkmark, no buttons.
   Rejected: fades out.

3. CommsReplyComposer.jsx
   Props: channel (string), recipientName (string), onSend(body), onCancel()
   Renders: "Replying via {channel} {icon}" header, textarea, character count 
   (show for SMS), Send button (disabled when empty), Cancel button.
   Uses slideIn animation on mount.

All: Tailwind only, no localStorage, match design system.

Output: three complete component files.
```

**Accept when:** Each component renders independently with mock props. Draft edit toggle works. Extraction approve/reject updates visual state. Reply composer shows character count for SMS channel.

---

### Prompt C3: CommsBatchBar + CommsInboxPage

```
Build two files:

1. CommsBatchBar.jsx
   Props: batches ({ morning: {count, reviewed}, midday: {...}, evening: {...} }),
          activeBatch (string|null), onBatchClick(window)
   Renders: horizontal bar with three batch indicators.
   Each: icon (☀️/🌤️/🌙) + "N/M" progress + status (✅ complete, ⏳ in progress, — empty).
   Active batch has --pink underline. Completed has --grn checkmark.
   Clicking a batch calls onBatchClick to filter the list.

2. CommsInboxPage.jsx (~500-700 lines)
   The main page component. Reference Section 14.1 Step 7 wireframe and 
   Section 14.4 API contract.

   State: filter, channelFilter, personFilter, batchFilter, visibilityFilter,
          batchReviewMode, selectedCommIndex (for carousel)
   
   Data: GET /api/comms/inbox with all filter params. Poll every 60 seconds.
         Use useAPI hook (existing pattern).
   
   URL params: Read filter/batch/channel from URL on mount for deep linking.
   /comms?batch=midday&filter=needs_response launches batch carousel mode.
   
   Layout:
   - Header: title + batch dropdown + settings gear link
   - FilterBar: tab buttons with counts (All, Needs Reply, Urgent, Drafts, FYI)
     + secondary dropdowns (channel, person, visibility)
   - MessageList: grouped by urgency (urgent first), then date DESC within group.
     Each item renders <CommsCard />. onAction handler routes to API endpoints.
   - CommsBatchBar at bottom
   
   Batch carousel mode: when batchReviewMode=true, render ONE CommsCard at a time
   (compact mode). Arrow buttons / swipe to advance. Progress: "3 of 5".
   On last card completed: confetti animation + "Inbox clear. {count} handled."
   
   Action routing (onAction handler):
   | approve-draft | POST /api/comms/{id}/approve-draft |
   | reject-draft | POST /api/comms/{id}/reject-draft |
   | reply | POST /api/comms/{id}/reply |
   | mark-responded | POST /api/comms/{id}/mark-responded |
   | approve-extraction | POST /api/comms/{id}/extraction/{index}/approve |
   | reject-extraction | POST /api/comms/{id}/extraction/{index}/reject |
   | snooze | POST /api/comms/{id}/snooze |
   | tag | POST /api/comms/{id}/tag |
   
   After any action: optimistic UI update, then refetch on success. 
   On error: revert optimistic update, show friendly error toast.
   
   Empty states:
   - No comms: "📨 No messages yet. Connect your channels in Settings."
   - Filter empty: "No {filter} messages. [Clear filters]"
   - All reviewed: "✅ All clear." with scale-pulse checkmark animation
   
   Loading: skeleton cards (3 placeholder cards with shimmer animation, 
   matching existing loading patterns in Tasks page)

Output: two complete files.
```

**Accept when:** Page renders with mock API response. Filters update URL params and refetch. Batch carousel mode shows one card at a time with progress indicator. All actions route to correct endpoints. Empty states display correctly.

---

### Prompt C4: Shell + Today + Settings Edits

```
Make targeted edits to three existing console files. 
Produce ONLY the changed sections, clearly marked with line context 
so they can be spliced in. Do NOT regenerate entire files.

1. Shell.jsx — add Comms nav item and route:
   
   In NAV_ITEMS array, after the "chat" entry and before "scoreboard":
   { id: "comms", icon: "📨", label: "Comms", badge: commsCount }
   
   Add commsCount state: poll GET /api/comms/counts every 30 seconds, 
   extract needs_response. Same pattern as taskCount polling.
   
   In page router switch, add:
   case "comms": return <CommsInboxPage />
   
   Add import: import CommsInboxPage from './pages/CommsInboxPage'

2. TodayJames.jsx — add comms_batch stream card:
   
   In the stream card render switch, add case "comms_batch":
   Renders: card with --info left border, 📨 icon, title, micro-script, 
   "Review" button that navigates to /comms?batch={item.batch_window}.
   ~15 lines of JSX.

3. Settings.jsx — add two accordion panels:
   
   Panel: "📨 Comms Settings"
   - Batch window time inputs (morning/midday/evening start+end)
   - Urgent bypass toggle
   - Extraction toggle + confidence slider
   - CoS drafting toggle + sample progress per channel
   - Source connection status list
   Each reads/writes pib_config via existing GET/PUT /api/config/{key}
   
   Panel: "🎤 Voice Profiles"
   - Read-only. Fetches GET /api/voice/profiles?member={current_member}
   - Lists each profile: scope name, sample count, confidence bar, style_summary
   - Profiles below threshold show grayed with "Needs N more samples"
   - Last rebuild timestamp

For each file, output ONLY:
- The import additions (if any)
- The specific code blocks to insert, with 3 lines of surrounding context 
  above and below so I can locate the insertion point
- Any new state declarations

Do NOT output complete files.
```

**Accept when:** Each edit is small and precisely located. Shell badge polls correctly. Stream card renders and navigates. Settings panels read from and write to config API.

---

## PHASE D: CROSS-REFERENCE + VERIFICATION

---

### Prompt D1: Appendix Updates

```
Edit ONLY the Appendix / end matter of pib-v5-build-spec.md.

1. FILE MANIFEST: Add all new files from Section 14.6, plus 
   apple-voice-notes-adapter.md as a referenced spec document.

2. API ENDPOINT INVENTORY: Add all comms endpoints from Section 14.4:
   GET /api/comms/inbox, GET /api/comms/{id}, GET /api/comms/counts,
   POST /api/comms/{id}/approve-draft, POST /api/comms/{id}/reject-draft,
   POST /api/comms/{id}/reply, POST /api/comms/{id}/mark-responded,
   POST /api/comms/{id}/extraction/{index}/approve,
   POST /api/comms/{id}/extraction/{index}/reject,
   POST /api/comms/{id}/snooze, POST /api/comms/{id}/tag,
   POST /api/comms/capture,
   GET /api/voice/profiles

3. TABLE OF CONTENTS: Update to include Section 14 and any new subsections 
   added in Phase B.

Output: the modified appendix sections only.
```

**Accept when:** All new files listed. All new endpoints listed. Table of contents accurate.

---

### Prompt D2: Verification Checklist

```
Read the complete, updated pib-v5-build-spec.md and verify:

1. Section 14 is present and complete
2. Gene 2 has all four new source classifications
3. Gene 3 has comms extraction examples
4. Gene 5 references comm-to-task bridge
5. Gene 6 references draft-approve-send
6. Gene 8 references Section 14 as worked example
7. ops_comms in Section 3 has all new columns
8. cos_voice_corpus and cos_voice_profiles tables are in Section 3
9. Four new sources in common_source_classifications seed data
10. All comms config keys in pib_config seed data
11. Apple Voice Notes in adapter inventory (Section 6)
12. Stage 6.5 documented in pipeline (Section 6)
13. COMMS_TRIGGERS in relevance detection (Section 7)
14. comms_assembler registered (Section 7)
15. Four new tools in tool inventory (Section 7)
16. Four new coach protocols (Section 7)
17. Six new proactive triggers (Section 8)
18. Phase 3 split into 3a/3b/3c (Section 9)
19. Comms test cases present (Section 10)
20. Comms success criteria present (Section 11)
21. Four new cron entries (Section 12)
22. Three new health checks (Section 12)
23. Four new canary tests (Section 13)
24. File manifest updated (Appendix)
25. API inventory updated (Appendix)

For each item, report: PASS or FAIL with the specific location (section + 
line range or heading) where you found it. If FAIL, report what's missing.

Output: the 25-item verification report.
```

**Accept when:** All 25 items PASS. If any fail, return to the specific Phase B prompt that covers that item and re-run only that one.

---

## DEPENDENCY GRAPH

```
Phase A (standalone, parallel-safe):
  A1 ──→ (Section 14 in build spec)
  A2 ──→ (migration files exist)
  A3 ──→ (voice notes adapter spec exists)

Phase B (sequential within, but each is independent):
  A1 ──→ B1 (Gene references need Section 14 to point to)
  A1 ──→ B2 (schema needs Section 14 definitions)
  A3 ──→ B3 (ingestion needs voice notes spec)
  B2 ──→ B4 (context tools reference schema)
       ──→ B5 (triggers reference schema)
       ──→ B6 (console wireframe references schema)
  B5 ──→ B7 (phases reference triggers and console)
  B7 ──→ B8 (tests reference phases)

Phase C (sequential, but independent of Phase B):
  C1 ──→ C2 (supporting components used by card)
  C2 ──→ C3 (page composes card + components)
  C3 ──→ C4 (shell/settings changes reference page)

Phase D (after all others):
  B* + C* ──→ D1 (appendix references everything)
  D1 ──→ D2 (verification checks everything)
```

## COST COMPARISON

| Approach | Prompts | Risk per prompt | Verification effort | Recovery from failure |
|---|---|---|---|---|
| **2 monolithic prompts** | 2 | VERY HIGH (3800-line regeneration) | Read entire document | Redo entire prompt |
| **16 atomic prompts** | 16 | LOW (50-300 lines each) | Diff one section | Redo one prompt |

More prompts. Less total risk. Each one either works or it doesn't, and you know within 5 minutes.
