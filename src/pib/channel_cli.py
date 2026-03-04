"""Channel management CLI commands.

Registered as subcommands in cli.py. Exposes the channel registry
to the terminal, console server, and OpenClaw agent routing.

Usage:
  python -m pib.cli channel-list $PIB_DB_PATH --json
  python -m pib.cli channel-enable $PIB_DB_PATH --json '{"channel_id":"gmail_personal"}'
  python -m pib.cli channel-disable $PIB_DB_PATH --json '{"channel_id":"gmail_personal"}'
  python -m pib.cli channel-status $PIB_DB_PATH --json '{"channel_id":"gmail_personal"}'
  python -m pib.cli channel-test $PIB_DB_PATH --json '{"channel_id":"gmail_personal"}'
  python -m pib.cli channel-onboarding $PIB_DB_PATH --json '{"channel_id":"gmail_personal"}'
  python -m pib.cli channel-step-done $PIB_DB_PATH --json '{"channel_id":"gmail_personal","step_key":"google_oauth"}'
  python -m pib.cli channel-add $PIB_DB_PATH --json '{"id":"gmail_laura","display_name":"Laura Gmail","adapter_id":"gmail_api","category":"conversational"}'
  python -m pib.cli channel-update $PIB_DB_PATH --json '{"channel_id":"gmail_personal","config":{"whitelist_mode":"strict"}}'
"""

import json
import logging

log = logging.getLogger(__name__)


async def cmd_channel_list(db, args: dict, agent_id: str) -> dict:
    """List all channels with their status and capabilities."""
    from pib.channels import ChannelRegistry

    registry = ChannelRegistry(db)
    await registry.load()

    category_filter = args.get("category")
    enabled_only = args.get("enabled_only", False)

    channels = registry.get_all()
    if category_filter:
        channels = [c for c in channels if c.category == category_filter]
    if enabled_only:
        channels = [c for c in channels if c.enabled]

    return {
        "channels": [
            {
                "id": ch.id,
                "display_name": ch.display_name,
                "icon": ch.icon,
                "category": ch.category,
                "adapter_id": ch.adapter_id,
                "enabled": ch.enabled,
                "setup_complete": ch.setup_complete,
                "status": ch.health.status,
                "capabilities": {
                    "inbound": ch.capabilities.can_inbound,
                    "outbound": ch.capabilities.can_outbound,
                    "draft": ch.capabilities.can_draft,
                    "extract": ch.capabilities.can_extract,
                    "voice_corpus": ch.capabilities.can_voice_corpus,
                },
                "privacy_level": ch.privacy_level,
                "sort_order": ch.sort_order,
            }
            for ch in channels
        ],
        "summary": {
            "total": len(channels),
            "enabled": sum(1 for c in channels if c.enabled),
            "can_send": sum(1 for c in channels if c.capabilities.can_outbound and c.enabled),
            "can_draft": sum(1 for c in channels if c.capabilities.can_draft and c.enabled),
        },
    }


async def cmd_channel_enable(db, args: dict, agent_id: str) -> dict:
    """Enable a channel after onboarding is complete."""
    from pib.channels import ChannelRegistry

    channel_id = args.get("channel_id")
    if not channel_id:
        return {"error": "channel_id is required"}

    registry = ChannelRegistry(db)
    await registry.load()
    return await registry.enable_channel(channel_id)


async def cmd_channel_disable(db, args: dict, agent_id: str) -> dict:
    """Disable a channel."""
    from pib.channels import ChannelRegistry

    channel_id = args.get("channel_id")
    if not channel_id:
        return {"error": "channel_id is required"}

    registry = ChannelRegistry(db)
    await registry.load()
    success = await registry.disable_channel(channel_id)
    return {"success": success, "channel_id": channel_id}


async def cmd_channel_status(db, args: dict, agent_id: str) -> dict:
    """Get full status for a specific channel."""
    from pib.channels import ChannelRegistry

    channel_id = args.get("channel_id")
    if not channel_id:
        return {"error": "channel_id is required"}

    registry = ChannelRegistry(db)
    await registry.load()
    ch = registry.get(channel_id)
    if not ch:
        return {"error": f"Unknown channel: {channel_id}"}

    return {
        "id": ch.id,
        "display_name": ch.display_name,
        "icon": ch.icon,
        "category": ch.category,
        "adapter_id": ch.adapter_id,
        "enabled": ch.enabled,
        "setup_complete": ch.setup_complete,
        "health": {
            "status": ch.health.status,
            "consecutive_failures": ch.health.consecutive_failures,
            "last_poll_at": ch.health.last_poll_at,
            "last_successful_at": ch.health.last_successful_at,
            "last_error": ch.health.last_error,
        },
        "capabilities": {
            "inbound": ch.capabilities.can_inbound,
            "outbound": ch.capabilities.can_outbound,
            "draft": ch.capabilities.can_draft,
            "extract": ch.capabilities.can_extract,
            "voice_corpus": ch.capabilities.can_voice_corpus,
            "auto_handle": ch.capabilities.can_auto_handle,
        },
        "behavior": {
            "brevity_mode": ch.behavior.brevity_mode,
            "max_context_messages": ch.behavior.max_context_messages,
            "model_hint": ch.behavior.model_hint,
            "format_hint": ch.behavior.format_hint,
        },
        "privacy_level": ch.privacy_level,
        "content_storage": ch.content_storage,
        "outbound_requires_approval": ch.outbound_requires_approval,
        "reply_channel_default": ch.reply_channel_default,
        "config": ch.config_json,
    }


async def cmd_channel_onboarding(db, args: dict, agent_id: str) -> dict:
    """Get onboarding status and steps for a channel."""
    from pib.channels import ChannelRegistry

    channel_id = args.get("channel_id")
    if not channel_id:
        return {"error": "channel_id is required"}

    registry = ChannelRegistry(db)
    await registry.load()
    return await registry.get_onboarding_status(channel_id)


async def cmd_channel_step_done(db, args: dict, agent_id: str) -> dict:
    """Mark an onboarding step as complete."""
    from pib.channels import ChannelRegistry

    channel_id = args.get("channel_id")
    step_key = args.get("step_key")
    if not channel_id or not step_key:
        return {"error": "channel_id and step_key are required"}

    registry = ChannelRegistry(db)
    await registry.load()
    success = await registry.complete_onboarding_step(channel_id, step_key)
    if not success:
        return {"error": f"Step {step_key} not found or already complete"}

    # Return updated onboarding status
    return await registry.get_onboarding_status(channel_id)


async def cmd_channel_test(db, args: dict, agent_id: str) -> dict:
    """Test a channel's adapter connectivity."""
    from pib.channels import ChannelRegistry

    channel_id = args.get("channel_id")
    if not channel_id:
        return {"error": "channel_id is required"}

    registry = ChannelRegistry(db)
    await registry.load()
    await registry.init_adapters()

    ch = registry.get(channel_id)
    if not ch:
        return {"error": f"Unknown channel: {channel_id}"}

    adapter = registry.get_adapter(channel_id)
    if not adapter:
        return {
            "channel_id": channel_id,
            "test": "skip",
            "reason": "No adapter registered or initialized",
        }

    try:
        reachable = await adapter.ping()
        return {
            "channel_id": channel_id,
            "test": "pass" if reachable else "fail",
            "adapter_id": ch.adapter_id,
        }
    except Exception as e:
        return {
            "channel_id": channel_id,
            "test": "error",
            "error": str(e),
        }


async def cmd_channel_add(db, args: dict, agent_id: str) -> dict:
    """Add a new channel to the registry."""
    from pib.channels import ChannelRegistry

    required = ["id", "display_name", "adapter_id"]
    for field in required:
        if not args.get(field):
            return {"error": f"{field} is required"}

    registry = ChannelRegistry(db)
    await registry.load()

    try:
        channel_id = await registry.add_channel(args)
        return {"success": True, "channel_id": channel_id}
    except ValueError as e:
        return {"error": str(e)}


async def cmd_channel_update(db, args: dict, agent_id: str) -> dict:
    """Update channel config."""
    from pib.channels import ChannelRegistry

    channel_id = args.get("channel_id")
    config = args.get("config", {})
    if not channel_id:
        return {"error": "channel_id is required"}

    registry = ChannelRegistry(db)
    await registry.load()
    success = await registry.update_config(channel_id, config)
    return {"success": success, "channel_id": channel_id}


async def cmd_channel_send_enum(db, args: dict, agent_id: str) -> dict:
    """Get the dynamic list of sendable channels (for LLM tool enum)."""
    from pib.channels import ChannelRegistry

    registry = ChannelRegistry(db)
    await registry.load()

    # If member_id provided, scope to that member's sendable channels
    member_id = args.get("member_id")
    if member_id:
        sendable = await registry.get_send_channel_enum_for_member(member_id)
        return {"channels": sendable, "member_id": member_id}

    sendable = registry.get_send_channel_enum()
    return {
        "channels": sendable,
        "icons": {ch.id: ch.icon for ch in registry.get_sendable()},
    }


# ═══════════════════════════════════════════════════════════════
# Member-scoped commands (migration 013)
# ═══════════════════════════════════════════════════════════════


async def cmd_channel_list_for_member(db, args: dict, agent_id: str) -> dict:
    """List channels visible to a specific member (their Console Inbox view).

    Usage: channel-member-list --json '{"member_id":"m-james","inbox_only":true}'
    """
    from pib.channels import ChannelRegistry

    member_id = args.get("member_id")
    if not member_id:
        return {"error": "member_id required"}

    registry = ChannelRegistry(db)
    await registry.load()

    inbox_only = args.get("inbox_only", True)
    channels = await registry.get_for_member(member_id, inbox_only=inbox_only)
    return {
        "member_id": member_id,
        "inbox_only": inbox_only,
        "channels": [
            {
                "id": ch["id"],
                "display_name": ch["display_name"],
                "icon": ch.get("icon", "💬"),
                "category": ch["category"],
                "status": ch.get("status", "inactive"),
                "enabled": bool(ch.get("enabled")),
                "access_level": ch["access_level"],
                "can_approve_drafts": bool(ch.get("can_approve_drafts")),
                "receives_proactive": bool(ch.get("receives_proactive")),
                "digest_include": bool(ch.get("digest_include")),
            }
            for ch in channels
        ],
    }


async def cmd_channel_grant_access(db, args: dict, agent_id: str) -> dict:
    """Grant a member access to a channel.

    Usage: channel-grant-access --json '{"channel_id":"imessage","member_id":"m-laura","access_level":"read"}'
    """
    from pib.channels import ChannelRegistry

    channel_id = args.get("channel_id")
    member_id = args.get("member_id")
    access_level = args.get("access_level", "read")
    if not channel_id or not member_id:
        return {"error": "channel_id and member_id required"}

    registry = ChannelRegistry(db)
    await registry.load()

    kwargs = {k: args[k] for k in (
        "show_in_inbox", "can_approve_drafts", "receives_proactive",
        "digest_include", "notify_on_urgent", "batch_window"
    ) if k in args}

    success = await registry.grant_member_access(channel_id, member_id, access_level, **kwargs)
    return {"success": success, "channel_id": channel_id, "member_id": member_id, "access_level": access_level}


async def cmd_channel_revoke_access(db, args: dict, agent_id: str) -> dict:
    """Revoke a member's access to a channel.

    Usage: channel-revoke-access --json '{"channel_id":"imessage","member_id":"m-nanny"}'
    """
    from pib.channels import ChannelRegistry

    channel_id = args.get("channel_id")
    member_id = args.get("member_id")
    if not channel_id or not member_id:
        return {"error": "channel_id and member_id required"}

    registry = ChannelRegistry(db)
    await registry.load()

    success = await registry.revoke_member_access(channel_id, member_id)
    return {"success": success, "channel_id": channel_id, "member_id": member_id}


async def cmd_channel_setup_member(db, args: dict, agent_id: str) -> dict:
    """Set up default channel access for a new member using a role template.

    Usage: channel-setup-member --json '{"member_id":"m-nanny","template":"nanny"}'
    Templates: parent, child, nanny, babysitter, default
    """
    from pib.channels import ChannelRegistry

    member_id = args.get("member_id")
    template = args.get("template", "default")
    if not member_id:
        return {"error": "member_id required"}

    registry = ChannelRegistry(db)
    await registry.load()

    granted = await registry.setup_member_channels(member_id, template)
    return {"success": True, "member_id": member_id, "template": template, "channels_granted": granted}


async def cmd_device_list(db, args: dict, agent_id: str) -> dict:
    """List all registered devices."""
    rows = await db.execute_fetchall("SELECT * FROM comms_devices WHERE active = 1 ORDER BY device_type")
    return {"devices": [dict(r) for r in (rows or [])]}


async def cmd_device_status(db, args: dict, agent_id: str) -> dict:
    """Update device status and propagate to channels.

    Usage: device-status --json '{"device_id":"pib-mac-mini","status":"offline"}'
    """
    from pib.channels import ChannelRegistry

    device_id = args.get("device_id")
    status = args.get("status")
    if not device_id or not status:
        return {"error": "device_id and status required"}

    await db.execute(
        "UPDATE comms_devices SET status = ?, last_seen_at = ? WHERE id = ?",
        [status, __import__("pib.tz", fromlist=["now_et"]).now_et().strftime("%Y-%m-%dT%H:%M:%SZ"), device_id],
    )
    await db.commit()

    registry = ChannelRegistry(db)
    await registry.load()
    await registry.propagate_device_status(device_id, status)

    affected = await registry.get_device_channels(device_id)
    return {"device_id": device_id, "status": status, "affected_channels": [ch.id for ch in affected]}


async def cmd_account_list(db, args: dict, agent_id: str) -> dict:
    """List all registered accounts."""
    member_id = args.get("member_id")
    if member_id:
        rows = await db.execute_fetchall(
            "SELECT * FROM comms_accounts WHERE owner_member_id = ? AND active = 1", [member_id]
        )
    else:
        rows = await db.execute_fetchall("SELECT * FROM comms_accounts WHERE active = 1")
    return {"accounts": [dict(r) for r in (rows or [])]}


# ═══════════════════════════════════════════════════════════════
# Registration map (for cli.py COMMAND_MAP)
# ═══════════════════════════════════════════════════════════════

CHANNEL_COMMANDS = {
    "channel-list": cmd_channel_list,
    "channel-enable": cmd_channel_enable,
    "channel-disable": cmd_channel_disable,
    "channel-status": cmd_channel_status,
    "channel-onboarding": cmd_channel_onboarding,
    "channel-step-done": cmd_channel_step_done,
    "channel-test": cmd_channel_test,
    "channel-add": cmd_channel_add,
    "channel-update": cmd_channel_update,
    "channel-send-enum": cmd_channel_send_enum,
    # Member-scoped (migration 013)
    "channel-member-list": cmd_channel_list_for_member,
    "channel-grant-access": cmd_channel_grant_access,
    "channel-revoke-access": cmd_channel_revoke_access,
    "channel-setup-member": cmd_channel_setup_member,
    # Device & account management
    "device-list": cmd_device_list,
    "device-status": cmd_device_status,
    "account-list": cmd_account_list,
}

# Governance gates for channel commands
CHANNEL_GATES = {
    "channel-list": True,       # Always allowed (read-only)
    "channel-status": True,
    "channel-onboarding": True,
    "channel-send-enum": True,
    "channel-test": True,
    "channel-enable": "confirm",    # Enabling a channel needs human yes
    "channel-disable": "confirm",
    "channel-add": "confirm",
    "channel-update": "confirm",
    "channel-step-done": True,      # Marking wizard steps is fine
    # Member-scoped
    "channel-member-list": True,    # Read-only
    "channel-grant-access": "confirm",
    "channel-revoke-access": "confirm",
    "channel-setup-member": "confirm",
    # Device & account
    "device-list": True,
    "device-status": True,         # Automated by health checks
    "account-list": True,
}
