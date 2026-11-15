"""
/api/student endpoints — optional student accounts for the history page.

    POST /api/student/register
    POST /api/student/login
    POST /api/student/logout
    GET  /api/student/me
    GET  /api/student/feedback   – the logged-in student's own submissions only

    POST /api/student/google            – "Sign in with Google" (body: {credential})
    POST /api/student/google/complete   – first Google sign-in: add Student ID + department
"""
import time

from flask import Blueprint, current_app, jsonify, request, session

from extensions import limiter
from models import feedback as feedback_model
from models import users
from utils import google_auth
from utils.auth import (current_student, json_body_required, login_student,
                        logout_student, student_required)
from utils.validators import (validate_google_profile, validate_login,
                              validate_student_registration)

bp = Blueprint("student", __name__, url_prefix="/api/student")

# How long a verified-but-not-yet-registered Google identity stays usable
# for the "complete your profile" step.
GOOGLE_PENDING_SECONDS = 15 * 60


@bp.post("/register")
@limiter.limit("5 per minute; 20 per hour")
@json_body_required
def register():
    data, errors = validate_student_registration(request.get_json(silent=True))
    if errors:
        return jsonify(error="Please correct the highlighted fields.", fields=errors), 400
    try:
        student = users.create_student(data)
    except users.StudentExists:
        return jsonify(error="An account with this Student ID already exists.",
                       fields={"student_id": "This Student ID is already registered."}), 409
    login_student(student)
    return jsonify(message="Account created.", student=current_student()), 201


@bp.post("/login")
@limiter.limit("10 per minute; 40 per hour")
@json_body_required
def login():
    data, errors = validate_login(request.get_json(silent=True), "student_id")
    if errors:
        return jsonify(error="Student ID and password are required.", fields=errors), 400
    student = users.authenticate_student(data["student_id"], data["password"])
    if student is None:
        return jsonify(error="Invalid Student ID or password."), 401
    login_student(student)
    return jsonify(message="Login successful.", student=current_student())


@bp.post("/google")
@limiter.limit("10 per minute; 40 per hour")
@json_body_required
def google_login():
    """
    The browser sends the ID token Google gave it. We verify it ourselves.
      * Known Google account  → logged in (200, needs_profile = false)
      * New Google account    → remembered in the signed session cookie and
                                 the page asks for Student ID + department
                                 (200, needs_profile = true)
    """
    client_id = current_app.config["GOOGLE_CLIENT_ID"]
    if not client_id:
        return jsonify(error="Google sign-in is not enabled on this server."), 404
    body = request.get_json(silent=True)
    credential = body.get("credential") if isinstance(body, dict) else None
    try:
        identity = google_auth.verify_google_token(credential, client_id)
    except google_auth.InvalidGoogleToken:
        return jsonify(error="Google sign-in failed. Please try again."), 401

    student = users.find_student_by_google_sub(identity["sub"])
    if student:
        login_student(student)
        return jsonify(message="Login successful.", needs_profile=False, student=current_student())

    session["google_pending"] = {**identity, "at": int(time.time())}
    return jsonify(needs_profile=True, email=identity["email"], full_name=identity["name"])


@bp.post("/google/complete")
@limiter.limit("5 per minute; 20 per hour")
@json_body_required
def google_complete():
    pending = session.get("google_pending")
    if not pending or time.time() - pending.get("at", 0) > GOOGLE_PENDING_SECONDS:
        session.pop("google_pending", None)
        return jsonify(error="Your Google sign-in expired. Please sign in with Google again."), 401

    data, errors = validate_google_profile(request.get_json(silent=True))
    if errors:
        return jsonify(error="Please correct the highlighted fields.", fields=errors), 400
    try:
        student = users.create_google_student(data, pending["sub"], pending["email"])
    except users.StudentExists:
        # Never attach a Google account to someone else's existing Student ID.
        return jsonify(error="This Student ID is already registered. Log in with your Student ID and password.",
                       fields={"student_id": "This Student ID is already registered."}), 409
    login_student(student)
    return jsonify(message="Account created.", student=current_student()), 201


@bp.post("/logout")
@json_body_required
def logout():
    logout_student()
    return jsonify(message="Logged out.")


@bp.get("/me")
@student_required
def me():
    return jsonify(student=current_student())


@bp.get("/feedback")
@student_required
def my_feedback():
    items = feedback_model.list_for_student_account(current_student()["id"])
    return jsonify(items=items, total=len(items))
