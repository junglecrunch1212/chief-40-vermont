"""Outbound Router — Channel-aware message dispatching.

Routes outbound messages through the channel registry with:
- Capability checks (can the channel send?)
- Approval gates (does this channel require human confirmation?)
- Draft queueing (if approval required, save as draft)
- Adapter dispatch (send via the channel's adapter)

Usage:
    from pib.outbound_router import route_outbound
    
    result = await route_outbound(
        db,
        channel_id="whatsapp_james",
        message="Your task is ready: Clean kitchen counters",
        member_id="m-james",
    )
    
    if result["status"] == "pending_approval":
        # Draft created, awaiting user approval
    elif result["status"] == "sent":
        # Message sent successfully
    elif result["status"] == "error":
        # Send failed
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pib.adapters.dispatcher import send_message
from pib.channels import ChannelRegistry
from pib.db import audit_log, next_id
from pib.ingest import OutboundMessage
from pib.tz import now_et

log = logging.getLogger(__name__)


async def route_outbound(
    db,
    channel_id: str,
    message: str,
    member_id: str | None = None,
    subject: str | None = None,
    reply_to: str | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """Route an outbound message through the channel registry.
    
    Args:
        db: Database connection
        channel_id: Target channel ID
        message: Message body
        member_id: Recipient member ID (for member-scoped channels)
        subject: Subject line (for email channels)
        reply_to: Original comm ID if this is a reply
        metadata: Additional metadata (attachments, etc.)
    
    Returns:
        {
            "status": "sent" | "pending_approval" | "queued" | "error",
            "channel_id": str,
            "message_id": str | None,
            "error": str | None,
        }
    """
    registry = ChannelRegistry(db)
    await registry.load()
    
    channel = registry.get(channel_id)
    if not channel:
        return {
            "status": "error",
            "channel_id": channel_id,
            "error": f"Unknown channel: {channel_id}",
        }
    
    # Check channel is enabled
    if not channel.enabled:
        return {
            "status": "error",
            "channel_id": channel_id,
            "error": f"Channel {channel_id} is disabled",
        }
    
    # Check channel can send
    if not channel.capabilities.can_outbound:
        return {
            "status": "error",
            "channel_id": channel_id,
            "error": f"Channel {channel_id} does not support outbound messages",
        }
    
    # Check approval requirement
    if channel.outbound_requires_approval:
        # Create draft for approval
        draft_id = await _create_draft(
            db,
            channel_id=channel_id,
            member_id=member_id,
            message=message,
            subject=subject,
            reply_to=reply_to,
            metadata=metadata,
        )
        return {
            "status": "pending_approval",
            "channel_id": channel_id,
            "draft_id": draft_id,
            "message": "Draft created, awaiting approval",
        }
    
    # Auto-send (no approval required)
    try:
        message_id = await _dispatch_message(
            db,
            registry=registry,
            channel_id=channel_id,
            member_id=member_id,
            message=message,
            subject=subject,
            reply_to=reply_to,
            metadata=metadata,
        )
        return {
            "status": "sent",
            "channel_id": channel_id,
            "message_id": message_id,
        }
    except Exception as e:
        log.exception(f"Failed to send message via {channel_id}")
        return {
            "status": "error",
            "channel_id": channel_id,
            "error": str(e),
        }


async def _create_draft(
    db,
    channel_id: str,
    member_id: str | None,
    message: str,
    subject: str | None,
    reply_to: str | None,
    metadata: dict | None,
) -> str:
    """Create a draft comm entry for approval."""
    draft_id = await next_id(db, "draft")
    now = now_et().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    await db.execute(
        """INSERT INTO ops_comms
        (id, date, channel, direction, member_id, subject, summary, body_snippet,
         draft_status, draft_response, needs_response, visibility, created_by, created_at)
        VALUES (?, ?, ?, 'outbound', ?, ?, ?, ?, 'pending', ?, 0, 'draft', 'pib_agent', ?)""",
        [
            draft_id,
            now[:10],
            channel_id,
            member_id,
            subject or f"Outbound via {channel_id}",
            message[:200],
            message,
            message,
            now,
        ],
    )
    await db.commit()
    await audit_log(
        db, "ops_comms", "INSERT", draft_id, actor="pib_agent",
        new_values=json.dumps({"draft_status": "pending", "channel": channel_id}),
    )
    return draft_id


async def _dispatch_message(
    db,
    registry: ChannelRegistry,
    channel_id: str,
    member_id: str | None,
    message: str,
    subject: str | None,
    reply_to: str | None,
    metadata: dict | None,
) -> str:
    """Dispatch message via adapter and record result.
    
    1. Resolve channel to adapter via dispatcher
    2. Call dispatcher.send_message()
    3. Record in ops_comms with actual result status
    4. Return message ID
    """
    message_id = await next_id(db, "msg")
    now = now_et().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Resolve "to" address for the adapter
    to_addr = None
    if member_id:
        try:
            row = await db.execute_fetchone(
                "SELECT phone, email, imessage_handle FROM common_members WHERE id = ?",
                [member_id],
            )
            if row:
                m = dict(row)
                channel = registry.get(channel_id)
                ch_type = channel.adapter if channel else channel_id
                if ch_type in ("imessage", "bluebubbles"):
                    to_addr = m.get("imessage_handle") or m.get("phone")
                elif ch_type in ("email", "gmail"):
                    to_addr = m.get("email")
                else:
                    to_addr = m.get("phone") or m.get("email")
        except Exception:
            pass
    
    # Build outbound message and dispatch
    delivery_status = "sent"
    delivery_error = None
    try:
        outbound = OutboundMessage(
            channel=channel_id,
            to=to_addr or member_id or channel_id,
            content=message,
            member_id=member_id,
        )
        if subject:
            outbound.metadata = {"subject": subject}
        result = await send_message(outbound)
        if not result.get("ok", False):
            delivery_status = "failed"
            delivery_error = result.get("error", "Unknown delivery error")
            log.error(f"Delivery failed via {channel_id}: {delivery_error}")
    except Exception as e:
        delivery_status = "failed"
        delivery_error = str(e)
        log.exception(f"Delivery exception via {channel_id}")
    
    # Record comm with actual delivery status
    outcome = delivery_status
    await db.execute(
        """INSERT INTO ops_comms
        (id, date, channel, direction, member_id, subject, summary, body_snippet,
         draft_status, outcome, needs_response, visibility, created_by, created_at)
        VALUES (?, ?, ?, 'outbound', ?, ?, ?, ?, ?, ?, 0, 'sent', 'pib_agent', ?)""",
        [
            message_id,
            now[:10],
            channel_id,
            member_id,
            subject or f"Outbound via {channel_id}",
            message[:200],
            message,
            delivery_status,
            outcome,
            now,
        ],
    )
    await db.commit()
    await audit_log(
        db, "ops_comms", "INSERT", message_id, actor="pib_agent",
        new_values=json.dumps({"status": delivery_status, "channel": channel_id, "error": delivery_error}),
    )
    
    if delivery_status == "failed":
        raise RuntimeError(f"Delivery failed: {delivery_error}")
    
    return message_id


async def send_draft(db, draft_id: str) -> dict[str, Any]:
    """Send an approved draft.
    
    Called after user approves a draft via the console or CLI.
    """
    row = await db.execute_fetchone(
        "SELECT * FROM ops_comms WHERE id = ? AND draft_status = 'approved'",
        [draft_id],
    )
    if not row:
        return {"error": f"Draft {draft_id} not found or not approved"}
    
    draft = dict(row)
    
    registry = ChannelRegistry(db)
    await registry.load()
    
    try:
        message_id = await _dispatch_message(
            db,
            registry=registry,
            channel_id=draft["channel"],
            member_id=draft["member_id"],
            message=draft["draft_response"],
            subject=draft.get("subject"),
            reply_to=None,
            metadata=None,
        )
        
        # Update draft status
        await db.execute(
            "UPDATE ops_comms SET draft_status = 'sent', outcome = 'sent' WHERE id = ?",
            [draft_id],
        )
        await db.commit()
        
        return {
            "status": "sent",
            "draft_id": draft_id,
            "message_id": message_id,
        }
    except Exception as e:
        log.exception(f"Failed to send draft {draft_id}")
        await db.execute(
            "UPDATE ops_comms SET draft_status = 'send_failed' WHERE id = ?",
            [draft_id],
        )
        await db.commit()
        return {
            "status": "error",
            "draft_id": draft_id,
            "error": str(e),
        }
