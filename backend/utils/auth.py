"""
Session helpers and route guards.

After a successful login we store the user's id in Flask's `session`.
Flask puts the session in a cookie that is cryptographically SIGNED with
SECRET_KEY, so a user can read nothing useful from it (HttpOnly) and cannot
forge or modify it — if they change one byte, the signature check fails and
the session is treated as empty.
"""
from functools import wraps

from flask import jsonify, request, session


def login_admin(admin):
    session.clear()              # prevents session fixation
    session.permanent = True     # expires after PERMANENT_SESSION_LIFETIME
    session["admin_id"] = admin["id"]
    session["admin_username"] = admin["username"]


def login_student(student):
    # keep an admin session if the same browser has one; replace student data
    session.pop("student_account_id", None)
    session.permanent = True
    session["student_account_id"] = student["id"]
    session["student_id"] = student["student_id"]
    session["student_name"] = student["full_name"]
    session["student_department"] = student["department"]


def logout_admin():
    for key in ("admin_id", "admin_username"):
        session.pop(key, None)


def logout_student():
    for key in ("student_account_id", "student_id", "student_name", "student_department"):
        session.pop(key, None)


def current_student():
    if "student_account_id" not in session:
        return None
    return {
        "id": session["student_account_id"],
        "student_id": session["student_id"],
        "full_name": session["student_name"],
        "department": session["student_department"],
    }


def admin_required(view):
    """Decorator: reject the request with 401 unless an admin is logged in."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return jsonify(error="Admin authentication required."), 401
        return view(*args, **kwargs)
    return wrapper


def student_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "student_account_id" not in session:
            return jsonify(error="Please log in as a student to continue."), 401
        return view(*args, **kwargs)
    return wrapper


def json_body_required(view):
    """
    State-changing endpoints only accept `Content-Type: application/json`.
    Browsers cannot send that content type cross-site without a CORS
    pre-flight check, which blocks CSRF attacks from other websites.
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not request.is_json:
            return jsonify(error="Content-Type must be application/json."), 415
        return view(*args, **kwargs)
    return wrapper
