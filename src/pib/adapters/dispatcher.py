"""Message dispatcher — routes OutboundMessages to the right sender adapter."""

import logging

from pib.ingest import OutboundMessage

log = logging.getLogger(__name__)

# Channel → adapter name mapping
CHANNEL_MAP = {
    "imessage": "bluebubbles",
    "sms": "twilio",
    "email": "gmail",
}


async def send_message(message: OutboundMessage) -> dict:
    """Route an outbound message to the appropriate adapter.

    Args:
        message: OutboundMessage with channel, to, content

    Returns:
        Dict with {ok, ...adapter-specific fields}
    """
    from pib.adapters import get_adapter

    adapter_name = CHANNEL_MAP.get(message.channel)
    if not adapter_name:
        log.error(f"Unknown channel: {message.channel}")
        return {"ok": False, "error": f"Unknown channel: {message.channel}"}

    adapter = get_adapter(adapter_name)
    if not adapter:
        log.warning(f"No adapter registered for channel {message.channel} ({adapter_name})")
        return {"ok": False, "error": f"Adapter {adapter_name} not available"}

    try:
        result = await adapter.send(message)
        return result
    except Exception as e:
        log.error(f"Send failed via {adapter_name}: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


async def deliver_to_member(db, member_id: str, content: str, channel: str | None = None) -> dict:
    """Send a message to a household member using their preferred channel.

    Args:
        db: Database connection
        member_id: Member to deliver to (e.g. 'm-james')
        content: Message text
        channel: Override channel (defaults to member's preferred_channel)

    Returns:
        Dict with send result
    """
    # Look up member's preferred channel and contact info
    member = await db.execute_fetchone(
        "SELECT preferred_channel, phone, email, imessage_handle FROM common_members WHERE id = ?",
        [member_id],
    )
    if not member:
        return {"ok": False, "error": f"Member {member_id} not found"}

    member = dict(member)
    ch = channel or member.get("preferred_channel", "imessage")

    # Resolve the "to" address based on channel
    if ch == "imessage":
        to = member.get("imessage_handle") or member.get("phone") or member.get("email")
    elif ch == "sms":
        to = member.get("phone")
    elif ch == "email":
        to = member.get("email")
    else:
        to = None

    if not to:
        return {"ok": False, "error": f"No {ch} address for {member_id}"}

    msg = OutboundMessage(channel=ch, to=to, content=content, member_id=member_id)
    return await send_message(msg)
