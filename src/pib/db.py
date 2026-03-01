"""Database layer: WriteQueue, PRAGMAs, migrations, next_id()."""

import asyncio
import hashlib
import logging
import os
import time
from datetime import datetime
from glob import glob
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)

# PRAGMA configuration — applied once on connection open
PRAGMAS = [
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA busy_timeout = 5000",
    "PRAGMA foreign_keys = ON",
    "PRAGMA cache_size = -20000",  # 20MB
    "PRAGMA auto_vacuum = INCREMENTAL",
    "PRAGMA temp_store = MEMORY",
    "PRAGMA mmap_size = 268435456",  # 256MB
]

DB_PATH = os.environ.get("PIB_DB_PATH", "pib.db")
MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"


class PIBConnection:
    """Wrapper around aiosqlite.Connection with execute_fetchone/fetchall helpers."""

    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def execute(self, sql: str, params=None):
        if params:
            return await self._conn.execute(sql, params)
        return await self._conn.execute(sql)

    async def executescript(self, sql: str):
        return await self._conn.executescript(sql)

    async def execute_fetchone(self, sql: str, params=None):
        if params:
            cursor = await self._conn.execute(sql, params)
        else:
            cursor = await self._conn.execute(sql)
        return await cursor.fetchone()

    async def execute_fetchall(self, sql: str, params=None):
        if params:
            cursor = await self._conn.execute(sql, params)
        else:
            cursor = await self._conn.execute(sql)
        return await cursor.fetchall()

    async def commit(self):
        return await self._conn.commit()

    async def close(self):
        return await self._conn.close()

    @property
    def row_factory(self):
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self._conn.row_factory = value


async def get_connection(db_path: str | None = None) -> PIBConnection:
    """Open a database connection with PRAGMAs applied."""
    path = db_path or DB_PATH
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    for pragma in PRAGMAS:
        await conn.execute(pragma)
    return PIBConnection(conn)


async def apply_schema(db: aiosqlite.Connection, schema_path: str | None = None):
    """Apply the initial schema from migration file and record it as migration 1."""
    path = schema_path or str(MIGRATIONS_DIR / "001_initial_schema.sql")
    with open(path) as f:
        sql = f.read()
    await db.executescript(sql)
    # Record migration 001 so apply_migrations() doesn't re-apply it
    checksum = hashlib.sha256(sql.encode()).hexdigest()
    await db.execute(
        "INSERT OR IGNORE INTO meta_migrations (version, name, up_sql, down_sql, applied_at, checksum) "
        "VALUES (?, ?, ?, ?, datetime('now'), ?)",
        [1, "001_initial_schema.sql", sql, "-- no rollback for initial schema", checksum],
    )
    await db.commit()


async def apply_migrations(db: aiosqlite.Connection, migrations_dir: str | None = None):
    """Apply pending migrations in order."""
    mdir = migrations_dir or str(MIGRATIONS_DIR)
    migration_files = sorted(glob(os.path.join(mdir, "*.sql")))

    # Get current version
    try:
        row = await db.execute_fetchone(
            "SELECT MAX(version) as v FROM meta_migrations WHERE applied_at IS NOT NULL"
        )
        current_version = row["v"] or 0 if row else 0
    except Exception:
        # meta_migrations doesn't exist yet — apply initial schema
        current_version = 0

    for f in migration_files:
        version = int(os.path.basename(f).split("_")[0])
        if version <= current_version:
            continue

        content = open(f).read()
        parts = content.split("-- DOWN")
        up_sql = parts[0].strip()
        down_sql = parts[1].strip() if len(parts) > 1 else "-- no rollback defined"
        checksum = hashlib.sha256(up_sql.encode()).hexdigest()

        await db.executescript(up_sql)
        await db.execute(
            "INSERT OR IGNORE INTO meta_migrations (version, name, up_sql, down_sql, applied_at, checksum) "
            "VALUES (?, ?, ?, ?, datetime('now'), ?)",
            [version, os.path.basename(f), up_sql, down_sql, checksum],
        )
        await db.commit()
        log.info(f"Migration {version} applied: {os.path.basename(f)}")


# ─── ID Generation ───

async def next_id(db: aiosqlite.Connection, prefix: str) -> str:
    """Generate a sequential prefixed ID: tsk-00001, mem-00001, etc."""
    await db.execute(
        "INSERT INTO common_id_sequences (prefix, next_val) VALUES (?, 1) "
        "ON CONFLICT(prefix) DO UPDATE SET next_val = next_val + 1",
        [prefix],
    )
    row = await db.execute_fetchone(
        "SELECT next_val FROM common_id_sequences WHERE prefix = ?", [prefix]
    )
    return f"{prefix}-{row['next_val']:05d}"


# ─── Write Queue ───

class WriteQueue:
    """Batched write queue: flushes every 100ms or 50 items, whichever comes first.

    Single persistent connection for all writes. Reads can use separate connections.
    """

    def __init__(self, db: aiosqlite.Connection, flush_interval: float = 0.1, flush_size: int = 50):
        self._db = db
        self._queue: asyncio.Queue = asyncio.Queue()
        self._flush_interval = flush_interval
        self._flush_size = flush_size
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the background flush loop."""
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())

    async def stop(self):
        """Stop the flush loop and drain remaining items."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._flush()

    async def put(self, sql: str, params: list | None = None):
        """Queue a write operation."""
        await self._queue.put((sql, params or []))

    async def _flush_loop(self):
        while self._running:
            await asyncio.sleep(self._flush_interval)
            await self._flush()

    async def _flush(self):
        items = []
        while not self._queue.empty() and len(items) < self._flush_size:
            try:
                items.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if not items:
            return

        try:
            for sql, params in items:
                await self._db.execute(sql, params)
            await self._db.commit()
        except Exception as e:
            log.error(f"WriteQueue flush failed: {e}", exc_info=True)
            raise


# ─── Audit Log ───

async def audit_log(
    db: aiosqlite.Connection,
    table_name: str,
    operation: str,
    entity_id: str,
    actor: str = "system",
    old_values: str | None = None,
    new_values: str | None = None,
    source: str = "unknown",
):
    """Record an audit log entry."""
    await db.execute(
        "INSERT INTO common_audit_log (table_name, operation, entity_id, actor, old_values, new_values, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [table_name, operation, entity_id, actor, old_values, new_values, source],
    )


# ─── Config Helpers ───

async def get_config(db: aiosqlite.Connection, key: str, default: str | None = None) -> str | None:
    """Get a runtime config value from pib_config."""
    row = await db.execute_fetchone(
        "SELECT value FROM pib_config WHERE key = ?", [key]
    )
    return row["value"] if row else default


async def set_config(db: aiosqlite.Connection, key: str, value: str, actor: str = "system"):
    """Set a runtime config value."""
    await db.execute(
        "INSERT INTO pib_config (key, value, updated_at, updated_by) VALUES (?, ?, datetime('now'), ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at, updated_by = excluded.updated_by",
        [key, value, actor],
    )
    await db.commit()
