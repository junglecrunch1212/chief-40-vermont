"""Google Calendar adapter — polls calendar events, writes to cal_raw_events + cal_classified_events.

Uses google-api-python-client with a service account. Reads only — Gene 4 forbids writing
to external calendars.
"""

import json
import logging
import os
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


class GoogleCalendarAdapter:
    """Adapter for Google Calendar API using service account credentials."""

    name = "google_calendar"
    source = "google_calendar"

    def __init__(self):
        self._service = None
        self._key_path = os.environ.get("GOOGLE_SA_KEY_PATH", "")

    async def init(self) -> None:
        """Initialize the Google Calendar API service."""
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        creds = Credentials.from_service_account_file(self._key_path, scopes=scopes)
        self._service = build("calendar", "v3", credentials=creds)
        log.info("Google Calendar adapter initialized")

    async def ping(self) -> bool:
        """Check if the Calendar API is reachable."""
        if not self._service:
            return False
        try:
            self._service.calendarList().list(maxResults=1).execute()
            return True
        except Exception as e:
            log.warning(f"Calendar ping failed: {e}")
            return False

    async def poll(self, db, calendar_ids: list[str] | None = None,
                   time_min: str | None = None, time_max: str | None = None,
                   use_sync_token: bool = True) -> int:
        """Poll calendar events and write to cal_raw_events.

        Args:
            db: PIB database connection
            calendar_ids: List of Google Calendar IDs to poll. If None, reads from cal_sources.
            time_min: ISO datetime for range start (default: 7 days ago)
            time_max: ISO datetime for range end (default: 30 days ahead)
            use_sync_token: Whether to use incremental sync tokens

        Returns:
            Number of events upserted
        """
        if not self._service:
            log.error("Calendar service not initialized")
            return 0

        # Get calendar sources from DB if not provided
        if not calendar_ids:
            sources = await db.execute_fetchall("SELECT * FROM cal_sources")
            if not sources:
                log.info("No calendar sources configured in cal_sources")
                return 0
        else:
            sources = [{"id": cid, "google_calendar_id": cid, "sync_token": None} for cid in calendar_ids]

        now = datetime.utcnow()
        if not time_min:
            time_min = (now - timedelta(days=7)).isoformat() + "Z"
        if not time_max:
            time_max = (now + timedelta(days=30)).isoformat() + "Z"

        total_upserted = 0

        for source in sources:
            src = dict(source) if hasattr(source, "keys") else source
            source_id = src["id"]
            cal_id = src["google_calendar_id"]
            sync_token = src.get("sync_token") if use_sync_token else None

            try:
                events, new_sync_token = await self._fetch_events(
                    cal_id, sync_token, time_min, time_max
                )
                count = await self._upsert_events(db, source_id, events)
                total_upserted += count

                # Update sync token
                if new_sync_token:
                    await db.execute(
                        "UPDATE cal_sources SET sync_token = ?, last_synced = ? WHERE id = ?",
                        [new_sync_token, now.isoformat() + "Z", source_id],
                    )

                log.info(f"Calendar {cal_id}: {count} events upserted")

            except Exception as e:
                log.error(f"Calendar poll failed for {cal_id}: {e}", exc_info=True)

        if total_upserted > 0:
            await db.commit()

        return total_upserted

    async def _fetch_events(self, calendar_id: str, sync_token: str | None,
                            time_min: str, time_max: str) -> tuple[list[dict], str | None]:
        """Fetch events from a single calendar, handling pagination."""
        all_events = []
        page_token = None
        new_sync_token = None

        while True:
            kwargs = {
                "calendarId": calendar_id,
                "singleEvents": True,
                "orderBy": "startTime",
                "maxResults": 250,
            }
            if sync_token and not page_token:
                kwargs["syncToken"] = sync_token
            else:
                kwargs["timeMin"] = time_min
                kwargs["timeMax"] = time_max

            if page_token:
                kwargs["pageToken"] = page_token

            try:
                result = self._service.events().list(**kwargs).execute()
            except Exception as e:
                # If sync token is invalid, fall back to full sync
                if sync_token and "410" in str(e):
                    log.info(f"Sync token expired for {calendar_id}, doing full sync")
                    return await self._fetch_events(calendar_id, None, time_min, time_max)
                raise

            all_events.extend(result.get("items", []))
            page_token = result.get("nextPageToken")
            new_sync_token = result.get("nextSyncToken")

            if not page_token:
                break

        return all_events, new_sync_token

    async def _upsert_events(self, db, source_id: str, events: list[dict]) -> int:
        """Upsert fetched events into cal_raw_events."""
        from pib.db import next_id

        count = 0
        for event in events:
            google_event_id = event.get("id", "")
            if not google_event_id:
                continue

            # Parse start/end times
            start = event.get("start", {})
            end = event.get("end", {})
            start_time = start.get("dateTime") or start.get("date")
            end_time = end.get("dateTime") or end.get("date")
            all_day = 1 if "date" in start and "dateTime" not in start else 0

            summary = event.get("summary", "")
            description = event.get("description", "")
            location = event.get("location", "")
            status = event.get("status", "confirmed")

            attendees = json.dumps([
                {"email": a.get("email"), "name": a.get("displayName"), "status": a.get("responseStatus")}
                for a in event.get("attendees", [])
            ])

            recurrence = json.dumps(event.get("recurrence", []))

            # Check if event already exists
            existing = await db.execute_fetchone(
                "SELECT id FROM cal_raw_events WHERE source_id = ? AND google_event_id = ?",
                [source_id, google_event_id],
            )

            if event.get("status") == "cancelled":
                if existing:
                    await db.execute(
                        "DELETE FROM cal_raw_events WHERE id = ?", [existing["id"]]
                    )
                    await db.execute(
                        "DELETE FROM cal_classified_events WHERE raw_event_id = ?", [existing["id"]]
                    )
                    count += 1
                continue

            raw_json = json.dumps(event)

            if existing:
                await db.execute(
                    "UPDATE cal_raw_events SET summary=?, description=?, location=?, "
                    "start_time=?, end_time=?, all_day=?, recurrence_rule=?, attendees=?, "
                    "status=?, raw_json=?, fetched_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
                    "WHERE id=?",
                    [summary, description, location, start_time, end_time, all_day,
                     recurrence, attendees, status, raw_json, existing["id"]],
                )
                raw_id = existing["id"]
            else:
                raw_id = await next_id(db, "cal")
                await db.execute(
                    "INSERT INTO cal_raw_events (id, source_id, google_event_id, summary, "
                    "description, location, start_time, end_time, all_day, recurrence_rule, "
                    "attendees, status, raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [raw_id, source_id, google_event_id, summary, description, location,
                     start_time, end_time, all_day, recurrence, attendees, status, raw_json],
                )

            # Auto-classify the event
            await self._classify_event(db, raw_id, source_id, event, all_day, start_time, end_time, summary)
            count += 1

        return count

    async def _classify_event(self, db, raw_event_id: str, source_id: str,
                              event: dict, all_day: int, start_time: str | None,
                              end_time: str | None, summary: str):
        """Classify a raw event into cal_classified_events with privacy filtering."""
        from pib.db import next_id

        # Determine event date
        start = event.get("start", {})
        event_date = (start.get("date") or (start.get("dateTime", "")[:10])) or None
        if not event_date:
            return

        # Get source info for privacy classification
        source_row = await db.execute_fetchone(
            "SELECT for_member_ids, classification_id FROM cal_sources WHERE id = ?",
            [source_id],
        )

        for_member_ids = "[]"
        privacy = "full"
        title = summary
        title_redacted = summary

        if source_row:
            src = dict(source_row)
            for_member_ids = src.get("for_member_ids") or "[]"
            classification_id = src.get("classification_id")

            # Privacy fence: if this is Laura's work calendar, redact titles
            if classification_id and "work" in (classification_id or "").lower():
                member_ids = json.loads(for_member_ids) if for_member_ids else []
                if "m-laura" in member_ids:
                    privacy = "redacted"
                    title_redacted = "Work event"

        # Determine scheduling impact
        scheduling_impact = "FYI"
        if all_day:
            scheduling_impact = "FYI"
        elif event.get("attendees") and len(event.get("attendees", [])) > 0:
            scheduling_impact = "HARD_BLOCK"
        elif summary and any(kw in summary.lower() for kw in ["meeting", "call", "appointment", "doctor"]):
            scheduling_impact = "HARD_BLOCK"
        elif summary and any(kw in summary.lower() for kw in ["pickup", "dropoff", "drop off", "pick up"]):
            scheduling_impact = "REQUIRES_TRANSPORT"

        # Determine event type
        event_type = "event"
        if all_day:
            event_type = "all_day"
        elif summary and any(kw in summary.lower() for kw in ["birthday", "anniversary"]):
            event_type = "milestone"

        # Upsert classified event
        existing = await db.execute_fetchone(
            "SELECT id FROM cal_classified_events WHERE raw_event_id = ?",
            [raw_event_id],
        )

        if existing:
            await db.execute(
                "UPDATE cal_classified_events SET event_date=?, start_time=?, end_time=?, "
                "all_day=?, title=?, title_redacted=?, event_type=?, for_member_ids=?, "
                "scheduling_impact=?, privacy=?, source_id=? WHERE id=?",
                [event_date, start_time, end_time, all_day, title, title_redacted,
                 event_type, for_member_ids, scheduling_impact, privacy, source_id, existing["id"]],
            )
        else:
            classified_id = await next_id(db, "cal")
            await db.execute(
                "INSERT INTO cal_classified_events (id, raw_event_id, source_id, event_date, "
                "start_time, end_time, all_day, title, title_redacted, event_type, "
                "for_member_ids, scheduling_impact, privacy) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [classified_id, raw_event_id, source_id, event_date, start_time, end_time,
                 all_day, title, title_redacted, event_type, for_member_ids,
                 scheduling_impact, privacy],
            )

    async def send(self, message) -> None:
        """Gene 4: PIB never writes to external calendars."""
        raise NotImplementedError("PIB does not write to external calendars (Gene 4)")
