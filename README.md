# CampusVoice — Cloud-Based Feedback Collection System

A web platform where students submit feedback about their college (faculty, infrastructure, library, canteen, events, overall experience) from any device. Administrators review it in a secure dashboard with search, analytics and reports. All data is stored in a **cloud PostgreSQL database (Supabase)**, and the application is built to be **hosted on Render**.

![Admin dashboard](docs/screenshots/06-dashboard-overview.png)

---

## Contents
1. [Problem statement](#1-problem-statement) · 2. [Objectives](#2-objectives) · 3. [Features](#3-features) · 4. [Technologies](#4-technologies) · 5. [Architecture](#5-system-architecture) · 6. [Database schema](#6-database-schema) · 7. [Project structure](#7-project-structure) · 8. [Local setup](#8-installation--local-setup) · 9. [Environment variables](#9-environment-variables) · 10. [API documentation](#10-api-documentation) · 11. [Cloud deployment](#11-cloud-deployment) · 12. [Testing](#12-testing) · 13. [Screenshots](#13-screenshots) · 14. [Future enhancements](#14-future-enhancements) · 15. [Status checklist](#15-implementation-status)

More documents: [Architecture & cloud concepts](docs/architecture.md) · [Deployment guide](docs/deployment.md) · [Viva questions](docs/viva-questions.md)

---

## 1. Problem statement
Colleges usually collect feedback on paper or through scattered forms. Responses get lost, cannot be searched, and are summarised by hand, so problems with teaching or facilities are noticed late. Students also have no easy way to give feedback from their phones, and rarely see that their feedback was recorded.

## 2. Objectives
* Provide a simple, mobile-friendly form for structured feedback (category, 1–5 stars, description, suggestions).
* Store every response durably in a **managed cloud database** reachable from anywhere.
* Give administrators a **secure** dashboard to search, filter, analyse and export feedback.
* Apply cloud practices: PaaS hosting, DBaaS, environment-based configuration, health checks, continuous deployment.
* Protect student data with authentication, password hashing, input validation and rate limiting.

## 3. Features

**Student portal**
* Home page with introduction, how-it-works and call to action
* Feedback form with interactive star rating, category tiles, character counters
* Browser and server validation with per-field error messages. Invalid submissions are blocked
* Success panel with reference number, toast notification, automatic form reset
* Optional student account (register/login) → **My Submissions** history with the student's own feedback only
* Fully responsive (tested at 390 px phone width)

**Admin dashboard**
* Secure login (scrypt password hashes, signed HttpOnly session cookie, 120-minute expiry, logout)
* Overview cards: total feedback, average rating, categories, recent (7-day) submissions, plus a 30-day trend and the latest submissions
* Feedback table: search by name or student ID, filter by category and rating, sort by date, rating or name, pagination, detail modal
* Analytics (Chart.js): category distribution, rating distribution, average rating per category, submission trend (7/30/90/365 days), each with a data-table view
* Reports: CSV export (Excel-ready, filterable, formula-injection safe) and a printable A4 report (save as PDF)
* Live "Cloud DB connected" indicator

**Security**: parameterised SQL, server-side validation, rate limiting on login and submit, CSRF and XSS mitigations, security headers and CSP, Supabase Row Level Security, secrets only in environment variables. Details: [docs/architecture.md §7](docs/architecture.md#7-security-model).

## 4. Technologies

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | HTML5, CSS3, **Bootstrap 5.3**, Bootstrap Icons, vanilla **JavaScript** | UI, validation, API calls |
| Charts | **Chart.js 4** | Analytics |
| Backend | **Python 3.10+**, **Flask 3**, Flask-CORS, Flask-Limiter | REST API, auth, rate limiting |
| DB driver | psycopg2 (connection pool) | Talks to PostgreSQL over TLS |
| Database | **Supabase PostgreSQL** | Cloud database (DBaaS) |
| Hosting | **Render** web service + Gunicorn | Cloud hosting (PaaS) |
| Tooling | VS Code, Git, GitHub, pytest, Playwright | Development & testing |

No React, TypeScript, Docker or Kubernetes.

## 5. System architecture

```
┌──────────────────┐  HTTPS / JSON  ┌─────────────────────────────┐  SQL over TLS  ┌─────────────────────┐
│ Browser (any     │ ─────────────▶ │ Render web service          │ ─────────────▶ │ Supabase            │
│ device, anywhere)│ ◀───────────── │ Gunicorn → Flask            │ ◀───────────── │ PostgreSQL          │
│ HTML·CSS·JS      │                │ /api/* REST + static pages  │                │ feedback, admins,   │
└──────────────────┘                └─────────────────────────────┘                │ students            │
                                     secrets from env variables                    └─────────────────────┘
```

* The **browser** loads the pages from Flask and calls the JSON API with `fetch()`.
* **Flask** validates input, checks the session, and runs parameterised SQL through a connection pool.
* **Supabase** stores the data. It is reachable only with the private `DATABASE_URL`, which exists only on the server.

The full request–response cycle, data-flow diagrams and cloud concepts are in **[docs/architecture.md](docs/architecture.md)**.

## 6. Database schema
Defined in [`database/schema.sql`](database/schema.sql) (idempotent: safe to run twice).

| Table | Key columns | Constraints / indexes |
|---|---|---|
| `feedback` | id, student_name, student_id, department, semester, category, rating, description, suggestions, student_account_id, created_at | rating 1–5, semester 1–8, category in 6 values, length checks; indexes on created_at, category, rating, student_id, student_account_id |
| `admins` | id, username, password_hash, created_at | unique username, username format check |
| `students` | id, student_id, full_name, department, password_hash, created_at | unique student_id, format checks |

Row Level Security is enabled on all tables so Supabase's public REST API cannot read them.

## 7. Project structure
```
Cloud_Feedback_System/
├── frontend/                  # static site, served by Flask
│   ├── index.html             # home
│   ├── feedback.html          # feedback form
│   ├── student-login.html     # student login / register
│   ├── history.html           # student's own submissions
│   ├── login.html             # admin login
│   ├── dashboard.html         # admin dashboard (overview, feedback, analytics, reports)
│   ├── report.html            # printable report
│   ├── 404.html
│   ├── css/  style.css · dashboard.css · report.css
│   ├── js/   config.js · api.js · common.js · charts.js · feedback.js · dashboard.js · …
│   └── assets/logo.svg
├── backend/
│   ├── app.py                 # app factory, security headers, error handlers, static serving
│   ├── config.py              # all settings from environment variables
│   ├── database.py            # connection pool + get_cursor()
│   ├── extensions.py          # rate limiter
│   ├── routes/                # feedback.py · admin.py · student.py · meta.py (REST endpoints)
│   ├── models/                # feedback.py · users.py (all SQL)
│   ├── utils/                 # validators.py · auth.py · constants.py
│   ├── manage.py              # init-db · create-admin · check-db · seed-demo · clear-demo
│   ├── verify_deployment.py   # checks a live deployment end to end
│   ├── tests/                 # pytest suite (real PostgreSQL)
│   ├── requirements.txt · requirements-dev.txt · .env.example · pytest.ini
├── database/schema.sql
├── docs/  architecture.md · deployment.md · viva-questions.md · screenshots/
├── render.yaml                # Render Blueprint (infrastructure as code)
├── README.md
└── .gitignore
```

## 8. Installation & local setup

**Prerequisites:** Python 3.10+, Git, a free Supabase project ([deployment guide §1](docs/deployment.md#1-create-the-cloud-database-supabase)).

```bash
# 1. Get the code and create a virtual environment
cd Cloud_Feedback_System
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements-dev.txt

# 2. Configure secrets
cd backend
copy .env.example .env            # macOS/Linux: cp .env.example .env
#    edit .env → DATABASE_URL (Supabase Session pooler URI) and SECRET_KEY

# 3. Create tables and the first admin in Supabase
python manage.py init-db
python manage.py create-admin
python manage.py check-db         # confirms connection + lists tables

# 4. Run
python app.py
```
Open **http://localhost:5000** (student portal) and **http://localhost:5000/login.html** (admin).

Optional, for a demo with charts full of data: `python manage.py seed-demo --count 40` inserts sample rows with student IDs `DEMO-…` into your database. `python manage.py clear-demo` removes them again.

## 9. Environment variables

| Variable | Required | Example / default | Meaning |
|---|---|---|---|
| `DATABASE_URL` | **yes** | `postgresql://postgres.xxxx:PASS@aws-0-ap-south-1.pooler.supabase.com:5432/postgres` | Supabase connection string (Session pooler) |
| `SECRET_KEY` | yes in production | 64 random hex chars | Signs session cookies. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FLASK_ENV` | no | `production` | `development` allows HTTP cookies and a temporary secret |
| `DB_POOL_MIN` / `DB_POOL_MAX` | no | `1` / `5` | Connection pool size |
| `SESSION_LIFETIME_MINUTES` | no | `120` | Login session lifetime |
| `CORS_ORIGINS` | no | *(empty)* | Only for a separately hosted frontend |
| `SESSION_COOKIE_SAMESITE` | no | `Lax` | `None` only for a separate frontend domain |
| `SESSION_COOKIE_SECURE` | no | `true` in production | HTTPS-only cookie |
| `RATELIMIT_STORAGE_URI` | no | `memory://` | e.g. Redis URL when running several instances |
| `SERVE_FRONTEND` | no | `true` | Flask serves `frontend/` |

## 10. API documentation
Base URL: same origin (e.g. `https://campusvoice.onrender.com`). All bodies are JSON. Errors look like `{"error": "message", "fields": {"field": "message"}}`.

### Public
| Method & path | Description | Success | Errors |
|---|---|---|---|
| `GET /api/health` | API + database status | 200 `{status, database:"connected", database_engine}` | 503 DB unreachable |
| `GET /api/meta` | Categories, departments, semesters | 200 | — |
| `GET /api/session` | Current browser's login state | 200 `{admin: {username}\|null, student: {…}\|null}` | — |
| `POST /api/feedback` | Submit feedback (rate limit 5/min, 30/h) | 201 `{message, feedback:{id, created_at}, linked_to_account}` | 400, 415, 429 |

`POST /api/feedback` body:
```json
{
  "student_name": "Priya Sharma", "student_id": "21CS045",
  "department": "Computer Science and Engineering", "semester": 5,
  "category": "Library", "rating": 4,
  "description": "Good collection of books, but too few copies.",
  "suggestions": "Extend timings during exams."
}
```
Rules: name 2–100 letters; student ID 3–20 of `A-Z 0-9 / _ -`; department from the list; semester 1–8; category one of the 6; rating integer 1–5; description 10–2000 chars; suggestions optional ≤1000.

### Admin (session cookie required, otherwise `401`)
| Method & path | Description |
|---|---|
| `POST /api/admin/login` | Body `{username, password}` → 200 + session cookie. 401 invalid. Rate limit 5/min, 20/h |
| `POST /api/admin/logout` | Body `{}` → ends the admin session |
| `GET /api/admin/me` | Logged-in admin |
| `GET /api/admin/dashboard` | `{admin, stats}` (same stats as below) |
| `GET /api/feedback` | Paginated list. Query: `page` (≥1), `per_page` (1–100, default 10), `search` (name or ID, partial), `category`, `rating` (1–5), `date_from`, `date_to` (YYYY-MM-DD), `sort` (`created_at`\|`rating`\|`category`\|`student_name`\|`student_id`), `order` (`asc`\|`desc`). Returns `{items:[…], pagination:{page, per_page, total, pages, has_next, has_prev}}` |
| `GET /api/feedback/<id>` | One record. 404 if missing |
| `GET /api/feedback/stats` | `{total_feedback, average_rating, total_categories, categories_with_feedback, submissions_last_7_days, submissions_last_24_hours, recent_submissions:[…5]}` |
| `GET /api/feedback/analytics?days=30` | `{category_distribution, rating_distribution, average_rating_by_category, submission_trend:[{date, count, average_rating}], trend_days}`. `days` 7–365 |
| `GET /api/feedback/export` | CSV download. Same filters as the list (up to 10,000 rows) |

### Student accounts
| Method & path | Description |
|---|---|
| `POST /api/student/register` | `{full_name, student_id, department, password}` → 201 and logged in. 409 if the ID exists |
| `POST /api/student/login` | `{student_id, password}` (rate limit 10/min) |
| `POST /api/student/logout` | `{}` |
| `GET /api/student/me` | Logged-in student (401 if not) |
| `GET /api/student/feedback` | The student's own submissions `{items, total}` |

Try it with curl:
```bash
curl -X POST http://localhost:5000/api/feedback -H "Content-Type: application/json" \
     -d "{\"student_name\":\"Test User\",\"student_id\":\"T001\",\"department\":\"Other\",\"semester\":1,\"category\":\"Canteen\",\"rating\":4,\"description\":\"Testing the API from curl.\"}"
curl -c cookies.txt -X POST http://localhost:5000/api/admin/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"YourPassword1\"}"
curl -b cookies.txt "http://localhost:5000/api/feedback?category=Canteen"
```

## 11. Cloud deployment
Step-by-step instructions, free-tier limits and troubleshooting: **[docs/deployment.md](docs/deployment.md)**. In short:

1. **Supabase**: create a project, run `database/schema.sql` in the SQL Editor, copy the *Session pooler* connection string.
2. `python manage.py create-admin` with that `DATABASE_URL`.
3. Push to **GitHub**.
4. **Render**: New → Blueprint → select the repo → paste `DATABASE_URL` → Apply.
5. Verify: `python backend/verify_deployment.py https://<your-app>.onrender.com`, then open the URL on a phone using mobile data.

**Free-tier notes:** the Render free instance sleeps after 15 minutes idle (the first request then takes ~30–60 s). Supabase free projects pause after 7 days without activity (restore from the dashboard). Neither charges anything unless you upgrade.

## 12. Testing

### Automated API tests (31 tests)
They run against a **real PostgreSQL 16** server that `pgserver` starts automatically in a temp folder, with the same `schema.sql`. Your Supabase data is never touched.
```bash
cd backend
pytest
```
Covered: saving to the DB, every validation rule, non-JSON rejection, SQL-injection payloads, admin-only routes returning 401, wrong passwords, cookie flags (HttpOnly, SameSite), hashed passwords, forged cookies, logout, pagination, search (incl. literal `%`/`_`), filters, sorting, single record and 404, exact stats and analytics values, CSV export and formula escaping, student registration/login/history isolation, rate limits (429), security headers and path traversal.

### End-to-end browser test
Run once during development with Playwright + Microsoft Edge on the full stack (PostgreSQL → `manage.py init-db/create-admin/seed-demo` → Flask → browser). All 14 checks passed: home page; invalid form blocked; valid submission saved in the DB and form cleared; dashboard redirects when logged out; wrong password rejected; overview totals match the DB; search, filters, sort, detail modal and pagination; four charts render; CSV contains every DB row; printable report (and PDF); logout; student register → submit → history; no horizontal scroll at 390 px; zero JavaScript/CSP console errors.

### Manual test checklist (for the deployed site)
| # | Test | Expected |
|---|---|---|
| 1 | Open `/api/health` | `"database": "connected"` |
| 2 | Submit the form with empty fields | Red messages under each field, nothing saved |
| 3 | Submit a valid form | Success panel with reference #, form cleared, row visible in Supabase Table Editor |
| 4 | Open `/dashboard.html` in a private window | Redirected to login |
| 5 | Open `/api/feedback` in a private window | `401` JSON |
| 6 | Log in as admin | Cards show the same totals as Supabase |
| 7 | Search a student ID, filter category/rating, sort | Table updates correctly |
| 8 | Analytics tab | 4 charts; "Show data table" numbers match |
| 9 | Reports → Download CSV | File opens in Excel with all rows |
| 10 | Reports → Generate report → Print | A4 layout, save as PDF |
| 11 | Six wrong admin logins within a minute | 6th returns "Too many requests" |
| 12 | Open the site on a phone (mobile data) | Layout fits; submission works |
| 13 | `python backend/verify_deployment.py <url>` | All checks pass |

## 13. Screenshots
Captured from the running application during the end-to-end test (sample data from `seed-demo`).

| | |
|---|---|
| Home ![](docs/screenshots/01-home.png) | Feedback form ![](docs/screenshots/02-feedback-form.png) |
| Validation errors ![](docs/screenshots/03-form-validation.png) | Submission success ![](docs/screenshots/04-submit-success.png) |
| Admin login ![](docs/screenshots/05-admin-login.png) | Dashboard overview ![](docs/screenshots/06-dashboard-overview.png) |
| Feedback management ![](docs/screenshots/07-feedback-table.png) | Feedback detail ![](docs/screenshots/08-feedback-detail.png) |
| Analytics ![](docs/screenshots/09-analytics.png) | Reports ![](docs/screenshots/10-reports.png) |
| Printable report ![](docs/screenshots/11-printable-report.png) | Student history ![](docs/screenshots/13-student-history.png) |
| Mobile home ![](docs/screenshots/14-mobile-home.png) | Mobile dashboard ![](docs/screenshots/16-mobile-dashboard.png) |

A sample generated PDF report is in [`docs/screenshots/sample-report.pdf`](docs/screenshots/sample-report.pdf).
*After deploying, add a screenshot of the live URL and of the Supabase Table Editor showing the rows.*

## 14. Future enhancements
* Email confirmation to students and weekly summary emails to admins
* Admin replies / "action taken" status per feedback, visible in the student's history
* Anonymous-submission mode, and sentiment analysis of descriptions
* Multiple admin roles (department head sees only their department)
* Admin-editable categories and departments (move to tables)
* Redis-backed rate limiting and server-side sessions (revocable logout)
* `pg_trgm` index for fast fuzzy search at scale
* GitHub Actions CI to run `pytest` on every push
* Custom domain and dark mode

## 15. Implementation status

| Area | Status |
|---|---|
| Database schema (tables, constraints, indexes, RLS) | ✅ Implemented & tested (PostgreSQL 16) |
| Flask REST API (all required endpoints + pagination) | ✅ Implemented & tested (31 pytest tests) |
| Student portal (home, form, validation, stars, success, reset) | ✅ Implemented & browser-tested |
| Student accounts + submission history | ✅ Implemented & tested |
| Admin auth (hashing, sessions, protected routes, logout) | ✅ Implemented & tested |
| Admin dashboard (cards, table, search, filters, sort, detail) | ✅ Implemented & browser-tested |
| Analytics (4 Chart.js charts) | ✅ Implemented & values verified by tests |
| CSV export & printable report | ✅ Implemented & tested |
| Security (validation, SQLi, XSS/CSP, CSRF, rate limiting, headers) | ✅ Implemented & tested |
| Responsive layout | ✅ Tested at 1366 px and 390 px |
| Deployment configuration (`render.yaml`, env vars, health check) | ✅ Prepared |
| **Connection to *your* Supabase project** | ⏳ Needs your `DATABASE_URL` (docs/deployment.md §1–3) |
| **Live deployment on Render** | ⏳ Needs your GitHub + Render accounts (docs/deployment.md §5–6) |
| Verification of the live deployment | ⏳ Run `verify_deployment.py` after deploying |
