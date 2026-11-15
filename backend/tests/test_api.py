"""End-to-end API tests: HTTP request → Flask → PostgreSQL → HTTP response."""
import csv
import io

from conftest import ADMIN_PASS, ADMIN_USER, valid_feedback

ADMIN_ONLY = [
    "/api/feedback", "/api/feedback/1", "/api/feedback/stats", "/api/feedback/analytics",
    "/api/feedback/export", "/api/admin/dashboard", "/api/admin/me",
]


def submit(client, **overrides):
    return client.post("/api/feedback", json=valid_feedback(**overrides))


# ------------------------------------------------------------------ health / meta
def test_health_reports_database_connected(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["database"] == "connected"
    assert body["database_engine"].startswith("PostgreSQL")


def test_meta_lists_categories(client):
    body = client.get("/api/meta").get_json()
    assert len(body["categories"]) == 6
    assert "Canteen" in body["categories"]


# ------------------------------------------------------------------ submission
def test_submit_feedback_is_saved_in_database(client, db):
    r = submit(client)
    assert r.status_code == 201
    new_id = r.get_json()["feedback"]["id"]
    with db.cursor() as cur:
        cur.execute("SELECT student_name, student_id, category, rating, semester FROM feedback WHERE id = %s", (new_id,))
        row = cur.fetchone()
    # student_id is normalised to upper case
    assert row == ("Priya Sharma", "21CS045", "Library", 4, 5)


def test_suggestions_are_optional(client, db):
    assert submit(client, suggestions="").status_code == 201
    with db.cursor() as cur:
        cur.execute("SELECT suggestions FROM feedback")
        assert cur.fetchone()[0] is None


def test_missing_fields_are_rejected(client, db):
    r = client.post("/api/feedback", json={})
    assert r.status_code == 400
    fields = r.get_json()["fields"]
    for f in ("student_name", "student_id", "department", "semester", "category", "rating", "description"):
        assert f in fields
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM feedback")
        assert cur.fetchone()[0] == 0


def test_invalid_values_are_rejected(client):
    cases = [
        {"rating": 6}, {"rating": 0}, {"rating": "five"}, {"rating": 4.5}, {"rating": True},
        {"category": "Hostel"}, {"semester": 9}, {"department": "Astrology"},
        {"description": "too short"}, {"description": "x" * 2001}, {"suggestions": "y" * 1001},
        {"student_name": "<script>alert(1)</script>"}, {"student_id": "a"},
    ]
    for case in cases:
        r = submit(client, **case)
        assert r.status_code == 400, case
        assert next(iter(case)) in r.get_json()["fields"], case


def test_non_json_body_is_rejected(client):
    r = client.post("/api/feedback", data="student_name=x", content_type="application/x-www-form-urlencoded")
    assert r.status_code == 415


def test_sql_injection_is_stored_as_plain_text(client, admin_client, db):
    evil = "Robert'); DROP TABLE feedback;--"
    assert submit(client, description=evil + " long enough").status_code == 201
    with db.cursor() as cur:
        cur.execute("SELECT description FROM feedback")
        assert cur.fetchone()[0].startswith(evil)       # stored literally, table still exists
    r = admin_client.get("/api/feedback", query_string={"search": "' OR '1'='1"})
    assert r.status_code == 200
    assert r.get_json()["pagination"]["total"] == 0    # injection did not match everything


# ------------------------------------------------------------------ authentication
def test_admin_routes_require_login(client):
    for url in ADMIN_ONLY:
        assert client.get(url).status_code == 401, url


def test_admin_login_wrong_password(client):
    r = client.post("/api/admin/login", json={"username": ADMIN_USER, "password": "wrong-pass1"})
    assert r.status_code == 401
    r = client.post("/api/admin/login", json={"username": "nobody", "password": "wrong-pass1"})
    assert r.status_code == 401
    assert client.get("/api/admin/dashboard").status_code == 401


def test_admin_login_sets_secure_session_cookie(client):
    r = client.post("/api/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200
    cookie = r.headers["Set-Cookie"]
    assert "cfs_session=" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert client.get("/api/admin/me").get_json()["admin"]["username"] == ADMIN_USER


def test_password_is_hashed_in_database(db):
    with db.cursor() as cur:
        cur.execute("SELECT password_hash FROM admins WHERE username = %s", (ADMIN_USER,))
        stored = cur.fetchone()[0]
    assert stored != ADMIN_PASS and stored.startswith("scrypt:")


def test_tampered_cookie_is_rejected(app, admin_client):
    other = app.test_client()
    other.set_cookie("cfs_session", "eyJhZG1pbl9pZCI6MX0.forged.signature")
    assert other.get("/api/admin/dashboard").status_code == 401


def test_logout_ends_session(admin_client):
    assert admin_client.get("/api/admin/dashboard").status_code == 200
    assert admin_client.post("/api/admin/logout", json={}).status_code == 200
    assert admin_client.get("/api/admin/dashboard").status_code == 401


# ------------------------------------------------------------------ admin data
def seed(client):
    rows = [
        dict(student_name="Aarav Shah", student_id="A100", category="Library", rating=5),
        dict(student_name="Bhavna Rao", student_id="B200", category="Library", rating=3),
        dict(student_name="Chetan Das", student_id="C300", category="Canteen", rating=1),
        dict(student_name="Divya Menon", student_id="D400", category="Infrastructure", rating=4),
        dict(student_name="Eshan Kapoor", student_id="E500", category="Canteen", rating=2),
    ]
    for row in rows:
        assert submit(client, **row).status_code == 201


def test_list_pagination_search_filter_sort(client, admin_client):
    seed(client)
    body = admin_client.get("/api/feedback?per_page=2&page=2").get_json()
    assert body["pagination"] == {"page": 2, "per_page": 2, "total": 5, "pages": 3, "has_next": True, "has_prev": True}
    assert len(body["items"]) == 2

    assert [i["student_id"] for i in admin_client.get("/api/feedback?search=c300").get_json()["items"]] == ["C300"]
    assert admin_client.get("/api/feedback?search=menon").get_json()["items"][0]["student_name"] == "Divya Menon"
    assert admin_client.get("/api/feedback?category=Canteen").get_json()["pagination"]["total"] == 2
    assert admin_client.get("/api/feedback?rating=5").get_json()["items"][0]["student_id"] == "A100"

    ratings = [i["rating"] for i in admin_client.get("/api/feedback?sort=rating&order=asc").get_json()["items"]]
    assert ratings == sorted(ratings)
    newest_first = admin_client.get("/api/feedback").get_json()["items"]
    assert newest_first[0]["student_id"] == "E500"
    oldest_first = admin_client.get("/api/feedback?sort=created_at&order=asc").get_json()["items"]
    assert oldest_first[0]["student_id"] == "A100"


def test_search_treats_wildcards_literally(client, admin_client):
    seed(client)
    assert admin_client.get("/api/feedback?search=%25").get_json()["pagination"]["total"] == 0
    assert admin_client.get("/api/feedback?search=_").get_json()["pagination"]["total"] == 0


def test_invalid_query_parameters(admin_client):
    for qs in ("page=0", "per_page=1000", "sort=password_hash", "order=sideways",
               "rating=9", "category=Hostel", "date_from=yesterday"):
        assert admin_client.get(f"/api/feedback?{qs}").status_code == 400, qs


def test_get_single_feedback(client, admin_client):
    seed(client)
    r = admin_client.get("/api/feedback/3")
    assert r.status_code == 200 and r.get_json()["student_id"] == "C300"
    assert admin_client.get("/api/feedback/999").status_code == 404


def test_stats_values(client, admin_client):
    seed(client)
    s = admin_client.get("/api/feedback/stats").get_json()
    assert s["total_feedback"] == 5
    assert s["average_rating"] == 3.0            # (5+3+1+4+2)/5
    assert s["total_categories"] == 6
    assert s["categories_with_feedback"] == 3
    assert s["submissions_last_7_days"] == 5
    assert len(s["recent_submissions"]) == 5
    dash = admin_client.get("/api/admin/dashboard").get_json()
    assert dash["stats"]["total_feedback"] == 5 and dash["admin"]["username"] == ADMIN_USER


def test_stats_with_no_data(admin_client):
    s = admin_client.get("/api/feedback/stats").get_json()
    assert s["total_feedback"] == 0 and s["average_rating"] is None


def test_analytics_values(client, admin_client):
    seed(client)
    a = admin_client.get("/api/feedback/analytics?days=7").get_json()
    by_cat = {c["category"]: c["count"] for c in a["category_distribution"]}
    assert by_cat == {"Faculty and Teaching": 0, "Infrastructure": 1, "Library": 2, "Canteen": 2,
                      "Events and Workshops": 0, "Overall College Experience": 0}
    assert [r["count"] for r in a["rating_distribution"]] == [1, 1, 1, 1, 1]
    avg = {c["category"]: c["average_rating"] for c in a["average_rating_by_category"]}
    assert avg["Library"] == 4.0 and avg["Canteen"] == 1.5 and avg["Library"] and avg["Faculty and Teaching"] is None
    assert len(a["submission_trend"]) == 7
    assert sum(d["count"] for d in a["submission_trend"]) == 5
    assert admin_client.get("/api/feedback/analytics?days=2").status_code == 400


def test_csv_export(client, admin_client):
    seed(client)
    submit(client, student_name="Faris Ali", student_id="F600", description="=HYPERLINK(\"http://evil\") is bad")
    r = admin_client.get("/api/feedback/export?category=Canteen")
    assert r.status_code == 200
    assert r.mimetype == "text/csv" and "attachment" in r.headers["Content-Disposition"]
    rows = list(csv.reader(io.StringIO(r.get_data(as_text=True).lstrip("﻿"))))
    assert rows[0][0] == "ID" and len(rows) == 3          # header + 2 canteen rows
    full = list(csv.reader(io.StringIO(admin_client.get("/api/feedback/export").get_data(as_text=True).lstrip("﻿"))))
    formula_row = next(r for r in full if r[3] == "F600")
    assert formula_row[8].startswith("'=")                # CSV-injection neutralised


# ------------------------------------------------------------------ students
def register(client, sid="21IT007", name="Neha Joshi"):
    return client.post("/api/student/register", json={
        "full_name": name, "student_id": sid, "department": "Information Technology", "password": "Student123"})


def test_student_history_shows_only_own_feedback(app, client):
    assert register(client).status_code == 201
    # identity comes from the session, even if the form says otherwise
    assert submit(client, student_name="Someone Else", student_id="X999").get_json()["linked_to_account"] is True
    other = app.test_client()
    assert register(other, sid="21IT008", name="Om Prakash").status_code == 201
    submit(other)
    submit(app.test_client())  # anonymous submission

    mine = client.get("/api/student/feedback").get_json()
    assert mine["total"] == 1
    assert mine["items"][0]["student_id"] == "21IT007"
    assert mine["items"][0]["student_name"] == "Neha Joshi"


def test_student_duplicate_registration_and_login(app, client):
    assert register(client).status_code == 201
    assert register(app.test_client()).status_code == 409
    c = app.test_client()
    assert c.post("/api/student/login", json={"student_id": "21it007", "password": "wrong1234"}).status_code == 401
    assert c.post("/api/student/login", json={"student_id": "21it007", "password": "Student123"}).status_code == 200
    assert c.get("/api/student/me").get_json()["student"]["student_id"] == "21IT007"
    assert c.post("/api/student/logout", json={}).status_code == 200
    assert c.get("/api/student/feedback").status_code == 401


def test_student_cannot_access_admin_routes(client):
    register(client)
    for url in ADMIN_ONLY:
        assert client.get(url).status_code == 401, url


def test_weak_student_password_rejected(client):
    r = client.post("/api/student/register", json={
        "full_name": "Neha Joshi", "student_id": "21IT007", "department": "Information Technology", "password": "short"})
    assert r.status_code == 400 and "password" in r.get_json()["fields"]


# ------------------------------------------------------------------ rate limiting & misc
def test_feedback_submission_rate_limited(client, rate_limited):
    codes = [submit(client).status_code for _ in range(6)]
    assert codes[:5] == [201] * 5 and codes[5] == 429
    assert "Too many requests" in submit(client).get_json()["error"]


def test_admin_login_rate_limited(client, rate_limited):
    codes = [client.post("/api/admin/login", json={"username": "x", "password": "y"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_unknown_api_route_returns_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.is_json


def test_frontend_is_served_with_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200 and b"CampusVoice" in r.data
    assert "Content-Security-Policy" in r.headers and r.headers["X-Frame-Options"] == "DENY"
    assert client.get("/dashboard.html").status_code == 200
    assert client.get("/../backend/.env").status_code == 404
    assert client.get("/nope.html").status_code == 404


def test_session_endpoint_reports_only_own_login_state(app, client, admin_client):
    assert client.get("/api/session").get_json() == {"admin": None, "student": None}
    assert admin_client.get("/api/session").get_json()["admin"] == {"username": ADMIN_USER}
    register(client)
    body = client.get("/api/session").get_json()
    assert body["admin"] is None and body["student"]["student_id"] == "21IT007"


# ------------------------------------------------------------------ Sign in with Google
import pytest  # noqa: E402

from utils import google_auth  # noqa: E402

FAKE_TOKENS = {
    "token-neha": {"sub": "google-111", "email": "neha@gmail.com", "name": "Neha Joshi"},
    "token-om": {"sub": "google-222", "email": "om@gmail.com", "name": "Om Prakash"},
}


@pytest.fixture
def google_enabled(app, monkeypatch):
    """Turn Google sign-in on and replace Google's signature check with a fake
    (real ID tokens can only be minted by Google). Everything else is real."""
    def fake_verify(token, client_id):
        assert client_id == "test-client-id.apps.googleusercontent.com"
        if token not in FAKE_TOKENS:
            raise google_auth.InvalidGoogleToken("bad token")
        return dict(FAKE_TOKENS[token])
    monkeypatch.setitem(app.config, "GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(google_auth, "verify_google_token", fake_verify)


def google_profile(client, sid="21IT050", name="Neha Joshi"):
    return client.post("/api/student/google/complete", json={
        "full_name": name, "student_id": sid, "department": "Information Technology"})


def test_google_disabled_by_default(client):
    assert client.get("/api/meta").get_json()["google_client_id"] is None
    assert client.post("/api/student/google", json={"credential": "token-neha"}).status_code == 404


def test_google_first_login_then_returning_login(app, client, google_enabled, db):
    assert client.get("/api/meta").get_json()["google_client_id"].startswith("test-client-id")

    r = client.post("/api/student/google", json={"credential": "token-neha"})
    body = r.get_json()
    assert r.status_code == 200 and body["needs_profile"] is True and body["email"] == "neha@gmail.com"
    assert client.get("/api/student/me").status_code == 401        # not logged in yet

    assert google_profile(client, sid="21it050").status_code == 201
    assert client.get("/api/student/me").get_json()["student"]["student_id"] == "21IT050"
    with db.cursor() as cur:
        cur.execute("SELECT google_sub, email, password_hash FROM students WHERE student_id = '21IT050'")
        assert cur.fetchone() == ("google-111", "neha@gmail.com", None)

    # a fresh browser: same Google account logs straight in
    c = app.test_client()
    r = c.post("/api/student/google", json={"credential": "token-neha"})
    assert r.status_code == 200 and r.get_json()["needs_profile"] is False
    assert c.get("/api/student/me").get_json()["student"]["student_id"] == "21IT050"
    submit(c)
    assert c.get("/api/student/feedback").get_json()["total"] == 1


def test_google_invalid_token_rejected(client, google_enabled):
    assert client.post("/api/student/google", json={"credential": "forged"}).status_code == 401
    assert client.post("/api/student/google", json={}).status_code == 401
    assert client.post("/api/student/google", data="x", content_type="text/plain").status_code == 415


def test_google_complete_requires_verified_google_identity(client, google_enabled):
    r = google_profile(client)
    assert r.status_code == 401
    assert client.get("/api/student/me").status_code == 401


def test_google_cannot_take_over_existing_student_id(app, client, google_enabled):
    assert register(app.test_client(), sid="21IT007").status_code == 201   # password account
    client.post("/api/student/google", json={"credential": "token-om"})
    r = google_profile(client, sid="21IT007", name="Om Prakash")
    assert r.status_code == 409
    assert client.get("/api/student/me").status_code == 401


def test_google_profile_validated(client, google_enabled):
    client.post("/api/student/google", json={"credential": "token-neha"})
    r = client.post("/api/student/google/complete", json={"full_name": "x", "student_id": "!", "department": "Nope"})
    assert r.status_code == 400
    assert set(r.get_json()["fields"]) == {"full_name", "student_id", "department"}


def test_google_only_account_cannot_password_login(app, client, google_enabled):
    client.post("/api/student/google", json={"credential": "token-neha"})
    google_profile(client, sid="21IT050")
    c = app.test_client()
    assert c.post("/api/student/login", json={"student_id": "21IT050", "password": "anything1"}).status_code == 401


def test_google_pending_identity_expires(client, google_enabled, monkeypatch):
    import routes.student as student_routes
    client.post("/api/student/google", json={"credential": "token-neha"})
    real_time = student_routes.time.time
    monkeypatch.setattr(student_routes.time, "time", lambda: real_time() + 16 * 60)
    assert google_profile(client).status_code == 401


def test_csp_allows_google_sign_in(client):
    csp = client.get("/student-login.html").headers["Content-Security-Policy"]
    assert "https://accounts.google.com/gsi/client" in csp
    assert "frame-src https://accounts.google.com/gsi/" in csp
