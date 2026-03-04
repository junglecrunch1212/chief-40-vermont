# archive/ — Deprecated Code (Reference Only)

These files were part of the original standalone FastAPI architecture.
They have been replaced by OpenClaw L0 infrastructure.

## deprecated-fastapi/
- `web.py` (2,187 lines) — Replaced by OpenClaw gateway + console/server.mjs
- `scheduler.py` (655 lines) — Replaced by OpenClaw cron engine
- `auth.py` (127 lines) — Replaced by OpenClaw channel auth
- `bootstrap_wizard.py` (231 lines) — Replaced by `openclaw init` + workspace-template/
- `sheets.py` (91 lines) — Replaced by `gog sheets` CLI
- `test_web.py` — Tests for deprecated web.py
- `test_scheduler.py` — Tests for deprecated scheduler.py
- `test_bootstrap_wizard.py` — Tests for deprecated bootstrap_wizard.py

## deprecated-frontend/
- React SPA (Vite + React) — Replaced by console/server.mjs + console/index.html
- Design prototype preserved in `docs/diagrams/pib-console-wired.jsx`

These files are kept for reference. Do not import or run them.
