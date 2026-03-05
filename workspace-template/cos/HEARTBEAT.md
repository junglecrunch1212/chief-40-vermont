# HEARTBEAT.md (CoS Agent)

Run these checks in order. Report any items with status "warn" or "error". If all "ok", reply HEARTBEAT_OK.

## Checks

1. **PIB health:** `python -m pib.cli health $PIB_DB_PATH --json`
   - Expected: `{"ready": true, ...}`
   - Error if: ready is false, or command fails

2. **Calendar freshness:** Check via health command output
   - Warn if: any calendar source > 30 minutes stale

3. **Morning digest ready:** `python -m pib.cli morning-digest $PIB_DB_PATH --member m-james --json`
   - Expected: valid JSON with today's brief
   - Warn if: empty or stale data
