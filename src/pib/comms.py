"""Comms Domain: inbox, batch windows, drafts, extraction, snooze, manual capture.

Implements the Comms Inbox as described in the atomic-prompts sequence:
- Batch window assignment (deterministic)
- Inbox queries with multi-filter support
- Draft lifecycle (generate → approve/edit/reject → send)
- Extraction lifecycle (queue → approve/reject proposed items)
- Snooze + visibility management
- Manual capture ingestion
"""

import json
import logging
from datetime import datetime, time, timedelta

from pib.db import audit_log, get_config, next_id
from pib.tz import now_et

log = logging.getLogger(__name__)

# ─── Batch Window Assignment ───


BATCH_WINDOWS = ["morning", "midday", "evening"]

BATCH_DEFAULTS = {
    "morning": ("07:00", "11:59"),
    "midday": ("12:00", "17:59"),
    "evening": ("18:00", "21:59"),
}


async def get_batch_config(db) -> dict:
    """Load batch window start/end times from pib_config."""
    config = {}
    for window in BATCH_WINDOWS:
        default_start, default_end = BATCH_DEFAULTS[window]
        start = await get_config(db, f"comms_batch_{window}_start", default_start)
        end = await get_config(db, f"comms_batch_{window}_end", default_end)
        h_s, m_s = map(int, start.split(":"))
        h_e, m_e = map(int, end.split(":"))
        config[window] = {
            "start": time(h_s, m_s),
            "end": time(h_e, m_e),
        }
    return config


def assign_batch_window(comm_time: datetime, batch_config: dict) -> str:
    """Deterministic batch assignment: which window does this comm land in?

    Rules:
    - If comm arrives during or after a window but before the next, it goes into the next window.
    - Pre-morning comms → morning. Post-evening comms → next day morning.
    - This is deterministic: same time + same config = same result.
    """
    t = comm_time.time()

    # If before morning window ends → morning
    if t < batch_config["morning"]["end"]:
        return "morning"
    # If before midday window ends → midday
    if t < batch_config["midday"]["end"]:
        return "midday"
    # If before evening window ends → evening
    if t < batch_config["evening"]["end"]:
        return "evening"
    # After evening → next day morning (still tagged as morning)
    return "morning"


def assign_batch_date(comm_time: datetime, batch_window: str, batch_config: dict) -> str:
    """Return the date string the batch belongs to.

    If the comm arrives after the evening window, it's assigned to the next day's morning.
    """
    if batch_window == "morning" and comm_time.time() >= batch_config["evening"]["end"]:
        return (comm_time.date() + timedelta(days=1)).isoformat()
    return comm_time.date().isoformat()


# ─── Inbox Queries ───


async def get_comms_inbox(
    db,
    *,
    visibility: str = "normal",
    needs_response: bool | None = None,
    urgency: str | None = None,
    channel: str | None = None,
    member_id: str | None = None,
    batch_window: str | None = None,
    batch_date: str | None = None,
    draft_status: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Query comms inbox with multi-filter support.

    Returns comms sorted by urgency (urgent first), then date DESC.
    """
    conditions = ["visibility = ?"]
    params: list = [visibility]

    # Scope to member's accessible channels if channel registry exists
    if member_id:
        try:
            accessible_rows = await db.execute_fetchall(
                "SELECT channel_id FROM comms_channel_member_access "
                "WHERE member_id = ? AND show_in_inbox = 1",
                [member_id],
            )
            if accessible_rows:
                channel_ids = [r["channel_id"] for r in accessible_rows]
                placeholders = ",".join("?" * len(channel_ids))
                conditions.append(f"channel IN ({placeholders})")
                params.extend(channel_ids)
        except Exception:
            pass  # Table may not exist yet — no scoping

    if needs_response is not None:
        conditions.append("needs_response = ?")
        params.append(1 if needs_response else 0)

    if urgency:
        conditions.append("response_urgency = ?")
        params.append(urgency)

    if channel:
        conditions.append("channel = ?")
        params.append(channel)

    if member_id:
        conditions.append("member_id = ?")
        params.append(member_id)

    if batch_window:
        conditions.append("batch_window = ?")
        params.append(batch_window)

    if batch_date:
        conditions.append("batch_date = ?")
        params.append(batch_date)

    if draft_status and draft_status != "none":
        conditions.append("draft_status = ?")
        params.append(draft_status)

    if search:
        conditions.append("(summary LIKE ? OR body_snippet LIKE ? OR subject LIKE ?)")
        params.extend([f"%{search}%"] * 3)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT * FROM ops_comms
        WHERE {where}
        ORDER BY
            CASE response_urgency
                WHEN 'urgent' THEN 0
                WHEN 'timely' THEN 1
                WHEN 'normal' THEN 2
                WHEN 'fyi' THEN 3
                ELSE 4
            END,
            date DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    rows = await db.execute_fetchall(sql, params)
    return [dict(r) for r in rows]


async def get_comms_counts(db) -> dict:
    """Aggregate counts for badge display and batch status."""
    result = {
        "needs_response": 0,
        "urgent": 0,
        "drafts_pending": 0,
        "total_normal": 0,
        "by_batch": {},
    }

    row = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM ops_comms WHERE visibility = 'normal' AND needs_response = 1"
    )
    result["needs_response"] = row["c"] if row else 0

    row = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM ops_comms WHERE visibility = 'normal' AND response_urgency = 'urgent' AND needs_response = 1"
    )
    result["urgent"] = row["c"] if row else 0

    row = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM ops_comms WHERE draft_status = 'pending'"
    )
    result["drafts_pending"] = row["c"] if row else 0

    row = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM ops_comms WHERE visibility = 'normal'"
    )
    result["total_normal"] = row["c"] if row else 0

    # Batch breakdown for today
    today = now_et().date().isoformat()
    rows = await db.execute_fetchall(
        "SELECT batch_window, COUNT(*) as c FROM ops_comms "
        "WHERE batch_date = ? AND visibility = 'normal' GROUP BY batch_window",
        [today],
    )
    for r in rows:
        if r["batch_window"]:
            result["by_batch"][r["batch_window"]] = r["c"]

    return result


async def get_comm_by_id(db, comm_id: str) -> dict | None:
    """Fetch a single comm by ID."""
    row = await db.execute_fetchone(
        "SELECT * FROM ops_comms WHERE id = ?", [comm_id]
    )
    return dict(row) if row else None


# ─── State Transitions ───


async def mark_responded(db, comm_id: str, outcome: str = "responded") -> bool:
    """Mark a comm as responded to."""
    now = now_et().strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.execute(
        "UPDATE ops_comms SET needs_response = 0, responded_at = ?, outcome = ? WHERE id = ?",
        [now, outcome, comm_id],
    )
    await db.commit()
    await audit_log(db, "ops_comms", "UPDATE", comm_id, actor="user",
                    new_values=json.dumps({"outcome": outcome, "responded_at": now}))
    return True


async def snooze_comm(db, comm_id: str, until: str) -> bool:
    """Snooze a comm until a given datetime."""
    await db.execute(
        "UPDATE ops_comms SET snoozed_until = ?, visibility = 'snoozed' WHERE id = ?",
        [until, comm_id],
    )
    await db.commit()
    await audit_log(db, "ops_comms", "UPDATE", comm_id, actor="user",
                    new_values=json.dumps({"snoozed_until": until, "visibility": "snoozed"}))
    return True


async def unsnooze_due(db) -> int:
    """Restore visibility for comms whose snooze has expired. Returns count."""
    now = now_et().strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = await db.execute(
        "UPDATE ops_comms SET visibility = 'normal', snoozed_until = NULL "
        "WHERE visibility = 'snoozed' AND snoozed_until <= ?",
        [now],
    )
    await db.commit()
    return cursor.rowcount


async def archive_comm(db, comm_id: str) -> bool:
    """Archive a comm (hide from inbox)."""
    await db.execute(
        "UPDATE ops_comms SET visibility = 'archived' WHERE id = ?", [comm_id]
    )
    await db.commit()
    return True


async def tag_comm(db, comm_id: str, tag: str) -> bool:
    """Tag/categorize a comm via suggested_action field."""
    await db.execute(
        "UPDATE ops_comms SET suggested_action = ? WHERE id = ?",
        [tag, comm_id],
    )
    await db.commit()
    return True


# ─── Extraction Lifecycle ───


async def queue_extraction(db, comm_id: str) -> bool:
    """Mark a comm for extraction by the async worker."""
    await db.execute(
        "UPDATE ops_comms SET extraction_status = 'pending' WHERE id = ? AND extraction_status = 'none'",
        [comm_id],
    )
    await db.commit()
    return True


async def get_pending_extractions(db, limit: int = 20) -> list[dict]:
    """Fetch comms awaiting extraction."""
    rows = await db.execute_fetchall(
        "SELECT * FROM ops_comms WHERE extraction_status = 'pending' ORDER BY date ASC LIMIT ?",
        [limit],
    )
    return [dict(r) for r in rows]


async def save_extraction_result(db, comm_id: str, items: list[dict], confidence: float) -> bool:
    """Store extraction results on a comm."""
    await db.execute(
        "UPDATE ops_comms SET extraction_status = 'completed', "
        "extracted_items = ?, extraction_confidence = ? WHERE id = ?",
        [json.dumps(items), confidence, comm_id],
    )
    await db.commit()
    return True


async def mark_extraction_failed(db, comm_id: str) -> bool:
    """Mark extraction as failed for retry."""
    await db.execute(
        "UPDATE ops_comms SET extraction_status = 'failed' WHERE id = ?",
        [comm_id],
    )
    await db.commit()
    return True


async def approve_extraction(db, comm_id: str, index: int) -> dict | None:
    """Approve one extracted item by index. Returns the item for action execution.

    The caller (web layer or LLM tool) is responsible for actually creating
    the task/event/entity from the returned item data.
    """
    comm = await get_comm_by_id(db, comm_id)
    if not comm or not comm.get("extracted_items"):
        return None

    items = json.loads(comm["extracted_items"])
    if index < 0 or index >= len(items):
        return None

    items[index]["approved"] = True
    await db.execute(
        "UPDATE ops_comms SET extracted_items = ? WHERE id = ?",
        [json.dumps(items), comm_id],
    )
    await db.commit()
    await audit_log(db, "ops_comms", "UPDATE", comm_id, actor="user",
                    new_values=json.dumps({"action": "extraction_approved", "index": index, "item": items[index]}))
    return items[index]


async def reject_extraction(db, comm_id: str, index: int) -> bool:
    """Reject one extracted item by index."""
    comm = await get_comm_by_id(db, comm_id)
    if not comm or not comm.get("extracted_items"):
        return False

    items = json.loads(comm["extracted_items"])
    if index < 0 or index >= len(items):
        return False

    items[index]["rejected"] = True
    await db.execute(
        "UPDATE ops_comms SET extracted_items = ? WHERE id = ?",
        [json.dumps(items), comm_id],
    )
    await db.commit()
    return True


# ─── Draft Lifecycle ───


async def save_draft(db, comm_id: str, draft_text: str, voice_profile_id: str | None = None) -> bool:
    """Store a generated draft response on a comm."""
    await db.execute(
        "UPDATE ops_comms SET draft_response = ?, draft_status = 'pending', "
        "draft_voice_profile_id = ? WHERE id = ?",
        [draft_text, voice_profile_id, comm_id],
    )
    await db.commit()
    await audit_log(db, "ops_comms", "UPDATE", comm_id, actor="pib_agent",
                    new_values=json.dumps({"action": "draft_created", "draft_status": "pending"}))
    return True


async def approve_draft(db, comm_id: str, edited_body: str | None = None) -> dict | None:
    """Approve a draft for sending. Optionally replace with edited text.

    Returns the comm dict with final draft for the outbound adapter.
    """
    comm = await get_comm_by_id(db, comm_id)
    if not comm or comm.get("draft_status") != "pending":
        return None

    final_body = edited_body or comm["draft_response"]
    await db.execute(
        "UPDATE ops_comms SET draft_response = ?, draft_status = 'approved' WHERE id = ?",
        [final_body, comm_id],
    )
    await db.commit()
    await audit_log(db, "ops_comms", "UPDATE", comm_id, actor="user",
                    new_values=json.dumps({"action": "draft_approved", "draft_status": "approved", "edited": edited_body is not None}))

    # Route through outbound_router if channel registry is available
    updated_comm = await get_comm_by_id(db, comm_id)
    send_result = await _try_route_outbound(db, updated_comm, final_body)
    if send_result:
        updated_comm["send_result"] = send_result
    return updated_comm


async def reject_draft(db, comm_id: str) -> bool:
    """Reject a draft response."""
    await db.execute(
        "UPDATE ops_comms SET draft_status = 'rejected' WHERE id = ?",
        [comm_id],
    )
    await db.commit()
    await audit_log(db, "ops_comms", "UPDATE", comm_id, actor="user",
                    new_values=json.dumps({"action": "draft_rejected"}))
    return True


async def mark_draft_sending(db, comm_id: str) -> bool:
    """Transition approved draft to sending state."""
    await db.execute(
        "UPDATE ops_comms SET draft_status = 'sending' WHERE id = ? AND draft_status = 'approved'",
        [comm_id],
    )
    await db.commit()
    return True


async def mark_draft_sent(db, comm_id: str) -> bool:
    """Mark draft as successfully sent."""
    now = now_et().strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.execute(
        "UPDATE ops_comms SET draft_status = 'sent', outcome = 'responded', "
        "needs_response = 0, responded_at = ? WHERE id = ?",
        [now, comm_id],
    )
    await db.commit()
    return True


async def mark_draft_send_failed(db, comm_id: str) -> bool:
    """Mark draft send as failed for retry."""
    await db.execute(
        "UPDATE ops_comms SET draft_status = 'send_failed' WHERE id = ?",
        [comm_id],
    )
    await db.commit()
    return True


# ─── Manual Capture ───


async def capture_manual(db, member_id: str, data: dict) -> str:
    """Create an ops_comms entry from manual capture (meeting notes, transcripts, etc.).

    data should contain: summary, body_snippet, channel (optional), comm_type (optional),
    subject (optional), from_addr (optional).
    """
    comm_id = await next_id(db, "c")
    now = now_et().strftime("%Y-%m-%dT%H:%M:%SZ")

    batch_config = await get_batch_config(db)
    now_dt = now_et()
    window = assign_batch_window(now_dt, batch_config)
    b_date = assign_batch_date(now_dt, window, batch_config)

    await db.execute(
        """INSERT INTO ops_comms (
            id, date, channel, direction, from_addr, member_id,
            subject, summary, body_snippet, comm_type,
            batch_window, batch_date, visibility,
            extraction_status, source_classification,
            created_by, created_at
        ) VALUES (?, ?, ?, 'inbound', ?, ?, ?, ?, ?, ?, ?, ?, 'normal', 'pending', 'manual_capture', 'user', ?)""",
        [
            comm_id,
            now[:10],
            data.get("channel", "manual"),
            data.get("from_addr"),
            member_id,
            data.get("subject"),
            data["summary"],
            data.get("body_snippet", data["summary"]),
            data.get("comm_type", "meeting_note"),
            window,
            b_date,
            now,
        ],
    )
    await db.commit()
    await audit_log(db, "ops_comms", "INSERT", comm_id, actor="user",
                    source="manual_capture")
    return comm_id


# ─── Outbound Router Integration ───


async def _try_route_outbound(db, comm: dict, body: str) -> dict | None:
    """Attempt to route an approved draft through outbound_router.

    Returns the send result dict, or None if the channel registry
    isn't available (graceful fallback to old behavior).
    """
    try:
        from pib.outbound_router import route_outbound
        channel_id = comm.get("channel") or "unknown"
        result = await route_outbound(
            db,
            channel_id=channel_id,
            message=body,
            member_id=comm.get("member_id"),
            reply_to=comm.get("source_ref"),
        )
        log.info(f"Outbound route for comm {comm['id']}: {result.get('status')}")
        return result
    except Exception as e:
        # Channel registry tables may not exist yet — fall back gracefully
        log.debug(f"Outbound routing unavailable, falling back: {e}")
        return None


async def determine_best_channel(db, member_id: str, recipient_id: str | None = None) -> str:
    """Query channel registry for the best sendable channel for a member.

    Priority order:
    1. Member's reply_channel_default (from comms_channel_member_access)
    2. Highest-priority enabled channel with outbound capability
    3. Fallback to 'imessage' if registry unavailable

    Args:
        db: Database connection
        member_id: The requesting member
        recipient_id: The recipient member (if different from requester)

    Returns:
        Channel ID string
    """
    target = recipient_id or member_id
    try:
        # Try member's default reply channel first, ordered by sort_order
        row = await db.execute_fetchone(
            """SELECT cma.channel_id FROM comms_channel_member_access cma
               JOIN comms_channels cc ON cma.channel_id = cc.id
               WHERE cma.member_id = ? AND cma.access_level IN ('write','admin')
               AND cc.enabled = 1
               ORDER BY cc.sort_order ASC
               LIMIT 1""",
            [target],
        )
        if row:
            return row["channel_id"]
    except Exception:
        pass  # Tables may not exist

    try:
        # Fall back to any enabled outbound channel
        from pib.channels import ChannelRegistry
        registry = ChannelRegistry(db)
        await registry.load()
        sendable = registry.get_sendable()
        if sendable:
            return sendable[0].id
    except Exception:
        pass

    return "imessage"


async def dispatch_proactive_message(
    db, member_id: str, message: str, trigger_type: str
) -> dict | None:
    """Dispatch a proactive message through the outbound router.

    Finds the best outbound channel for the member and routes the message.
    Guardrails (quiet hours, rate limits) should be checked by the caller
    before invoking this function.

    Args:
        db: Database connection
        member_id: Recipient member ID
        message: Message body to send
        trigger_type: The proactive trigger name (for audit trail)

    Returns:
        Route result dict, or None if routing unavailable
    """
    try:
        from pib.outbound_router import route_outbound
        channel_id = await determine_best_channel(db, member_id)
        result = await route_outbound(
            db,
            channel_id=channel_id,
            message=message,
            member_id=member_id,
            metadata={"trigger_type": trigger_type, "source": "proactive"},
        )
        log.info(f"Proactive dispatch for {member_id} via {channel_id}: {result.get('status')}")
        return result
    except Exception as e:
        log.debug(f"Proactive dispatch unavailable: {e}")
        return None


# ─── Batch Helpers ───


async def assign_batch_to_comm(db, comm_id: str) -> str | None:
    """Assign batch window to an existing comm based on its date."""
    comm = await get_comm_by_id(db, comm_id)
    if not comm:
        return None

    batch_config = await get_batch_config(db)
    comm_dt = datetime.fromisoformat(comm["created_at"].replace("Z", "+00:00"))
    window = assign_batch_window(comm_dt, batch_config)
    b_date = assign_batch_date(comm_dt, window, batch_config)

    await db.execute(
        "UPDATE ops_comms SET batch_window = ?, batch_date = ? WHERE id = ?",
        [window, b_date, comm_id],
    )
    await db.commit()
    return window
