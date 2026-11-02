"""Fixed lists shared by validation, analytics and the /api/meta endpoint."""

CATEGORIES = [
    "Faculty and Teaching",
    "Infrastructure",
    "Library",
    "Canteen",
    "Events and Workshops",
    "Overall College Experience",
]

DEPARTMENTS = [
    "Computer Science and Engineering",
    "Information Technology",
    "Electronics and Communication",
    "Electrical and Electronics",
    "Mechanical Engineering",
    "Civil Engineering",
    "Business Administration",
    "Other",
]

SEMESTERS = list(range(1, 9))  # 1..8  → Year = (semester + 1) // 2

# Columns the admin may sort the feedback table by (whitelist — the value is
# put into the SQL text, so it must never come straight from user input).
SORTABLE_COLUMNS = {
    "created_at": "created_at",
    "rating": "rating",
    "category": "category",
    "student_name": "student_name",
    "student_id": "student_id",
}

MAX_PER_PAGE = 100
DEFAULT_PER_PAGE = 10
