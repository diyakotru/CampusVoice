"""
SQL for the `admins` and `students` tables.

Passwords are hashed with werkzeug's generate_password_hash (scrypt with a
random salt). We store only the hash; check_password_hash re-hashes the
login attempt and compares. Even someone who steals the database cannot
read the original passwords.
"""
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_cursor

# A real hash of a random string. Used so a login for a username that does
# not exist takes as long as one with a wrong password — otherwise attackers
# could discover valid usernames by timing the responses.
_DUMMY_HASH = generate_password_hash("not-a-real-password-8f3a1c")


def hash_password(password):
    return generate_password_hash(password)


# ------------------------------------------------------------------ admins
def create_admin(username, password):
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO admins (username, password_hash) VALUES (%s, %s) "
            "ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash "
            "RETURNING id, username, created_at",
            (username, hash_password(password)),
        )
        return cur.fetchone()


def authenticate_admin(username, password):
    with get_cursor() as cur:
        cur.execute("SELECT id, username, password_hash FROM admins WHERE username = %s", (username,))
        admin = cur.fetchone()
    if admin is None:
        check_password_hash(_DUMMY_HASH, password)
        return None
    if not check_password_hash(admin["password_hash"], password):
        return None
    return {"id": admin["id"], "username": admin["username"]}


# ------------------------------------------------------------------ students
class StudentExists(Exception):
    pass


def create_student(data):
    from psycopg2 import errors

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO students (student_id, full_name, department, password_hash) "
                "VALUES (%s, %s, %s, %s) RETURNING id, student_id, full_name, department",
                (data["student_id"], data["full_name"], data["department"],
                 hash_password(data["password"])),
            )
            return cur.fetchone()
    except errors.UniqueViolation as exc:
        raise StudentExists() from exc


def authenticate_student(student_id, password):
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, student_id, full_name, department, password_hash FROM students WHERE student_id = %s",
            (student_id.upper(),),
        )
        student = cur.fetchone()
    # Google-only accounts have no password: they can never log in this way.
    if student is None or student["password_hash"] is None:
        check_password_hash(_DUMMY_HASH, password)
        return None
    if not check_password_hash(student["password_hash"], password):
        return None
    student.pop("password_hash")
    return dict(student)


# ------------------------------------------------------------------ Google sign-in
def find_student_by_google_sub(google_sub):
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, student_id, full_name, department FROM students WHERE google_sub = %s",
            (google_sub,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def create_google_student(data, google_sub, email):
    """A student account with no password, identified by its Google account."""
    from psycopg2 import errors

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO students (student_id, full_name, department, google_sub, email) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id, student_id, full_name, department",
                (data["student_id"], data["full_name"], data["department"], google_sub, email),
            )
            return cur.fetchone()
    except errors.UniqueViolation as exc:
        raise StudentExists() from exc
