# console/ — PIB Dashboard Server

Express/Hono server + dashboard UI, created by the OpenClaw agent during bootstrap Phase 7.

## Expected Files

| File | Purpose |
|------|---------|
| `server.mjs` | Express server on port 3333, REST API reading from SQLite |
| `index.html` | Dashboard (scoreboard, ADHD stream, schedule, chat) |

## Prototype Reference
`docs/diagrams/pib-console-wired.jsx` — 1,738 lines of React prototype to reference for UI design.

## API Contract
See `docs/pib-api-contract.md` for all endpoint definitions with request/response shapes.
