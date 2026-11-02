"""
Test setup.

The tests run against a REAL PostgreSQL server, never a mock:
  * If TEST_DATABASE_URL is set, that database is used (it will be EMPTIED —
    never point it at your production Supabase database).
  * Otherwise a temporary local PostgreSQL is started with the `pgserver`
    package (pip install -r requirements-dev.txt).
The same database/schema.sql that you run on Supabase is applied first.
"""
import os
import sys
import tempfile
from pathlib import Path

import psycopg2
import pytest

BACKEND = Path(__file__).resolve().parent.parent
SCHEMA = BACKEND.parent / "database" / "schema.sql"
sys.path.insert(0, str(BACKEND))

_server = None
db_url = os.environ.get("TEST_DATABASE_URL")
if not db_url:
    import logging

    import pgserver
    logging.getLogger("pgserver").setLevel(logging.WARNING)  # quiet start/stop chatter
    _server = pgserver.get_server(tempfile.mkdtemp(prefix="cfs_pg_"), cleanup_mode="stop")
    db_url = _server.get_uri()

# Configure the app BEFORE importing it (config.py reads env vars at import time).
os.environ.update({
    "DATABASE_URL": db_url,
    "FLASK_ENV": "development",
    "SECRET_KEY": "test-secret-key-0123456789abcdef0123456789abcdef",
    "RATELIMIT_ENABLED": "true",
    "PROXY_COUNT": "0",
    "SERVE_FRONTEND": "true",
})

with psycopg2.connect(db_url) as _conn, _conn.cursor() as _cur:
    _cur.execute(SCHEMA.read_text(encoding="utf-8"))

import app as app_module  # noqa: E402
from extensions import limiter  # noqa: E402
from models import users  # noqa: E402

ADMIN_USER = "testadmin"
ADMIN_PASS = "Admin12345"


@pytest.fixture(scope="session")
def app():
    application = app_module.app
    application.config["TESTING"] = True
    return application


@pytest.fixture(autouse=True)
def clean_db(app):
    """Every test starts with empty tables, one admin and fresh rate-limit counters."""
    with psycopg2.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE feedback, students, admins RESTART IDENTITY CASCADE")
    with app.app_context():
        users.create_admin(ADMIN_USER, ADMIN_PASS)
        limiter.reset()
    limiter.enabled = False   # most tests submit many rows; see the rate_limited fixture
    yield


@pytest.fixture
def rate_limited():
    limiter.enabled = True
    yield
    limiter.enabled = False


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(app):
    c = app.test_client()
    r = c.post("/api/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, r.get_json()
    return c


@pytest.fixture
def db():
    """Direct database connection, used to check what was really stored."""
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    yield conn
    conn.close()


def valid_feedback(**overrides):
    data = {
        "student_name": "Priya Sharma",
        "student_id": "21cs045",
        "department": "Computer Science and Engineering",
        "semester": 5,
        "category": "Library",
        "rating": 4,
        "description": "The library has a good collection of books.",
        "suggestions": "Extend timings during exams.",
    }
    data.update(overrides)
    return data
