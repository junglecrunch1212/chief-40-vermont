"""The Sensor Bus — polls registered sensors, stores readings, manages lifecycle.

Parallel to the ingestion pipeline but for context signals. Runs on its own scheduler.
Writes to pib_sensor_readings. Consumed by daily_state, context assembly, and proactive triggers.

DESIGN PRINCIPLES:
  1. Every sensor is optional. PIB works with zero sensors active.
  2. Sensors degrade gracefully. If weather API is down, PIB uses stale data with
     confidence="stale". If no weather at all, daily_state just omits weather context.
  3. No sensor can block the bus. Each read() has a timeout. Failures are logged, not fatal.
  4. Readings are append-only. Old readings aren't deleted, they expire via TTL.
     Consumers always query for latest reading per sensor_id where not expired.
  5. The bus doesn't interpret readings. It stores them. Interpretation happens
     in daily_state computation and context assembly.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from pib.sensors.protocol import SENSOR_REGISTRY, Sensor, SensorReading

log = logging.getLogger(__name__)

POLL_TIMEOUT_SECONDS = 10
DEGRADED_THRESHOLD = 3
DISABLE_THRESHOLD = 10


class SensorBus:
    """Central coordinator for all sensor polling and reading storage."""

    def __init__(self, db):
        self.db = db
        self.sensors: dict[str, Sensor] = {}
        self._running = False

    async def start(self):
        """Initialize all enabled sensors.

        For each sensor in SENSOR_REGISTRY:
          1. Check pib_sensor_config: is it enabled?
          2. If enabled, instantiate + init()
          3. Log health status

        Actual polling is driven by the external scheduler (APScheduler).
        """
        self._running = True
        rows = await self.db.execute_fetchall(
            "SELECT sensor_id FROM pib_sensor_config WHERE enabled = 1"
        )
        enabled_ids = {row["sensor_id"] for row in rows} if rows else set()

        for sensor_id, sensor_cls in SENSOR_REGISTRY.items():
            if sensor_id not in enabled_ids:
                continue
            try:
                instance = sensor_cls()
                await instance.init()
                self.sensors[sensor_id] = instance
                await self.db.execute(
                    "UPDATE pib_sensor_config SET status = 'healthy', consecutive_failures = 0 WHERE sensor_id = ?",
                    [sensor_id],
                )
                log.info(f"Sensor initialized: {sensor_id}")
            except Exception as e:
                log.warning(f"Sensor init failed: {sensor_id}: {e}")
                await self.db.execute(
                    "UPDATE pib_sensor_config SET status = 'error', last_error = ? WHERE sensor_id = ?",
                    [str(e), sensor_id],
                )

        await self.db.commit()
        log.info(f"Sensor bus started: {len(self.sensors)} sensors active")

    async def stop(self):
        """Shut down the sensor bus."""
        self._running = False
        self.sensors.clear()
        log.info("Sensor bus stopped")

    async def poll_sensor(self, sensor_id: str):
        """Poll a single sensor: read with timeout, dedup, store, handle failures."""
        sensor = self.sensors.get(sensor_id)
        if not sensor:
            return

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            readings = await asyncio.wait_for(
                sensor.read(), timeout=POLL_TIMEOUT_SECONDS
            )
            stored = 0
            for reading in readings:
                if await self._store_reading(reading):
                    stored += 1

            # Update health status
            await self.db.execute(
                """UPDATE pib_sensor_config
                   SET status = 'healthy', consecutive_failures = 0,
                       last_poll_at = ?, last_successful_read = ?,
                       next_poll_at = datetime(?, '+' || poll_interval_minutes || ' minutes')
                   WHERE sensor_id = ?""",
                [now, now, now, sensor_id],
            )
            await self.db.commit()

            if stored > 0:
                log.debug(f"Sensor {sensor_id}: stored {stored} readings")

        except asyncio.TimeoutError:
            await self._record_failure(sensor_id, "Read timed out", now)
        except Exception as e:
            await self._record_failure(sensor_id, str(e), now)

    async def _store_reading(self, reading: SensorReading) -> bool:
        """Store a reading, deduplicating by idempotency_key. Returns True if stored."""
        # Check dedup
        existing = await self.db.execute_fetchone(
            "SELECT 1 FROM pib_sensor_readings WHERE idempotency_key = ?",
            [reading.idempotency_key],
        )
        if existing:
            return False

        # Compute expires_at
        ts = reading.timestamp
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.now(timezone.utc)
        expires = (dt + timedelta(minutes=reading.ttl_minutes)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        await self.db.execute(
            """INSERT INTO pib_sensor_readings
               (sensor_id, reading_type, timestamp, value, member_id, location_id,
                confidence, ttl_minutes, expires_at, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                reading.sensor_id,
                reading.reading_type,
                reading.timestamp,
                json.dumps(reading.value),
                reading.member_id,
                reading.location_id,
                reading.confidence,
                reading.ttl_minutes,
                expires,
                reading.idempotency_key,
            ],
        )
        return True

    async def _record_failure(self, sensor_id: str, error: str, now: str):
        """Record a sensor failure and escalate if needed."""
        await self.db.execute(
            """UPDATE pib_sensor_config
               SET consecutive_failures = consecutive_failures + 1,
                   last_error = ?, last_poll_at = ?
               WHERE sensor_id = ?""",
            [error, now, sensor_id],
        )

        row = await self.db.execute_fetchone(
            "SELECT consecutive_failures FROM pib_sensor_config WHERE sensor_id = ?",
            [sensor_id],
        )
        failures = row["consecutive_failures"] if row else 0

        if failures >= DISABLE_THRESHOLD:
            await self.db.execute(
                "UPDATE pib_sensor_config SET status = 'disabled', enabled = 0 WHERE sensor_id = ?",
                [sensor_id],
            )
            self.sensors.pop(sensor_id, None)
            log.error(f"Sensor {sensor_id} disabled after {failures} consecutive failures")
        elif failures >= DEGRADED_THRESHOLD:
            await self.db.execute(
                "UPDATE pib_sensor_config SET status = 'degraded' WHERE sensor_id = ?",
                [sensor_id],
            )
            log.warning(f"Sensor {sensor_id} degraded ({failures} failures): {error}")
        else:
            log.warning(f"Sensor {sensor_id} poll failed ({failures}): {error}")

        await self.db.commit()

    async def get_latest_readings(
        self,
        category: str | None = None,
        member_id: str | None = None,
        sensor_id: str | None = None,
        max_age_minutes: int | None = None,
    ) -> list[dict]:
        """Get the most recent reading per sensor, optionally filtered.

        Excludes readings older than their TTL (stale).
        Returns readings enriched with is_stale, is_fresh, age_minutes.
        """
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        conditions = ["r.expires_at > ?"]
        params: list = [now_str]

        if sensor_id:
            conditions.append("r.sensor_id = ?")
            params.append(sensor_id)
        if member_id:
            conditions.append("r.member_id = ?")
            params.append(member_id)
        if category:
            conditions.append("c.category = ?")
            params.append(category)
        if max_age_minutes:
            cutoff = (now - timedelta(minutes=max_age_minutes)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            conditions.append("r.timestamp > ?")
            params.append(cutoff)

        where = " AND ".join(conditions)

        rows = await self.db.execute_fetchall(
            f"""SELECT r.*, c.category, c.privacy
                FROM pib_sensor_readings r
                JOIN pib_sensor_config c ON r.sensor_id = c.sensor_id
                WHERE {where}
                AND r.id IN (
                    SELECT MAX(id) FROM pib_sensor_readings
                    GROUP BY sensor_id, reading_type
                )
                ORDER BY r.timestamp DESC""",
            params,
        )

        results = []
        for row in rows or []:
            reading = dict(row)
            # Parse value JSON
            try:
                reading["value"] = json.loads(reading["value"])
            except (json.JSONDecodeError, TypeError):
                pass

            # Compute freshness
            try:
                ts = datetime.fromisoformat(reading["timestamp"].replace("Z", "+00:00"))
                age = (now - ts).total_seconds() / 60
                ttl = reading["ttl_minutes"]
                reading["age_minutes"] = round(age, 1)
                reading["is_stale"] = age > ttl
                reading["is_fresh"] = age < (ttl / 2)
            except (ValueError, KeyError):
                reading["age_minutes"] = None
                reading["is_stale"] = True
                reading["is_fresh"] = False

            results.append(reading)

        return results

    async def get_reading_history(
        self, sensor_id: str, hours: int = 24
    ) -> list[dict]:
        """Historical readings for trend analysis."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        rows = await self.db.execute_fetchall(
            """SELECT * FROM pib_sensor_readings
               WHERE sensor_id = ? AND timestamp > ?
               ORDER BY timestamp DESC""",
            [sensor_id, cutoff],
        )
        results = []
        for row in rows or []:
            reading = dict(row)
            try:
                reading["value"] = json.loads(reading["value"])
            except (json.JSONDecodeError, TypeError):
                pass
            results.append(reading)
        return results

    async def create_alert(
        self,
        sensor_id: str,
        alert_type: str,
        severity: str,
        title: str,
        description: str | None = None,
        member_ids: list[str] | None = None,
        reading_id: int | None = None,
        suggested_action: str | None = None,
        expires_at: str | None = None,
    ) -> str:
        """Create a sensor alert. Returns the alert ID."""
        from pib.db import next_id

        alert_id = await next_id(self.db, "sns")
        await self.db.execute(
            """INSERT INTO pib_sensor_alerts
               (id, sensor_id, alert_type, severity, title, description,
                member_ids, reading_id, suggested_action, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                alert_id,
                sensor_id,
                alert_type,
                severity,
                title,
                description,
                json.dumps(member_ids or []),
                reading_id,
                suggested_action,
                expires_at,
            ],
        )
        await self.db.commit()
        return alert_id

    async def get_active_alerts(
        self, severity: str | None = None
    ) -> list[dict]:
        """Get active sensor alerts, optionally filtered by severity."""
        if severity:
            rows = await self.db.execute_fetchall(
                "SELECT * FROM pib_sensor_alerts WHERE status = 'active' AND severity = ? ORDER BY created_at DESC",
                [severity],
            )
        else:
            rows = await self.db.execute_fetchall(
                "SELECT * FROM pib_sensor_alerts WHERE status = 'active' ORDER BY created_at DESC"
            )
        results = []
        for row in rows or []:
            alert = dict(row)
            try:
                alert["member_ids"] = json.loads(alert["member_ids"])
            except (json.JSONDecodeError, TypeError):
                pass
            results.append(alert)
        return results
