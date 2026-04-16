"""Channel Registry — Unified omni-channel management.

All inbound/outbound comms routes through the channel registry.
Channels represent communication endpoints (WhatsApp, Gmail, iMessage, etc.)
with unified capabilities, health tracking, and per-member access control.

Architecture:
- Channel = endpoint definition (WhatsApp family group, James's Gmail, etc.)
- Adapter = protocol implementation (WhatsApp API, Gmail API, BlueBubbles, etc.)
- Device = physical/virtual device running an adapter (Mac Mini, cloud service, etc.)
- Account = credentials/identity (email address, phone number, API key, etc.)
- Member Access = per-member visibility, permissions, digest preferences

Usage:
    registry = ChannelRegistry(db)
    await registry.load()
    channels = registry.get_all()
    gmail = registry.get("gmail_personal")
    sendable = registry.get_sendable()
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from pib.db import next_id, audit_log

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════

@dataclass
class ChannelCapabilities:
    """What a channel can do."""
    can_inbound: bool = True
    can_outbound: bool = True
    can_draft: bool = True
    can_extract: bool = True
    can_voice_corpus: bool = False
    can_auto_handle: bool = False


@dataclass
class ChannelBehavior:
    """How PIB interacts with this channel."""
    brevity_mode: str = "normal"  # brief, normal, detailed
    max_context_messages: int = 10
    model_hint: str = "sonnet"    # sonnet, haiku, opus
    format_hint: str = "text"     # text, markdown, html


@dataclass
class ChannelHealth:
    """Health/connectivity status."""
    status: str = "inactive"      # active, degraded, offline, inactive, error
    consecutive_failures: int = 0
    last_poll_at: str | None = None
    last_successful_at: str | None = None
    last_error: str | None = None


@dataclass
class Channel:
    """A communication channel."""
    id: str
    display_name: str
    icon: str
    category: str                 # conversational, broadcast, capture, administrative
    adapter_id: str
    enabled: bool
    setup_complete: bool
    
    capabilities: ChannelCapabilities = field(default_factory=ChannelCapabilities)
    behavior: ChannelBehavior = field(default_factory=ChannelBehavior)
    health: ChannelHealth = field(default_factory=ChannelHealth)
    
    privacy_level: str = "full"   # full, metadata_only, none
    content_storage: str = "full" # full, metadata_only, none, encrypted
    outbound_requires_approval: bool = True
    reply_channel_default: bool = False
    sort_order: int = 100
    config_json: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# Channel Registry
# ═══════════════════════════════════════════════════════════════

class ChannelRegistry:
    """Unified channel registry with member-scoped access control."""
    
    def __init__(self, db):
        self.db = db
        self.channels: dict[str, Channel] = {}
        self.adapters: dict[str, Any] = {}  # adapter_id → adapter instance
    
    async def load(self) -> None:
        """Load all channels from database."""
        rows = await self.db.execute_fetchall("SELECT * FROM comms_channels")
        if not rows:
            return
        
        for row in rows:
            # Load health
            health_row = await self.db.execute_fetchone(
                "SELECT * FROM comms_channel_health WHERE channel_id = ?", [row["id"]]
            )
            health = ChannelHealth(
                status=health_row["status"] if health_row else "inactive",
                consecutive_failures=health_row["consecutive_failures"] if health_row else 0,
                last_poll_at=health_row["last_poll_at"] if health_row else None,
                last_successful_at=health_row["last_successful_at"] if health_row else None,
                last_error=health_row["last_error"] if health_row else None,
            )
            
            # Parse config JSON
            config = {}
            if row["config_json"]:
                try:
                    config = json.loads(row["config_json"])
                except json.JSONDecodeError:
                    log.warning(f"Invalid config_json for channel {row['id']}")
            
            # Extract capabilities from config
            caps_data = config.get("capabilities", {})
            # Handle both array format (["in","out"]) and dict format ({"can_inbound": true})
            if isinstance(caps_data, list):
                cap_set = set(caps_data)
                capabilities = ChannelCapabilities(
                    can_inbound="in" in cap_set,
                    can_outbound="out" in cap_set,
                    can_draft="draft" in cap_set,
                    can_extract="extract" in cap_set,
                    can_voice_corpus="voice" in cap_set,
                    can_auto_handle="auto_handle" in cap_set,
                )
            elif isinstance(caps_data, dict):
                capabilities = ChannelCapabilities(
                    can_inbound=caps_data.get("can_inbound", True),
                    can_outbound=caps_data.get("can_outbound", True),
                    can_draft=caps_data.get("can_draft", True),
                    can_extract=caps_data.get("can_extract", True),
                    can_voice_corpus=caps_data.get("can_voice_corpus", False),
                    can_auto_handle=caps_data.get("can_auto_handle", False),
                )
            else:
                capabilities = ChannelCapabilities()
            
            # Extract behavior from config
            behavior_data = config.get("behavior", {})
            behavior = ChannelBehavior(
                brevity_mode=behavior_data.get("brevity_mode", "normal"),
                max_context_messages=behavior_data.get("max_context_messages", 10),
                model_hint=behavior_data.get("model_hint", "sonnet"),
                format_hint=behavior_data.get("format_hint", "text"),
            )
            
            channel = Channel(
                id=row["id"],
                display_name=row["display_name"],
                icon=row["icon"] or "💬",
                category=row["category"],
                adapter_id=row["adapter_id"],
                enabled=bool(row["enabled"]),
                setup_complete=bool(row["setup_complete"]),
                capabilities=capabilities,
                behavior=behavior,
                health=health,
                privacy_level=row["privacy_level"],
                content_storage=row["content_storage"],
                outbound_requires_approval=bool(row["outbound_requires_approval"]),
                reply_channel_default=bool(row["reply_channel_default"]),
                sort_order=row["sort_order"],
                config_json=config,
            )
            self.channels[row["id"]] = channel
    
    def get_all(self) -> list[Channel]:
        """Return all channels sorted by sort_order."""
        return sorted(self.channels.values(), key=lambda c: c.sort_order)
    
    def get(self, channel_id: str) -> Channel | None:
        """Get a channel by ID."""
        return self.channels.get(channel_id)
    
    def get_sendable(self) -> list[Channel]:
        """Return channels that can send (enabled + can_outbound)."""
        return [
            c for c in self.get_all()
            if c.enabled and c.capabilities.can_outbound
        ]
    
    async def enable_channel(self, channel_id: str) -> dict:
        """Enable a channel after onboarding is complete."""
        channel = self.get(channel_id)
        if not channel:
            return {"error": f"Unknown channel: {channel_id}"}
        
        if not channel.setup_complete:
            return {"error": f"Channel {channel_id} onboarding not complete"}
        
        await self.db.execute(
            "UPDATE comms_channels SET enabled = 1, updated_at = ? WHERE id = ?",
            [__import__("pib.tz", fromlist=["now_et"]).now_et().strftime("%Y-%m-%dT%H:%M:%SZ"), channel_id],
        )
        await self.db.commit()
        await audit_log(self.db, "comms_channels", "UPDATE", channel_id, actor="user",
                        new_values=json.dumps({"enabled": True}))
        
        channel.enabled = True
        return {"success": True, "channel_id": channel_id, "enabled": True}
    
    async def disable_channel(self, channel_id: str) -> bool:
        """Disable a channel."""
        channel = self.get(channel_id)
        if not channel:
            return False
        
        await self.db.execute(
            "UPDATE comms_channels SET enabled = 0, updated_at = ? WHERE id = ?",
            [__import__("pib.tz", fromlist=["now_et"]).now_et().strftime("%Y-%m-%dT%H:%M:%SZ"), channel_id],
        )
        await self.db.commit()
        await audit_log(self.db, "comms_channels", "UPDATE", channel_id, actor="user",
                        new_values=json.dumps({"enabled": False}))
        
        channel.enabled = False
        return True
    
    async def get_onboarding_status(self, channel_id: str) -> dict:
        """Get onboarding status and steps for a channel."""
        channel = self.get(channel_id)
        if not channel:
            return {"error": f"Unknown channel: {channel_id}"}
        
        rows = await self.db.execute_fetchall(
            "SELECT * FROM comms_onboarding_steps WHERE channel_id = ? ORDER BY step_number",
            [channel_id],
        )
        steps = [dict(r) for r in rows] if rows else []
        
        completed = sum(1 for s in steps if s["status"] == "completed")
        total = len(steps)
        
        return {
            "channel_id": channel_id,
            "setup_complete": channel.setup_complete,
            "steps": steps,
            "completed": completed,
            "total": total,
            "progress": completed / total if total > 0 else 0,
        }
    
    async def complete_onboarding_step(self, channel_id: str, step_key: str) -> bool:
        """Mark an onboarding step as complete."""
        row = await self.db.execute_fetchone(
            "SELECT * FROM comms_onboarding_steps WHERE channel_id = ? AND step_key = ?",
            [channel_id, step_key],
        )
        if not row or row["status"] == "completed":
            return False
        
        await self.db.execute(
            "UPDATE comms_onboarding_steps SET status = 'completed', completed_at = ? WHERE channel_id = ? AND step_key = ?",
            [__import__("pib.tz", fromlist=["now_et"]).now_et().strftime("%Y-%m-%dT%H:%M:%SZ"), channel_id, step_key],
        )
        await self.db.commit()
        
        # Check if all steps are complete
        rows = await self.db.execute_fetchall(
            "SELECT status FROM comms_onboarding_steps WHERE channel_id = ?", [channel_id]
        )
        if rows and all(r["status"] == "completed" for r in rows):
            await self.db.execute(
                "UPDATE comms_channels SET setup_complete = 1, updated_at = ? WHERE id = ?",
                [__import__("pib.tz", fromlist=["now_et"]).now_et().strftime("%Y-%m-%dT%H:%M:%SZ"), channel_id],
            )
            await self.db.commit()
            if channel_id in self.channels:
                self.channels[channel_id].setup_complete = True
        
        return True
    
    async def init_adapters(self) -> None:
        """Initialize adapter instances for enabled channels.
        
        Note: Actual adapter implementation is deferred.
        This stub allows the CLI to call init_adapters() without error.
        """
        log.info("Adapter initialization stub called (no-op)")
    
    def get_adapter(self, channel_id: str) -> Any | None:
        """Get adapter instance for a channel.
        
        Returns None (stub). Real adapters will be implemented separately.
        """
        channel = self.get(channel_id)
        if not channel:
            return None
        return self.adapters.get(channel.adapter_id)
    
    async def add_channel(self, data: dict) -> str:
        """Add a new channel to the registry."""
        required = ["id", "display_name", "adapter_id"]
        for field in required:
            if not data.get(field):
                raise ValueError(f"{field} is required")
        
        if data["id"] in self.channels:
            raise ValueError(f"Channel {data['id']} already exists")
        
        channel_id = data["id"]
        await self.db.execute(
            """INSERT INTO comms_channels 
            (id, display_name, icon, category, adapter_id, enabled, setup_complete, 
             privacy_level, content_storage, outbound_requires_approval, 
             reply_channel_default, sort_order, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                channel_id,
                data["display_name"],
                data.get("icon", "💬"),
                data.get("category", "conversational"),
                data["adapter_id"],
                data.get("enabled", 0),
                data.get("setup_complete", 0),
                data.get("privacy_level", "full"),
                data.get("content_storage", "full"),
                data.get("outbound_requires_approval", 1),
                data.get("reply_channel_default", 0),
                data.get("sort_order", 100),
                json.dumps(data.get("config", {})),
            ],
        )
        await self.db.commit()
        await audit_log(self.db, "comms_channels", "INSERT", channel_id, actor="user")
        
        # Reload
        await self.load()
        return channel_id
    
    async def update_config(self, channel_id: str, config: dict) -> bool:
        """Update channel config JSON."""
        channel = self.get(channel_id)
        if not channel:
            return False
        
        # Merge with existing config
        merged = {**channel.config_json, **config}
        
        await self.db.execute(
            "UPDATE comms_channels SET config_json = ?, updated_at = ? WHERE id = ?",
            [json.dumps(merged), __import__("pib.tz", fromlist=["now_et"]).now_et().strftime("%Y-%m-%dT%H:%M:%SZ"), channel_id],
        )
        await self.db.commit()
        await audit_log(self.db, "comms_channels", "UPDATE", channel_id, actor="user",
                        new_values=json.dumps({"config": merged}))
        
        channel.config_json = merged
        return True
    
    def get_send_channel_enum(self) -> list[str]:
        """Return dynamic enum of sendable channel IDs for LLM tool schemas."""
        return [c.id for c in self.get_sendable()]
    
    async def get_send_channel_enum_for_member(self, member_id: str) -> list[str]:
        """Return sendable channels scoped to a member's access."""
        rows = await self.db.execute_fetchall(
            """SELECT c.id FROM comms_channels c
            JOIN comms_channel_member_access a ON c.id = a.channel_id
            WHERE a.member_id = ? AND c.enabled = 1 AND a.access_level IN ('write','admin')""",
            [member_id],
        )
        return [r["id"] for r in rows] if rows else []
    
    async def get_for_member(self, member_id: str, inbox_only: bool = True) -> list[dict]:
        """Get channels visible to a specific member with their access metadata."""
        condition = "AND a.show_in_inbox = 1" if inbox_only else ""
        
        rows = await self.db.execute_fetchall(
            f"""SELECT c.*, a.access_level, a.show_in_inbox, a.can_approve_drafts,
                       a.receives_proactive, a.digest_include, a.notify_on_urgent,
                       a.batch_window, h.status
            FROM comms_channels c
            JOIN comms_channel_member_access a ON c.id = a.channel_id
            LEFT JOIN comms_channel_health h ON c.id = h.channel_id
            WHERE a.member_id = ? {condition}
            ORDER BY c.sort_order""",
            [member_id],
        )
        return [dict(r) for r in rows] if rows else []
    
    async def grant_member_access(
        self,
        channel_id: str,
        member_id: str,
        access_level: str = "read",
        **kwargs
    ) -> bool:
        """Grant a member access to a channel."""
        channel = self.get(channel_id)
        if not channel:
            return False
        
        access_id = await next_id(self.db, "ma")
        
        await self.db.execute(
            """INSERT INTO comms_channel_member_access
            (id, member_id, channel_id, access_level, show_in_inbox, can_approve_drafts,
             receives_proactive, digest_include, notify_on_urgent, batch_window)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(member_id, channel_id) DO UPDATE SET
                access_level = excluded.access_level,
                show_in_inbox = excluded.show_in_inbox,
                can_approve_drafts = excluded.can_approve_drafts,
                receives_proactive = excluded.receives_proactive,
                digest_include = excluded.digest_include,
                notify_on_urgent = excluded.notify_on_urgent,
                batch_window = excluded.batch_window,
                updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')""",
            [
                access_id,
                member_id,
                channel_id,
                access_level,
                kwargs.get("show_in_inbox", 1),
                kwargs.get("can_approve_drafts", 0),
                kwargs.get("receives_proactive", 1),
                kwargs.get("digest_include", 1),
                kwargs.get("notify_on_urgent", 1),
                kwargs.get("batch_window"),
            ],
        )
        await self.db.commit()
        await audit_log(self.db, "comms_channel_member_access", "UPSERT", access_id,
                        actor="user", new_values=json.dumps({"member_id": member_id, "channel_id": channel_id}))
        return True
    
    async def revoke_member_access(self, channel_id: str, member_id: str) -> bool:
        """Revoke a member's access to a channel."""
        await self.db.execute(
            "DELETE FROM comms_channel_member_access WHERE channel_id = ? AND member_id = ?",
            [channel_id, member_id],
        )
        await self.db.commit()
        return True
    
    async def setup_member_channels(self, member_id: str, template: str = "default") -> list[str]:
        """Set up default channel access for a new member using a role template.
        
        Templates:
        - parent: full access to household channels
        - child: limited access (no financial, no drafts)
        - nanny: WhatsApp + webconsole only, no email
        - babysitter: WhatsApp family only
        - default: read-only on all conversational channels
        """
        templates = {
            "parent": {
                "channels": ["whatsapp_family", "imessage", "webconsole"],
                "access_level": "admin",
                "show_in_inbox": True,
                "can_approve_drafts": True,
                "receives_proactive": True,
            },
            "child": {
                "channels": ["whatsapp_family", "imessage"],
                "access_level": "read",
                "show_in_inbox": True,
                "can_approve_drafts": False,
                "receives_proactive": False,
            },
            "nanny": {
                "channels": ["whatsapp_family", "webconsole"],
                "access_level": "write",
                "show_in_inbox": True,
                "can_approve_drafts": False,
                "receives_proactive": True,
            },
            "babysitter": {
                "channels": ["whatsapp_family"],
                "access_level": "write",
                "show_in_inbox": True,
                "can_approve_drafts": False,
                "receives_proactive": False,
            },
            "default": {
                "channels": [c.id for c in self.get_all() if c.category == "conversational"],
                "access_level": "read",
                "show_in_inbox": True,
                "can_approve_drafts": False,
                "receives_proactive": False,
            },
        }
        
        config = templates.get(template, templates["default"])
        granted = []
        
        for channel_id in config["channels"]:
            if channel_id not in self.channels:
                continue
            
            await self.grant_member_access(
                channel_id,
                member_id,
                access_level=config["access_level"],
                show_in_inbox=config["show_in_inbox"],
                can_approve_drafts=config["can_approve_drafts"],
                receives_proactive=config["receives_proactive"],
            )
            granted.append(channel_id)
        
        return granted
    
    async def propagate_device_status(self, device_id: str, status: str) -> None:
        """Update health status for all channels linked to a device."""
        rows = await self.db.execute_fetchall(
            "SELECT channel_id FROM comms_channel_devices WHERE device_id = ?",
            [device_id],
        )
        if not rows:
            return
        
        for row in rows:
            channel_id = row["channel_id"]
            await self.db.execute(
                "UPDATE comms_channel_health SET status = ?, updated_at = ? WHERE channel_id = ?",
                [status, __import__("pib.tz", fromlist=["now_et"]).now_et().strftime("%Y-%m-%dT%H:%M:%SZ"), channel_id],
            )
            
            if channel_id in self.channels:
                self.channels[channel_id].health.status = status
        
        await self.db.commit()
    
    async def get_device_channels(self, device_id: str) -> list[Channel]:
        """Get all channels linked to a device."""
        rows = await self.db.execute_fetchall(
            "SELECT channel_id FROM comms_channel_devices WHERE device_id = ?",
            [device_id],
        )
        if not rows:
            return []
        
        return [self.channels[r["channel_id"]] for r in rows if r["channel_id"] in self.channels]
