"""
/api/student endpoints — optional student accounts for the history page.

    POST /api/student/register
    POST /api/student/login
    POST /api/student/logout
    GET  /api/student/me
    GET  /api/student/feedback   – the logged-in student's own submissions only
"""
from flask import Blueprint, jsonify, request

from extensions import limiter
from models import feedback as feedback_model
from models import users
from utils.auth import (current_student, json_body_required, login_student,
                        logout_student, student_required)
from utils.validators import validate_login, validate_student_registration

bp = Blueprint("student", __name__, url_prefix="/api/student")


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
