import asyncio
import aiosqlite
import time
import uuid
import os
from typing import Optional, Dict, Any
from src.core.logger import get_logger

logger = get_logger()

_db_path: str = "/var/lib/otp-service/otp.db"
_db_conn: Optional[aiosqlite.Connection] = None


async def init_db(path: str) -> None:
    global _db_path, _db_conn
    _db_path = path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _db_conn = await aiosqlite.connect(path)
    _db_conn.row_factory = aiosqlite.Row
    await _db_conn.execute("PRAGMA journal_mode=WAL")
    await _db_conn.execute("PRAGMA synchronous=NORMAL")
    await _create_tables()
    logger.info(f"Database initialized at {path}")


async def _create_tables() -> None:
    conn = await _get_conn()
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS otp_calls (
            request_id   TEXT PRIMARY KEY,
            mobile       TEXT NOT NULL,
            code_masked  TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'queued',
            hangup_cause TEXT,
            duration     INTEGER,
            created_at   REAL NOT NULL,
            updated_at   REAL NOT NULL,
            expires_at   REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_otp_calls_mobile
            ON otp_calls(mobile, created_at);

        CREATE INDEX IF NOT EXISTS idx_otp_calls_expires
            ON otp_calls(expires_at);
    """)
    await conn.commit()


async def _get_conn() -> aiosqlite.Connection:
    global _db_conn
    if _db_conn is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db_conn


async def create_call_record(
    mobile: str,
    code_masked: str,
    ttl_seconds: int = 300,
) -> str:
    conn = await _get_conn()
    request_id = str(uuid.uuid4())
    now = time.time()
    await conn.execute(
        """INSERT INTO otp_calls
           (request_id, mobile, code_masked, status, created_at, updated_at, expires_at)
           VALUES (?, ?, ?, 'queued', ?, ?, ?)""",
        (request_id, mobile, code_masked, now, now, now + ttl_seconds),
    )
    await conn.commit()
    return request_id


async def update_call_status(
    request_id: str,
    status: str,
    hangup_cause: Optional[str] = None,
    duration: Optional[int] = None,
) -> None:
    conn = await _get_conn()
    now = time.time()
    await conn.execute(
        """UPDATE otp_calls
           SET status=?, hangup_cause=?, duration=?, updated_at=?
           WHERE request_id=?""",
        (status, hangup_cause, duration, now, request_id),
    )
    await conn.commit()


async def get_call_record(request_id: str) -> Optional[Dict[str, Any]]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT * FROM otp_calls WHERE request_id=?", (request_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def cleanup_expired() -> int:
    """حذف رکوردهای منقضی"""
    conn = await _get_conn()
    now = time.time()
    cursor = await conn.execute(
        "DELETE FROM otp_calls WHERE expires_at < ?", (now,)
    )
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
