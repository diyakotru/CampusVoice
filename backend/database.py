"""
Database access layer.

The backend talks to Supabase PostgreSQL over the internet using psycopg2.
Opening a new TLS connection to a cloud database for every request is slow
(~100-300 ms), so we keep a small POOL of open connections and reuse them.

Usage in the rest of the code:

    with get_cursor() as cur:
        cur.execute("SELECT * FROM feedback WHERE id = %s", (feedback_id,))
        row = cur.fetchone()

The values are always passed separately from the SQL text (the second
argument to execute). psycopg2 sends them safely, so user input can never
change the meaning of the query — this is how SQL injection is prevented.
"""
import logging
import threading
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool

log = logging.getLogger(__name__)

_pool = None
_pool_lock = threading.Lock()
_dsn = None


class DatabaseUnavailable(Exception):
    """Raised when the cloud database cannot be reached."""


def init_db(app):
    """Remember the connection string; the pool is created lazily on first use."""
    global _dsn
    _dsn = app.config["DATABASE_URL"]
    app.extensions["db_pool_size"] = (app.config["DB_POOL_MIN"], app.config["DB_POOL_MAX"])


def _connect_kwargs():
    kwargs = {
        "dsn": _dsn,
        "connect_timeout": 10,
        "application_name": "cloud-feedback-system",
        # keep idle connections alive through NAT / load balancers
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }
    # Supabase requires TLS. Add sslmode=require unless the URL already chose one.
    if "sslmode=" not in _dsn and ("supabase.co" in _dsn or "supabase.com" in _dsn):
        kwargs["sslmode"] = "require"
    return kwargs


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                from flask import current_app
                minconn, maxconn = current_app.extensions.get("db_pool_size", (1, 5))
                try:
                    _pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, **_connect_kwargs())
                except psycopg2.OperationalError as exc:
                    log.error("Could not connect to database: %s", exc)
                    raise DatabaseUnavailable(str(exc)) from exc
    return _pool


def close_pool():
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


@contextmanager
def get_cursor(commit=False):
    """
    Borrow a connection from the pool and yield a cursor that returns rows
    as dictionaries. Commits when commit=True, rolls back on any error and
    always returns the connection to the pool.
    """
    pool = _get_pool()
    try:
        conn = pool.getconn()
    except psycopg2.pool.PoolError as exc:
        raise DatabaseUnavailable("Connection pool exhausted") from exc
    except psycopg2.OperationalError as exc:
        raise DatabaseUnavailable(str(exc)) from exc

    broken = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        if commit:
            conn.commit()
        else:
            conn.rollback()  # end the read-only transaction cleanly
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
        # The connection died (e.g. the cloud DB restarted, network blip).
        broken = True
        log.warning("Database connection lost: %s", exc)
        raise DatabaseUnavailable(str(exc)) from exc
    except Exception:
        try:
            conn.rollback()
        except psycopg2.Error:
            broken = True
        raise
    finally:
        # Throw away dead connections so the pool opens a fresh one next time.
        pool.putconn(conn, close=broken or conn.closed != 0)


def check_connection():
    """Used by /api/health to prove the backend can reach the cloud database."""
    with get_cursor() as cur:
        cur.execute("SELECT version() AS version, NOW() AS server_time, current_database() AS db")
        return cur.fetchone()
