# Codebase Audit — chief-40-vermont (2026-03-04)

## Legend
- ✅ KEEP — Good, aligned with current architecture
- 🔧 REFACTOR — Needs updates to match OpenClaw L0 architecture
- 🗑️ REMOVE — No longer needed, replaced by OpenClaw or dead code
- 📦 ARCHIVE — Move to `archive/` — reference value but not active code
- 📄 REFERENCE — Static docs/specs, keep as-is

---

## Root Files

| File | Date | Lines | Verdict | Notes |
|------|------|-------|---------|-------|
| `.gitignore` | 03-01 | - | ✅ KEEP | |
| `CLAUDE.md` | 03-01 | - | 🔧 REFACTOR | Still references FastAPI :3141, needs OpenClaw L0 framing |
| `pyproject.toml` | 03-03 | - | 🔧 REFACTOR | Dependencies include FastAPI, uvicorn, apscheduler — keep for now (still used by domain code) but mark deprecated deps |
| `LifeOS-CoS-SOP.docx` | 03-01 | - | 📄 REFERENCE | Static planning doc |
| `PIB-LifeOS-v4-Spec.xlsx` | 03-01 | - | 📄 REFERENCE | v4 spec, historical |
| `pib-v5-blueprint (1).xlsx` | 03-01 | - | 📄 REFERENCE | Blueprint spreadsheet |
| `stice_financial_planner_streamlined (3).xlsx` | 03-01 | - | 📄 REFERENCE | Financial planning |

## Config

| File | Date | Verdict | Notes |
|------|------|---------|-------|
| `config/.env.example` | 03-02 | 🔧 REFACTOR | Has Cloudflare vars — remove. Add PIB_DB_PATH. Mark OpenClaw-managed vars |
| `config/agent_capabilities.yaml` | 03-03 | ✅ KEEP | |
| `config/governance.yaml` | 03-03 | ✅ KEEP | |
| `config/com.pib.runtime.plist` | 03-01 | 🔧 REFACTOR | Still references uvicorn — update for OpenClaw paths |

## Source — KEEP (domain logic, no OpenClaw overlap)

| File | Date | Lines | Notes |
|------|------|-------|-------|
| `src/pib/__init__.py` | 03-01 | - | ✅ |
| `src/pib/__main__.py` | 03-01 | - | ✅ |
| `src/pib/cli.py` | 03-03 | 1023 | ✅ Core permission boundary |
| `src/pib/engine.py` | 03-03 | 360 | ✅ whatNow(), pure |
| `src/pib/rewards.py` | 03-04 | 176 | ✅ Just fixed today |
| `src/pib/custody.py` | 03-03 | 69 | ✅ Pure function |
| `src/pib/memory.py` | 03-03 | 213 | ✅ FTS5 search |
| `src/pib/ingest.py` | 03-03 | 244 | ✅ Prefix parser |
| `src/pib/voice.py` | 03-03 | 371 | ✅ Voice profiles |
| `src/pib/comms.py` | 03-03 | 497 | ✅ Batch windows |
| `src/pib/proactive.py` | 03-03 | 274 | ✅ 11 triggers |
| `src/pib/extraction.py` | 03-01 | 151 | ✅ Comms enrichment |
| `src/pib/db.py` | 03-03 | 250 | ✅ SQLite connection |
| `src/pib/cost.py` | 03-01 | 32 | ✅ API cost tracking |
| `src/pib/backup.py` | 03-03 | 105 | ✅ SQLite backup |
| `src/pib/readiness.py` | 03-03 | 86 | ✅ Bootstrap checks |
| `src/pib/tz.py` | 03-03 | - | ✅ Timezone constants |
| `src/pib/llm.py` | 03-03 | - | 🔧 REFACTOR — Uses direct Anthropic client. Should be updated to call through OpenClaw model routing or kept as L2 fallback |
| `src/pib/capture.py` | 03-02 | - | ✅ |
| `src/pib/capture_organizer.py` | 03-02 | - | ✅ |
| `src/pib/corrections.py` | 03-01 | 23 | ✅ Tiny, keep |

## Source — DEPRECATED (replaced by OpenClaw)

| File | Date | Lines | Verdict | Replacement |
|------|------|-------|---------|-------------|
| `src/pib/web.py` | 03-03 | 2187 | 📦 ARCHIVE | OpenClaw gateway + console/server.mjs |
| `src/pib/scheduler.py` | 03-03 | 655 | 📦 ARCHIVE | OpenClaw cron engine |
| `src/pib/auth.py` | 03-03 | 127 | 📦 ARCHIVE | OpenClaw channel auth |
| `src/pib/bootstrap_wizard.py` | 03-02 | 231 | 📦 ARCHIVE | `openclaw init` + workspace-template/ |
| `src/pib/sheets.py` | 03-01 | 91 | 📦 ARCHIVE | `gog sheets` CLI |

## Source — Sensors (keep, used by Bridge Minis)

| File | Date | Verdict |
|------|------|---------|
| `src/pib/sensors/__init__.py` | 03-02 | ✅ |
| `src/pib/sensors/bus.py` | 03-02 | ✅ |
| `src/pib/sensors/enrichment.py` | 03-02 | ✅ |
| `src/pib/sensors/protocol.py` | 03-02 | ✅ |
| `src/pib/sensors/seed.py` | 03-02 | ✅ |
| `src/pib/sensors/sources/*.py` (14 files) | 03-02 | ✅ |

## Source — Project module (keep)

| File | Date | Verdict |
|------|------|---------|
| `src/pib/project/*.py` (10 files) | 03-03 | ✅ |

## Migrations

| File | Date | Verdict | Notes |
|------|------|---------|-------|
| `migrations/001_initial_schema.sql` | 03-03 | ✅ | |
| `migrations/002_add_energy_states.sql` | 03-01 | ✅ | |
| `migrations/003_comms_enhancement.sql` | 03-01 | ✅ | |
| `migrations/004_voice_intelligence.sql` | 03-01 | ✅ | |
| `migrations/005_sensor_bus.sql` | 03-02 | ✅ | |
| `migrations/006_capture_domain.sql` | 03-02 | ✅ | |
| `migrations/007_fts5_sync_triggers.sql` | 03-03 | ✅ | |
| `migrations/008_comms_per_member.sql` | 03-03 | ✅ | |
| `migrations/009_project_schema.sql` | 03-04 | ✅ | Renamed from 007 today |
| `migrations/010_comms_batch_seed.sql` | 03-03 | ✅ | |
| `migrations/011_comms_fts5.sql` | 03-03 | ✅ | |

## Tests

| File | Date | Verdict | Notes |
|------|------|---------|-------|
| `tests/test_web.py` | 03-01 | 📦 ARCHIVE | Tests for deprecated web.py |
| `tests/test_scheduler.py` | 03-03 | 📦 ARCHIVE | Tests for deprecated scheduler.py |
| `tests/test_bootstrap_wizard.py` | 03-02 | 📦 ARCHIVE | Tests for deprecated bootstrap_wizard.py |
| All other tests (30+ files) | 03-01–03 | ✅ KEEP | Test domain logic that's still active |

## Frontend

| File | Date | Verdict | Notes |
|------|------|---------|-------|
| `frontend/index.html` | 03-01 | 📦 ARCHIVE | Old React SPA — replaced by console/index.html |
| `frontend/package.json` | 03-01 | 📦 ARCHIVE | |
| `frontend/vite.config.js` | 03-01 | 📦 ARCHIVE | |
| `frontend/src/App.jsx` | 03-01 | 📦 ARCHIVE | |
| `frontend/src/CommsInboxPage.jsx` | 03-01 | 📦 ARCHIVE | |
| `frontend/src/main.jsx` | 03-01 | 📦 ARCHIVE | |

## Docs

| File | Date | Verdict | Notes |
|------|------|---------|-------|
| `docs/pib-v5-build-spec.md` | 03-01 | ✅ KEEP | Master spec, still canonical |
| `docs/pib-api-contract.md` | 03-01 | 🔧 REFACTOR | Endpoint paths need updating for Express :3333 |
| `docs/atomic-prompts.md` | 03-01 | 📄 REFERENCE | Build prompts for comms domain |
| `docs/cos-enablement-spec.md` | 03-02 | ✅ KEEP | |
| `docs/pre-bootstrap-refactor.md` | 03-03 | 📄 REFERENCE | Historical — refactor already completed |

## Scripts

| File | Date | Verdict | Notes |
|------|------|---------|-------|
| `scripts/bootstrap.sh` | 03-03 | ✅ KEEP | Production bootstrap script |
| `scripts/seed_data.py` | 03-01 | ✅ KEEP | Database seeder |

---

## Summary

| Action | Count | Files |
|--------|-------|-------|
| ✅ KEEP | ~100 | Domain logic, tests, migrations, sensors, config |
| 🔧 REFACTOR | 5 | CLAUDE.md, .env.example, com.pib.runtime.plist, llm.py, pib-api-contract.md |
| 📦 ARCHIVE | 11 | web.py, scheduler.py, auth.py, bootstrap_wizard.py, sheets.py, frontend/*, test_web, test_scheduler, test_bootstrap_wizard |
| 📄 REFERENCE | 6 | .docx, .xlsx files, atomic-prompts.md, pre-bootstrap-refactor.md |
