import threading
import psycopg2
import psycopg2.pool
from pgvector.psycopg2 import register_vector

from backend.config import DATABASE_URL

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_lock = threading.Lock()


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            _pool = psycopg2.pool.ThreadedConnectionPool(1, 20, DATABASE_URL)
    return _pool


def get_conn() -> psycopg2.extensions.connection:
    conn = get_pool().getconn()
    register_vector(conn)
    return conn


def put_conn(conn: psycopg2.extensions.connection) -> None:
    get_pool().putconn(conn)
