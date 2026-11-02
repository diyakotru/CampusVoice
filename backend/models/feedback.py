"""
All SQL for the `feedback` table.

Rule followed everywhere: user-supplied VALUES go in the params tuple
(%s placeholders), never into the SQL string. The only things inserted
into SQL text are column names picked from a fixed whitelist.
"""
from datetime import date, datetime, timedelta

from psycopg2 import sql

from database import get_cursor
from utils.constants import CATEGORIES, DEFAULT_PER_PAGE, MAX_PER_PAGE, SORTABLE_COLUMNS

PUBLIC_COLUMNS = """id, student_name, student_id, department, semester, category,
                    rating, description, suggestions, created_at"""


def serialize(row):
    """Convert DB values to JSON-friendly ones (datetimes → ISO 8601 strings)."""
    if row is None:
        return None
    out = dict(row)
    for key, value in out.items():
        if isinstance(value, (datetime, date)):
            out[key] = value.isoformat()
    return out


# ------------------------------------------------------------------ writes
def create_feedback(data, student_account_id=None):
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO feedback (student_name, student_id, department, semester, category,
                                  rating, description, suggestions, student_account_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (data["student_name"], data["student_id"], data["department"], data["semester"],
             data["category"], data["rating"], data["description"], data["suggestions"],
             student_account_id),
        )
        return serialize(cur.fetchone())


# ------------------------------------------------------------------ filters
def parse_filters(args):
    """
    Turn query-string arguments into a validated filter dict.
    Returns (filters, errors).
    """
    errors = {}
    filters = {}

    search = (args.get("search") or "").strip()
    if len(search) > 100:
        errors["search"] = "Search text is too long."
    elif search:
        filters["search"] = search

    category = (args.get("category") or "").strip()
    if category:
        if category not in CATEGORIES:
            errors["category"] = "Unknown category."
        else:
            filters["category"] = category

    rating = (args.get("rating") or "").strip()
    if rating:
        if rating not in {"1", "2", "3", "4", "5"}:
            errors["rating"] = "Rating filter must be 1–5."
        else:
            filters["rating"] = int(rating)

    for key in ("date_from", "date_to"):
        value = (args.get(key) or "").strip()
        if value:
            try:
                filters[key] = date.fromisoformat(value)
            except ValueError:
                errors[key] = "Dates must look like YYYY-MM-DD."

    return filters, errors


def _where(filters):
    clauses, params = [], []
    if "search" in filters:
        # Escape LIKE wildcards so a search for "50%" means the text "50%"
        term = (filters["search"].replace("\\", "\\\\")
                .replace("%", "\\%").replace("_", "\\_"))
        clauses.append("(student_id ILIKE %s OR student_name ILIKE %s)")
        params += [f"%{term}%", f"%{term}%"]
    if "category" in filters:
        clauses.append("category = %s")
        params.append(filters["category"])
    if "rating" in filters:
        clauses.append("rating = %s")
        params.append(filters["rating"])
    if "date_from" in filters:
        clauses.append("created_at >= %s")
        params.append(filters["date_from"])
    if "date_to" in filters:
        clauses.append("created_at < %s")  # include the whole "to" day
        params.append(filters["date_to"] + timedelta(days=1))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def parse_paging(args):
    errors = {}
    try:
        page = int(args.get("page", 1))
        if page < 1:
            raise ValueError
    except (TypeError, ValueError):
        errors["page"] = "page must be a positive integer."
        page = 1
    try:
        per_page = int(args.get("per_page", DEFAULT_PER_PAGE))
        if not 1 <= per_page <= MAX_PER_PAGE:
            raise ValueError
    except (TypeError, ValueError):
        errors["per_page"] = f"per_page must be between 1 and {MAX_PER_PAGE}."
        per_page = DEFAULT_PER_PAGE

    sort = args.get("sort", "created_at")
    if sort not in SORTABLE_COLUMNS:
        errors["sort"] = "Unsupported sort column."
        sort = "created_at"
    order = (args.get("order") or "desc").lower()
    if order not in ("asc", "desc"):
        errors["order"] = "order must be asc or desc."
        order = "desc"
    return {"page": page, "per_page": per_page, "sort": sort, "order": order}, errors


# ------------------------------------------------------------------ reads
def list_feedback(filters, paging):
    where, params = _where(filters)
    order_by = sql.SQL("ORDER BY {col} {direction}, id {direction}").format(
        col=sql.Identifier(SORTABLE_COLUMNS[paging["sort"]]),
        direction=sql.SQL("ASC" if paging["order"] == "asc" else "DESC"),
    )
    offset = (paging["page"] - 1) * paging["per_page"]

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM feedback {where}", params)
        total = cur.fetchone()["total"]

        query = sql.SQL(f"SELECT {PUBLIC_COLUMNS} FROM feedback {where} ") + order_by + sql.SQL(" LIMIT %s OFFSET %s")
        cur.execute(query, params + [paging["per_page"], offset])
        rows = [serialize(r) for r in cur.fetchall()]

    pages = max(1, -(-total // paging["per_page"]))  # ceiling division
    return {
        "items": rows,
        "pagination": {
            "page": paging["page"],
            "per_page": paging["per_page"],
            "total": total,
            "pages": pages,
            "has_next": paging["page"] < pages,
            "has_prev": paging["page"] > 1,
        },
    }


def export_feedback(filters, limit=10000):
    where, params = _where(filters)
    with get_cursor() as cur:
        cur.execute(
            f"SELECT {PUBLIC_COLUMNS} FROM feedback {where} ORDER BY created_at DESC, id DESC LIMIT %s",
            params + [limit],
        )
        return cur.fetchall()


def get_feedback(feedback_id):
    with get_cursor() as cur:
        cur.execute(f"SELECT {PUBLIC_COLUMNS} FROM feedback WHERE id = %s", (feedback_id,))
        return serialize(cur.fetchone())


def list_for_student_account(account_id):
    with get_cursor() as cur:
        cur.execute(
            f"SELECT {PUBLIC_COLUMNS} FROM feedback WHERE student_account_id = %s "
            "ORDER BY created_at DESC, id DESC",
            (account_id,),
        )
        return [serialize(r) for r in cur.fetchall()]


# ------------------------------------------------------------------ aggregates
def get_stats(recent_limit=5):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)                                               AS total,
                   ROUND(AVG(rating)::numeric, 2)                         AS average_rating,
                   COUNT(DISTINCT category)                               AS categories_used,
                   COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days')  AS last_7_days,
                   COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 day')   AS last_24_hours
            FROM feedback
            """
        )
        totals = cur.fetchone()
        cur.execute(
            f"SELECT {PUBLIC_COLUMNS} FROM feedback ORDER BY created_at DESC, id DESC LIMIT %s",
            (recent_limit,),
        )
        recent = [serialize(r) for r in cur.fetchall()]

    avg = totals["average_rating"]
    return {
        "total_feedback": totals["total"],
        "average_rating": float(avg) if avg is not None else None,
        "total_categories": len(CATEGORIES),
        "categories_with_feedback": totals["categories_used"],
        "submissions_last_7_days": totals["last_7_days"],
        "submissions_last_24_hours": totals["last_24_hours"],
        "recent_submissions": recent,
    }


def get_analytics(days=30):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT category, COUNT(*) AS count, ROUND(AVG(rating)::numeric, 2) AS average_rating
            FROM feedback GROUP BY category
            """
        )
        by_category = {r["category"]: r for r in cur.fetchall()}

        cur.execute("SELECT rating, COUNT(*) AS count FROM feedback GROUP BY rating")
        by_rating = {r["rating"]: r["count"] for r in cur.fetchall()}

        # One row per day for the last `days` days, including days with zero
        # submissions (generate_series builds the calendar, LEFT JOIN fills it).
        cur.execute(
            """
            WITH days AS (
                SELECT generate_series(
                    (NOW() AT TIME ZONE 'UTC')::date - (%s - 1),
                    (NOW() AT TIME ZONE 'UTC')::date,
                    INTERVAL '1 day')::date AS day
            )
            SELECT d.day, COUNT(f.id) AS count, ROUND(AVG(f.rating)::numeric, 2) AS average_rating
            FROM days d
            LEFT JOIN feedback f ON (f.created_at AT TIME ZONE 'UTC')::date = d.day
            GROUP BY d.day ORDER BY d.day
            """,
            (days,),
        )
        trend = cur.fetchall()

    def num(value):
        return float(value) if value is not None else None

    return {
        "category_distribution": [
            {"category": c, "count": by_category[c]["count"] if c in by_category else 0}
            for c in CATEGORIES
        ],
        "rating_distribution": [{"rating": r, "count": by_rating.get(r, 0)} for r in range(1, 6)],
        "average_rating_by_category": [
            {"category": c, "average_rating": num(by_category[c]["average_rating"]) if c in by_category else None}
            for c in CATEGORIES
        ],
        "submission_trend": [
            {"date": r["day"].isoformat(), "count": r["count"], "average_rating": num(r["average_rating"])}
            for r in trend
        ],
        "trend_days": days,
    }
