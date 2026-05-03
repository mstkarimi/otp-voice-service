import asyncio
import aiosqlite
import time
import uuid
import os
import json
from typing import Optional, Dict, Any, List
from src.core.logger import get_logger

logger = get_logger()

_db_path: str = "/var/lib/otp-service/otp.db"
_db_conn: Optional[aiosqlite.Connection] = None


# Statuses that allow a retry by the developer
RETRYABLE_STATUSES = {"no_answer", "busy", "congestion", "failed", "unreachable", "rejected"}

# Final statuses (no more updates will arrive)
TERMINAL_STATUSES = {
    "completed", "no_answer", "busy", "congestion",
    "failed", "unreachable", "rejected", "cancelled",
}


async def init_db(path: str) -> None:
    global _db_path, _db_conn
    _db_path = path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _db_conn = await aiosqlite.connect(path)
    _db_conn.row_factory = aiosqlite.Row
    await _db_conn.execute("PRAGMA journal_mode=WAL")
    await _db_conn.execute("PRAGMA synchronous=NORMAL")
    await _create_tables()
    await _migrate_schema()
    await _create_indexes()
    logger.info(f"Database initialized at {path}")


async def _create_tables() -> None:
    """Create tables (idempotent). Indexes that reference newer columns are
    created in _create_indexes() after _migrate_schema() has run."""
    conn = await _get_conn()
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS otp_calls (
            request_id        TEXT PRIMARY KEY,
            mobile            TEXT NOT NULL,
            code              TEXT NOT NULL DEFAULT '',
            code_masked       TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'queued',
            channel           TEXT,
            hangup_cause      TEXT,
            asterisk_reason   TEXT,
            duration          INTEGER,
            retry_count       INTEGER NOT NULL DEFAULT 0,
            parent_request_id TEXT,
            created_at        REAL NOT NULL,
            updated_at        REAL NOT NULL,
            expires_at        REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS otp_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id  TEXT NOT NULL,
            event       TEXT NOT NULL,
            detail      TEXT,
            at          REAL NOT NULL
        );
    """)
    await conn.commit()


async def _create_indexes() -> None:
    conn = await _get_conn()
    await conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_otp_calls_mobile
            ON otp_calls(mobile, created_at);
        CREATE INDEX IF NOT EXISTS idx_otp_calls_expires
            ON otp_calls(expires_at);
        CREATE INDEX IF NOT EXISTS idx_otp_calls_channel
            ON otp_calls(channel);
        CREATE INDEX IF NOT EXISTS idx_otp_events_request
            ON otp_events(request_id, at);
    """)
    await conn.commit()


async def _migrate_schema() -> None:
    """Add columns to existing installs (idempotent)."""
    conn = await _get_conn()
    async with conn.execute("PRAGMA table_info(otp_calls)") as cur:
        cols = {row[1] for row in await cur.fetchall()}

    add = []
    if "code" not in cols:              add.append("ALTER TABLE otp_calls ADD COLUMN code TEXT NOT NULL DEFAULT ''")
    if "channel" not in cols:           add.append("ALTER TABLE otp_calls ADD COLUMN channel TEXT")
    if "asterisk_reason" not in cols:   add.append("ALTER TABLE otp_calls ADD COLUMN asterisk_reason TEXT")
    if "retry_count" not in cols:       add.append("ALTER TABLE otp_calls ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
    if "parent_request_id" not in cols: add.append("ALTER TABLE otp_calls ADD COLUMN parent_request_id TEXT")
    for stmt in add:
        try:
            await conn.execute(stmt)
        except Exception as e:
            logger.warning(f"Migration failed: {stmt} -- {e}")
    if add:
        await conn.commit()


async def _get_conn() -> aiosqlite.Connection:
    global _db_conn
    if _db_conn is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db_conn


async def create_call_record(
    mobile: str,
    code: str,
    code_masked: str,
    ttl_seconds: int = 300,
    parent_request_id: Optional[str] = None,
) -> str:
    conn = await _get_conn()
    request_id = str(uuid.uuid4())
    now = time.time()
    await conn.execute(
        """INSERT INTO otp_calls
           (request_id, mobile, code, code_masked, status, parent_request_id,
            created_at, updated_at, expires_at)
           VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?)""",
        (request_id, mobile, code, code_masked, parent_request_id, now, now, now + ttl_seconds),
    )
    await conn.commit()
    await add_event(request_id, "queued", None)
    return request_id


async def update_call_status(
    request_id: str,
    status: str,
    hangup_cause: Optional[str] = None,
    asterisk_reason: Optional[str] = None,
    duration: Optional[int] = None,
    channel: Optional[str] = None,
) -> bool:
    """Update status; returns True if a row was changed.

    Will not overwrite a terminal status with a non-terminal one.
    """
    conn = await _get_conn()
    record = await get_call_record(request_id)
    if record is None:
        return False
    if record["status"] in TERMINAL_STATUSES and status not in TERMINAL_STATUSES:
        return False  # don't go back from terminal

    fields = ["status=?", "updated_at=?"]
    values: List[Any] = [status, time.time()]
    if hangup_cause is not None:
        fields.append("hangup_cause=?"); values.append(hangup_cause)
    if asterisk_reason is not None:
        fields.append("asterisk_reason=?"); values.append(asterisk_reason)
    if duration is not None:
        fields.append("duration=?"); values.append(duration)
    if channel is not None:
        fields.append("channel=?"); values.append(channel)
    values.append(request_id)

    await conn.execute(
        f"UPDATE otp_calls SET {', '.join(fields)} WHERE request_id=?",
        tuple(values),
    )
    await conn.commit()
    return True


async def add_event(request_id: str, event: str, detail: Optional[str]) -> None:
    conn = await _get_conn()
    await conn.execute(
        "INSERT INTO otp_events (request_id, event, detail, at) VALUES (?,?,?,?)",
        (request_id, event, detail, time.time()),
    )
    await conn.commit()


async def get_events(request_id: str) -> List[Dict[str, Any]]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT event, detail, at FROM otp_events WHERE request_id=? ORDER BY at ASC",
        (request_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_call_record(request_id: str) -> Optional[Dict[str, Any]]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT * FROM otp_calls WHERE request_id=?", (request_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_call_by_channel(channel: str) -> Optional[Dict[str, Any]]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT * FROM otp_calls WHERE channel=? ORDER BY created_at DESC LIMIT 1",
        (channel,),
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def increment_retry(request_id: str) -> int:
    """Increment the retry_count of a record and return the new value."""
    conn = await _get_conn()
    await conn.execute(
        "UPDATE otp_calls SET retry_count = retry_count + 1, updated_at=? WHERE request_id=?",
        (time.time(), request_id),
    )
    await conn.commit()
    rec = await get_call_record(request_id)
    return rec["retry_count"] if rec else 0


async def cleanup_expired() -> int:
    conn = await _get_conn()
    now = time.time()
    cursor = await conn.execute("DELETE FROM otp_calls WHERE expires_at < ?", (now,))
    await conn.execute("DELETE FROM otp_events WHERE request_id NOT IN (SELECT request_id FROM otp_calls)")
    await conn.commit()
    count = cursor.rowcount
    if count > 0:
        logger.debug(f"Cleaned up {count} expired call records")
    return count


async def close_db() -> None:
    global _db_conn
    if _db_conn:
        await _db_conn.close()
        _db_conn = None
