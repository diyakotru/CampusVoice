"""
Server-side input validation.

The browser also validates the form, but anyone can bypass a browser
(e.g. with curl or Postman), so the server must check everything again.
Each validator returns (clean_data, errors) where errors maps a field name
to a human-readable message.
"""
import re

from .constants import CATEGORIES, DEPARTMENTS, SEMESTERS

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,99}$")
STUDENT_ID_RE = re.compile(r"^[A-Z0-9/_-]{3,20}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _text(data, field):
    """Fetch a field as a stripped string with control characters removed."""
    value = data.get(field)
    if value is None:
        return ""
    if not isinstance(value, (str, int)):
        return None  # wrong type, e.g. a list or object
    return CONTROL_CHARS_RE.sub("", str(value)).strip()


def _collapse_spaces(value):
    return re.sub(r"\s+", " ", value)


def validate_name(value, errors, field="student_name"):
    if value is None:
        errors[field] = "Name must be text."
    elif not value:
        errors[field] = "Name is required."
    elif not NAME_RE.match(value):
        errors[field] = "Name must be 2–100 letters (spaces, . ' - allowed)."
    return value


def validate_student_id(value, errors, field="student_id"):
    if value is None:
        errors[field] = "Student ID must be text."
        return value
    value = value.upper()
    if not value:
        errors[field] = "Student ID is required."
    elif not STUDENT_ID_RE.match(value):
        errors[field] = "Student ID must be 3–20 characters: letters, digits, / _ -"
    return value


def validate_department(value, errors, field="department"):
    if not value:
        errors[field] = "Department is required."
    elif value not in DEPARTMENTS:
        errors[field] = "Please choose a department from the list."
    return value


def validate_feedback(data):
    """Validate the body of POST /api/feedback."""
    errors = {}
    if not isinstance(data, dict):
        return None, {"_": "Request body must be a JSON object."}

    name = _text(data, "student_name")
    clean = {
        "student_name": validate_name(_collapse_spaces(name) if name else name, errors),
        "student_id": validate_student_id(_text(data, "student_id"), errors),
        "department": validate_department(_text(data, "department"), errors),
    }

    # semester: integer 1..8
    try:
        semester = int(data.get("semester"))
        if semester not in SEMESTERS:
            raise ValueError
    except (TypeError, ValueError):
        errors["semester"] = "Please choose a semester between 1 and 8."
        semester = None
    clean["semester"] = semester

    category = _text(data, "category")
    if not category:
        errors["category"] = "Feedback category is required."
    elif category not in CATEGORIES:
        errors["category"] = "Please choose a valid feedback category."
    clean["category"] = category

    # rating: integer 1..5 (reject booleans, floats like 4.5, strings like "five")
    rating = data.get("rating")
    if isinstance(rating, bool) or not isinstance(rating, (int, str)):
        rating = None
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except (TypeError, ValueError):
        errors["rating"] = "Please select a rating from 1 to 5 stars."
        rating = None
    clean["rating"] = rating

    description = _text(data, "description")
    if description is None or not description:
        errors["description"] = "Feedback description is required."
    elif len(description) < 10:
        errors["description"] = "Please write at least 10 characters."
    elif len(description) > 2000:
        errors["description"] = "Description must be at most 2000 characters."
    clean["description"] = description

    suggestions = _text(data, "suggestions")
    if suggestions is None:
        errors["suggestions"] = "Suggestions must be text."
    elif len(suggestions) > 1000:
        errors["suggestions"] = "Suggestions must be at most 1000 characters."
    clean["suggestions"] = suggestions or None

    return clean, errors


def validate_password(password, errors, field="password"):
    if not isinstance(password, str) or not password:
        errors[field] = "Password is required."
    elif len(password) < 8:
        errors[field] = "Password must be at least 8 characters."
    elif len(password) > 128:
        errors[field] = "Password must be at most 128 characters."
    elif not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        errors[field] = "Password must contain at least one letter and one number."
    return password


def validate_student_registration(data):
    errors = {}
    if not isinstance(data, dict):
        return None, {"_": "Request body must be a JSON object."}
    name = _text(data, "full_name")
    clean = {
        "full_name": validate_name(_collapse_spaces(name) if name else name, errors, "full_name"),
        "student_id": validate_student_id(_text(data, "student_id"), errors),
        "department": validate_department(_text(data, "department"), errors),
        "password": validate_password(data.get("password"), errors),
    }
    return clean, errors


def validate_login(data, id_field):
    """Basic shape check for login bodies. Wrong credentials are handled separately."""
    if not isinstance(data, dict):
        return None, {"_": "Request body must be a JSON object."}
    identifier = _text(data, id_field)
    password = data.get("password")
    errors = {}
    if not identifier:
        errors[id_field] = "This field is required."
    if not isinstance(password, str) or not password:
        errors["password"] = "Password is required."
    elif len(password) > 128:
        errors["password"] = "Password is too long."
    return {id_field: identifier, "password": password}, errors
