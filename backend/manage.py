"""
Command-line helper for setting up the cloud database.

    python manage.py check-db        # can we reach the database? which tables exist?
    python manage.py init-db         # create tables/indexes from database/schema.sql
    python manage.py create-admin    # create (or reset the password of) an admin
    python manage.py seed-demo       # OPTIONAL: insert sample rows (student_id starts with DEMO-)
    python manage.py clear-demo      # delete those sample rows again

All commands use DATABASE_URL from backend/.env (or the environment).
"""
import argparse
import getpass
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2

from config import Config

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "database" / "schema.sql"


def connect():
    if not Config.DATABASE_URL:
        sys.exit("DATABASE_URL is not set. Copy backend/.env.example to backend/.env and fill it in.")
    kwargs = {"connect_timeout": 15}
    if "sslmode=" not in Config.DATABASE_URL and "supabase" in Config.DATABASE_URL:
        kwargs["sslmode"] = "require"
    try:
        return psycopg2.connect(Config.DATABASE_URL, **kwargs)
    except psycopg2.OperationalError as exc:
        sys.exit(f"Could not connect to the database:\n{exc}")


def check_db(_args):
    conn = connect()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT version(), current_database(), inet_server_addr()")
        version, dbname, addr = cur.fetchone()
        print(f"Connected to database '{dbname}' at {addr or 'local socket'}")
        print(f"Server: {version.split(' on ')[0]}")
        cur.execute("SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name")
        tables = [r[0] for r in cur.fetchall()]
        print("Tables:", ", ".join(tables) if tables else "(none — run: python manage.py init-db)")
        for table in ("feedback", "admins", "students"):
            if table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")  # table name from fixed list
                print(f"  {table:<9} {cur.fetchone()[0]} rows")
    conn.close()


def init_db(_args):
    conn = connect()
    with conn, conn.cursor() as cur:
        cur.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
    conn.close()
    print(f"Schema applied from {SCHEMA_FILE.name}. Tables: students, feedback, admins.")


def create_admin(args):
    from utils.validators import USERNAME_RE, validate_password
    from werkzeug.security import generate_password_hash

    username = args.username or input("Admin username: ").strip()
    if not USERNAME_RE.match(username):
        sys.exit("Username must be 3–50 characters: letters, digits, _ . -")
    password = args.password or getpass.getpass("Admin password (min 8 chars, letters + digits): ")
    errors = {}
    validate_password(password, errors)
    if errors:
        sys.exit(errors["password"])
    if not args.password and getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")

    conn = connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO admins (username, password_hash) VALUES (%s, %s) "
            "ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash "
            "RETURNING (xmax = 0) AS inserted",
            (username, generate_password_hash(password)),
        )
        inserted = cur.fetchone()[0]
    conn.close()
    print(f"Admin '{username}' {'created' if inserted else 'password updated'}.")


DEMO_TEXT = {
    "Faculty and Teaching": ["Lectures are well structured and doubts are cleared patiently.",
                             "Some subjects need more practical examples in class.",
                             "Lab sessions should start on time; theory classes are good."],
    "Infrastructure": ["Classrooms need better ventilation and working projectors.",
                       "Wi-Fi in the hostel block is very slow in the evenings.",
                       "New seminar hall is excellent and well maintained."],
    "Library": ["Good collection of reference books, but too few copies.",
                "Please extend library hours during exam weeks.",
                "Digital library access from home would be very helpful."],
    "Canteen": ["Food quality is good but queues are long at lunch time.",
                "Prices are reasonable; more healthy options would be nice.",
                "Hygiene near the serving counter needs improvement."],
    "Events and Workshops": ["The technical fest was very well organised.",
                             "More industry workshops on cloud and AI, please.",
                             "Event schedules should be announced earlier."],
    "Overall College Experience": ["Overall a supportive environment for learning.",
                                   "Placement training should start from third year.",
                                   "Good campus life, administration could be faster."],
}


def seed_demo(args):
    from utils.constants import DEPARTMENTS

    names = ["Aarav Sharma", "Diya Patel", "Rohan Gupta", "Ananya Iyer", "Kabir Singh",
             "Meera Nair", "Arjun Reddy", "Sara Khan", "Vihaan Joshi", "Isha Verma"]
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(args.count):
        category = random.choice(list(DEMO_TEXT))
        rows.append((
            random.choice(names), f"DEMO-{1000 + i}", random.choice(DEPARTMENTS[:7]),
            random.randint(1, 8), category, random.choices([1, 2, 3, 4, 5], [1, 2, 4, 6, 5])[0],
            random.choice(DEMO_TEXT[category]),
            random.choice([None, "Collect feedback every semester.", "Share action taken with students."]),
            now - timedelta(days=random.randint(0, 29), hours=random.randint(0, 23)),
        ))
    conn = connect()
    with conn, conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO feedback (student_name, student_id, department, semester, category, rating, "
            "description, suggestions, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            rows,
        )
    conn.close()
    print(f"Inserted {len(rows)} demo rows (student IDs DEMO-…). Remove with: python manage.py clear-demo")


def clear_demo(_args):
    conn = connect()
    with conn, conn.cursor() as cur:
        cur.execute("DELETE FROM feedback WHERE student_id LIKE %s", ("DEMO-%",))
        print(f"Deleted {cur.rowcount} demo rows.")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Cloud Feedback System – database helper")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-db", help="Test the database connection").set_defaults(func=check_db)
    sub.add_parser("init-db", help="Create tables from database/schema.sql").set_defaults(func=init_db)
    p = sub.add_parser("create-admin", help="Create or reset an admin account")
    p.add_argument("--username")
    p.add_argument("--password", help="(avoid on shared machines: visible in shell history)")
    p.set_defaults(func=create_admin)
    p = sub.add_parser("seed-demo", help="Insert sample feedback for demonstrations")
    p.add_argument("--count", type=int, default=40)
    p.set_defaults(func=seed_demo)
    sub.add_parser("clear-demo", help="Delete the sample feedback").set_defaults(func=clear_demo)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
