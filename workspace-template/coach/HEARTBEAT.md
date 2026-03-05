# HEARTBEAT.md (Coach Agent)

Run these checks. Report "warn" or "error". If all "ok", reply HEARTBEAT_OK.

## Checks

1. **PIB health:** `python -m pib.cli health $PIB_DB_PATH --json`
   - Expected: `{"ready": true}`
   - Error if: ready is false or command fails
