# HEARTBEAT.md

Run these checks in order. Report any items with status "warn" or "error". If all "ok", reply HEARTBEAT_OK.

## Checks

1. **PIB health:** `python -m pib.cli health $PIB_DB_PATH --json`
   - Expected: `{"ready": true, ...}`
   - Error if: ready is false, or command fails

2. **Google auth:** `gog calendar list --no-input 2>&1 | head -3`
   - Expected: calendar list output
   - Error if: "invalid_grant" or "Token has been expired"

3. **Database writable:** `sqlite3 $PIB_DB_PATH "SELECT COUNT(*) FROM ops_tasks;"`
   - Expected: a number
   - Error if: "readonly" or "locked" or fails

4. **Console server:** `curl -s -o /dev/null -w "%{http_code}" http://localhost:3333/api/pulse`
   - Expected: 200
   - Warn if: non-200 or timeout

5. **Disk space:** `df -h $PIB_DB_PATH | awk 'NR==2{print $5}'`
   - Warn if: usage > 85%

6. **Backup freshness:** Check most recent file in `$PIB_HOME/data/backups/`
   - Warn if: newest backup > 2 hours old

7. **Calendar sync:** Check `last_synced` in `cal_sources` table
   - Warn if: any source > 30 minutes stale
