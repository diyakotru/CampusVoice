"""
Public helper endpoints.

    GET /api/health  – is the server up AND can it reach the cloud database?
    GET /api/meta    – lists for the form drop-downs (categories, departments)
    GET /api/session – is this browser logged in as an admin and/or student?
"""
from flask import Blueprint, current_app, jsonify, session

from database import DatabaseUnavailable, check_connection
from utils.auth import current_student
from utils.constants import CATEGORIES, DEPARTMENTS, SEMESTERS

bp = Blueprint("meta", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    try:
        info = check_connection()
    except DatabaseUnavailable:
        return jsonify(status="degraded", api="ok", database="unreachable"), 503
    return jsonify(
        status="ok",
        api="ok",
        database="connected",
        database_server_time=info["server_time"].isoformat(),
        database_engine=info["version"].split(" on ")[0],
    )


@bp.get("/meta")
def meta():
    # google_client_id is public (Google puts it in every sign-in page); null = button hidden
    return jsonify(categories=CATEGORIES, departments=DEPARTMENTS, semesters=SEMESTERS,
                   google_client_id=current_app.config["GOOGLE_CLIENT_ID"] or None)


@bp.get("/session")
def session_info():
    """
    Who is logged in *in this browser*? Pages call this on load to decide
    what to show. It only ever describes the caller's own session.
    """
    admin = {"username": session["admin_username"]} if "admin_id" in session else None
    return jsonify(admin=admin, student=current_student())
