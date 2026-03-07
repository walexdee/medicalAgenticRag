import logging
from typing import Optional, List

from backend.config import MAX_HISTORY_TURNS
from backend.db import get_conn, put_conn

logger = logging.getLogger(__name__)


def init_history_schema() -> None:
    """Create the conversation_turns table (idempotent)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id              SERIAL PRIMARY KEY,
                    conversation_id TEXT      NOT NULL,
                    role            TEXT      NOT NULL,
                    content         TEXT      NOT NULL,
                    created_at      TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_conv_id
                ON conversation_turns(conversation_id)
            """)
            conn.commit()
    finally:
        put_conn(conn)


def get_history(conversation_id: Optional[str]) -> List[dict]:
    """Return the last MAX_HISTORY_TURNS turns for a conversation."""
    if not conversation_id:
        return []
    limit = MAX_HISTORY_TURNS * 2
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content FROM (
                    SELECT id, role, content
                    FROM conversation_turns
                    WHERE conversation_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                ) sub
                ORDER BY id ASC
                """,
                (conversation_id, limit),
            )
            rows = cur.fetchall()
        return [{"role": row[0], "content": row[1]} for row in rows]
    finally:
        put_conn(conn)


def save_turn(conversation_id: Optional[str], user_msg: str, assistant_msg: str) -> None:
    """Persist one user + assistant turn."""
    if not conversation_id:
        return
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversation_turns (conversation_id, role, content) VALUES (%s, %s, %s)",
                (conversation_id, "user", user_msg),
            )
            cur.execute(
                "INSERT INTO conversation_turns (conversation_id, role, content) VALUES (%s, %s, %s)",
                (conversation_id, "assistant", assistant_msg),
            )
            conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Save turn error: {e}")
        raise
    finally:
        put_conn(conn)
