"""Ingestion pipeline: adapters, prefix parser, micro-scripts, pipeline stages."""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

log = logging.getLogger(__name__)


# ─── IngestEvent ───

@dataclass
class IngestEvent:
    source: str
    timestamp: str
    idempotency_key: str
    raw: dict
    text: str | None = None
    member_id: str | None = None
    reply_channel: str | None = None
    reply_address: str | None = None


# ─── Adapter Protocol ───

class Adapter(Protocol):
    name: str
    source: str

    async def init(self) -> None: ...
    async def poll(self) -> list[IngestEvent]: ...
    async def ping(self) -> bool: ...
    async def send(self, message: "OutboundMessage") -> None: ...


@dataclass
class OutboundMessage:
    channel: str
    to: str
    content: str
    member_id: str | None = None
    metadata: dict = field(default_factory=dict)


# ─── Prefix Parser ───

PREFIX_RULES = [
    (r"^grocery:\s*(.+)", "lists", {"list_name": "grocery"}),
    (r"^costco:\s*(.+)", "lists", {"list_name": "costco"}),
    (r"^target:\s*(.+)", "lists", {"list_name": "target"}),
    (r"^hardware:\s*(.+)", "lists", {"list_name": "hardware"}),
    (r"^james:\s*(.+)", "tasks", {"assignee": "m-james"}),
    (r"^laura:\s*(.+)", "tasks", {"assignee": "m-laura"}),
    (r"^buy\s+(.+)", "tasks", {"item_type": "purchase"}),
    (r"^call\s+(.+)", "tasks", {"requires": "phone"}),
    (r"^remember\s+(.+)", "memory", {"action": "save_fact"}),
    (r"^meds\s*(taken)?", "state", {"action": "medication_taken"}),
    (r"^sleep\s+(great|okay|rough)", "state", {"action": "sleep_report"}),
]


def parse_prefix(text: str) -> dict | None:
    """Parse a prefix command. Returns {shape, content, metadata} or None."""
    text = text.strip()
    for pattern, shape, metadata in PREFIX_RULES:
        m = re.match(pattern, text, re.IGNORECASE)
        if m:
            return {
                "shape": shape,
                "content": m.group(1).strip() if m.lastindex else text,
                "metadata": metadata,
            }
    return None


# ─── Micro-Script Generator (deterministic, no LLM) ───

def generate_micro_script(task: dict, items_cache: dict | None = None) -> str:
    """Generate the first-physical-action instruction for a task."""
    items_cache = items_cache or {}
    item_type = task.get("item_type", "task")
    item = items_cache.get(task.get("item_ref")) if task.get("item_ref") else None

    if item_type == "appointment" and item and item.get("phone"):
        return f"Open phone \u2192 call {item['name']} at {item['phone']}"
    if item_type == "purchase":
        return f'Open browser \u2192 search "{task["title"]}"'
    if item_type == "research":
        return f'Open browser \u2192 search "{task["title"]}" \u2192 read top 3 results'
    if item_type == "decision":
        return f'Open notes \u2192 list pros/cons for: {task["title"]}'
    if task.get("requires") == "phone":
        return f'Pick up phone \u2192 "{task.get("waiting_on") or task["title"]}"'
    if task.get("requires") == "car" and task.get("location_text"):
        return f"Keys + wallet \u2192 car \u2192 {task['location_text']}"
    return f'Start: {task["title"]}'


# ─── Idempotency ───

def make_idempotency_key(source: str, identifier: str) -> str:
    """Generate a SHA256 idempotency key."""
    return hashlib.sha256(f"{source}:{identifier}".encode()).hexdigest()


async def is_duplicate(db, key_hash: str) -> bool:
    """Check if an event has already been processed."""
    row = await db.execute_fetchone(
        "SELECT 1 FROM common_idempotency_keys WHERE key_hash = ?", [key_hash]
    )
    return row is not None


async def record_idempotency(db, event: IngestEvent):
    """Record that an event has been processed."""
    await db.execute(
        "INSERT OR IGNORE INTO common_idempotency_keys (key_hash, source, original_id) VALUES (?, ?, ?)",
        [event.idempotency_key, event.source, event.raw.get("id")],
    )


# ─── Pipeline (8 stages) ───

async def ingest(event: IngestEvent, db, event_bus=None) -> list[dict]:
    """Main ingestion pipeline: dedup → parse → classify → privacy → write → observe → confirm."""
    actions = []

    # STAGE 1: DEDUP
    if await is_duplicate(db, event.idempotency_key):
        return [{"action": "skipped_duplicate"}]
    await record_idempotency(db, event)

    # STAGE 2: MEMBER RESOLUTION
    if not event.member_id:
        event.member_id = await resolve_member(db, event)

    # STAGE 3: PARSE (prefix commands first)
    if event.text:
        prefix_result = parse_prefix(event.text)
        if prefix_result:
            actions.append(await route_prefix(db, prefix_result, event))
            await db.commit()
            return actions

    # STAGE 4-8: Route through LLM for classification + response
    if event.text and event.member_id:
        channel = event.reply_channel or event.source
        try:
            from pib.llm import chat as llm_chat
            result = await llm_chat(db, event.text, event.member_id, channel)
            actions.append({
                "action": "llm_response",
                "response": result.get("response", ""),
                "session_id": result.get("session_id"),
                "tool_actions": result.get("actions", []),
            })
            # Queue outbound reply if there's a reply channel
            if event.reply_channel and event.reply_address and result.get("response"):
                actions.append({
                    "action": "outbound_reply",
                    "channel": event.reply_channel,
                    "to": event.reply_address,
                    "content": result["response"],
                })
        except Exception as e:
            log.error(f"LLM processing failed for ingest: {e}", exc_info=True)
            actions.append({
                "action": "queued_for_processing",
                "text": event.text,
                "member_id": event.member_id,
                "error": str(e),
            })

    await db.commit()
    return actions


async def resolve_member(db, event: IngestEvent) -> str | None:
    """Resolve event source to a member ID."""
    if event.member_id:
        return event.member_id

    # Try phone number lookup
    addr = event.raw.get("from") or event.raw.get("phone")
    if addr:
        row = await db.execute_fetchone(
            "SELECT id FROM common_members WHERE phone = ? OR imessage_handle = ?",
            [addr, addr],
        )
        if row:
            return row["id"]

    # Try email lookup
    email = event.raw.get("email") or event.raw.get("from_email")
    if email:
        row = await db.execute_fetchone(
            "SELECT id FROM common_members WHERE email = ?", [email]
        )
        if row:
            return row["id"]

    return None


async def route_prefix(db, prefix_result: dict, event: IngestEvent) -> dict:
    """Route a parsed prefix command to the right handler."""
    from pib.db import next_id

    shape = prefix_result["shape"]
    content = prefix_result["content"]
    metadata = prefix_result["metadata"]

    if shape == "lists":
        # Add items to a list
        items = [item.strip() for item in content.split(",")]
        for item_text in items:
            if item_text:
                item_id = await next_id(db, "lst")
                await db.execute(
                    "INSERT INTO ops_lists (id, list_name, item_text, added_by) VALUES (?, ?, ?, ?)",
                    [item_id, metadata["list_name"], item_text, event.member_id],
                )
        return {"action": "list_items_added", "list": metadata["list_name"], "count": len(items)}

    elif shape == "tasks":
        task_id = await next_id(db, "tsk")
        assignee = metadata.get("assignee", event.member_id or "m-james")
        micro = generate_micro_script({"title": content, **metadata})
        await db.execute(
            "INSERT INTO ops_tasks (id, title, assignee, item_type, micro_script, created_by, source_system) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [task_id, content, assignee, metadata.get("item_type", "task"), micro, "prefix_parser", event.source],
        )
        return {"action": "task_created", "task_id": task_id, "title": content}

    elif shape == "state":
        return {"action": "state_command", "command": metadata["action"], "value": content}

    elif shape == "memory":
        return {"action": "memory_save", "content": content}

    return {"action": "unknown_shape", "shape": shape}
