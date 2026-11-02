"""
/api/feedback endpoints.

    POST /api/feedback              public   – submit feedback
    GET  /api/feedback              admin    – paginated, searchable list
    GET  /api/feedback/<id>         admin    – one feedback record
    GET  /api/feedback/stats        admin    – overview card numbers
    GET  /api/feedback/analytics    admin    – chart data
    GET  /api/feedback/export       admin    – CSV download
"""
import csv
import io
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

from extensions import limiter
from models import feedback as feedback_model
from utils.auth import admin_required, current_student, json_body_required
from utils.validators import validate_feedback

bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")


@bp.post("")
@limiter.limit("5 per minute; 30 per hour")
@json_body_required
def submit_feedback():
    data, errors = validate_feedback(request.get_json(silent=True))
    if errors:
        return jsonify(error="Please correct the highlighted fields.", fields=errors), 400

    # A logged-in student's identity comes from their session, not from the
    # form, so nobody can file feedback into another student's history.
    student = current_student()
    account_id = None
    if student:
        data["student_id"] = student["student_id"]
        data["student_name"] = student["full_name"]
        account_id = student["id"]

    created = feedback_model.create_feedback(data, account_id)
    return jsonify(
        message="Thank you! Your feedback has been submitted successfully.",
        feedback={"id": created["id"], "created_at": created["created_at"]},
        linked_to_account=account_id is not None,
    ), 201


@bp.get("")
@admin_required
def list_feedback():
    filters, errors = feedback_model.parse_filters(request.args)
    paging, paging_errors = feedback_model.parse_paging(request.args)
    errors.update(paging_errors)
    if errors:
        return jsonify(error="Invalid query parameters.", fields=errors), 400
    return jsonify(feedback_model.list_feedback(filters, paging))


@bp.get("/<int:feedback_id>")
@admin_required
def get_feedback(feedback_id):
    row = feedback_model.get_feedback(feedback_id)
    if row is None:
        return jsonify(error="Feedback not found."), 404
    return jsonify(row)


@bp.get("/stats")
@admin_required
def stats():
    return jsonify(feedback_model.get_stats())


@bp.get("/analytics")
@admin_required
def analytics():
    try:
        days = int(request.args.get("days", 30))
        if not 7 <= days <= 365:
            raise ValueError
    except ValueError:
        return jsonify(error="days must be between 7 and 365."), 400
    return jsonify(feedback_model.get_analytics(days))


def _csv_safe(value):
    """
    Stop "CSV injection": spreadsheet apps run cells starting with = + - @
    as formulas. Prefixing them with ' makes Excel show them as plain text.
    """
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


@bp.get("/export")
@admin_required
def export_csv():
    filters, errors = feedback_model.parse_filters(request.args)
    if errors:
        return jsonify(error="Invalid query parameters.", fields=errors), 400
    rows = feedback_model.export_feedback(filters)

    columns = ["id", "created_at", "student_name", "student_id", "department", "semester",
               "category", "rating", "description", "suggestions"]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Submitted At (UTC)", "Student Name", "Student ID", "Department",
                     "Semester", "Category", "Rating", "Description", "Suggestions"])
    for row in rows:
        values = []
        for col in columns:
            value = row[col]
            if col == "created_at":
                value = value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            values.append(_csv_safe(value))
        writer.writerow(values)

    filename = f"feedback_export_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.csv"
    # "﻿" (byte-order mark) makes Excel open the file as UTF-8
    return Response(
        "﻿" + buffer.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"',
                 "Cache-Control": "no-store"},
    )
