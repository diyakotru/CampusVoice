"""
/api/admin endpoints.

    POST /api/admin/login       – check credentials, start a session
    POST /api/admin/logout      – end the session
    GET  /api/admin/me          – who is logged in? (used by the frontend guard)
    GET  /api/admin/dashboard   – everything the overview page needs, in one call
"""
from flask import Blueprint, jsonify, request, session

from extensions import limiter
from models import feedback as feedback_model
from models import users
from utils.auth import admin_required, json_body_required, login_admin, logout_admin
from utils.validators import validate_login

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.post("/login")
@limiter.limit("5 per minute; 20 per hour")
@json_body_required
def login():
    data, errors = validate_login(request.get_json(silent=True), "username")
    if errors:
        return jsonify(error="Username and password are required.", fields=errors), 400

    admin = users.authenticate_admin(data["username"], data["password"])
    if admin is None:
        # Same message for "no such user" and "wrong password" on purpose.
        return jsonify(error="Invalid username or password."), 401

    login_admin(admin)
    return jsonify(message="Login successful.", admin={"username": admin["username"]})


@bp.post("/logout")
@json_body_required
def logout():
    logout_admin()
    return jsonify(message="Logged out.")


@bp.get("/me")
@admin_required
def me():
    return jsonify(admin={"id": session["admin_id"], "username": session["admin_username"]})


@bp.get("/dashboard")
@admin_required
def dashboard():
    return jsonify(
        admin={"username": session["admin_username"]},
        stats=feedback_model.get_stats(recent_limit=5),
    )
