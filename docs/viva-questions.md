# Viva Questions & Answers

Short, accurate answers you can expand on. Where useful, the file to open during the viva is given.

---

## A. Project & architecture

**1. What problem does the project solve?**
Paper or ad-hoc feedback is slow to collect, easy to lose and hard to analyse. Our system collects feedback online from any device, stores it in a managed cloud database, and gives administrators search, analytics and export instantly.

**2. Describe the architecture.**
Three tiers. Presentation: HTML/CSS/JS with Bootstrap and Chart.js in the browser. Application: a Flask REST API running under Gunicorn on Render. Data: PostgreSQL on Supabase. The browser talks only to Flask over HTTPS, and only Flask talks to the database, over TLS, using a secret connection string.

**3. Why didn't the frontend talk to Supabase directly?**
Then the browser would need database credentials or the public API key, and every rule (validation, who may read what) would have to be enforced by database policies alone. Keeping a backend lets us validate, rate-limit, hash passwords and hide student data behind admin authentication. The database is never exposed to users.

**4. What is a REST API? Give examples from your project.**
An interface where resources are identified by URLs and manipulated with HTTP methods, exchanging JSON, and each request is self-contained (stateless). `POST /api/feedback` creates feedback, `GET /api/feedback?page=2` lists it, `GET /api/feedback/15` reads one record.

**5. Which HTTP status codes do you return and when?**
200 OK (success), 201 Created (feedback submitted, account created), 400 Bad Request (validation failed), 401 Unauthorized (not logged in or wrong password), 404 Not Found, 409 Conflict (student ID already registered), 413 (body too large), 415 (not JSON), 429 Too Many Requests (rate limit), 500 (unexpected error), 503 (database unreachable).

**6. Explain the request–response cycle for submitting feedback.**
`feedback.js` validates the form and sends `POST /api/feedback` with JSON over HTTPS. Render's proxy passes it to Gunicorn and then Flask. Flask checks the rate limit and content type, validates every field again, and runs a parameterised `INSERT … RETURNING id` on Supabase. PostgreSQL checks constraints and stores the row. Flask returns `201` with the new ID, and the browser shows the success panel and clears the form. (See `docs/architecture.md` §4.)

**7. Why Flask and not Django?**
Flask is minimal. For a JSON API with three tables we don't need Django's ORM, admin site or template system, and with Flask every part of the request flow is visible in our own code, which is better for learning.

**8. What is Gunicorn and why is it needed?**
A production WSGI HTTP server. Flask's built-in server is single-purpose and not secure or efficient enough for production. Gunicorn manages worker processes and threads that call our Flask app. We use 1 worker × 4 threads.

**9. What is WSGI?**
Web Server Gateway Interface, the Python standard (PEP 3333) for how a web server calls a Python web application. `app:app` tells Gunicorn the module and the WSGI callable.

## B. Cloud computing

**10. Where is cloud computing actually used in this project?**
The application runs on Render (PaaS), the data lives in Supabase PostgreSQL (DBaaS), and both are reached over the public internet with HTTPS. Configuration comes from environment variables set in the cloud dashboard. Deployment is continuous from GitHub. Nothing runs on our own hardware once deployed.

**11. Differentiate IaaS, PaaS and SaaS with examples.**
IaaS gives virtual machines, networks and storage, and you manage the OS (AWS EC2, Azure VMs). PaaS lets you deploy code while the provider manages runtime, OS and scaling (Render, Heroku, Google App Engine). SaaS is a finished application you use (Gmail, GitHub). Supabase is DBaaS, a managed-database flavour of PaaS.

**12. Which deployment model is this: public, private, hybrid?**
Public cloud: Render and Supabase are shared, multi-tenant infrastructure available to anyone.

**13. List the NIST essential characteristics of cloud computing and map them to your project.**
On-demand self-service (we created services from a dashboard). Broad network access (works on any device with a browser). Resource pooling (multi-tenant free tiers). Rapid elasticity (instance type and count can be changed without code changes). Measured service (usage-based quotas and billing).

**14. What happens when the free Render instance "sleeps"?**
After 15 minutes without traffic Render stops the instance (scale-to-zero). The next request starts it again, which takes about 30–60 seconds. This saves resources, at the cost of a slow first request.

**15. Why do you use environment variables?**
To keep secrets (database URL, session key) out of source code and Git, and to run the same code in different environments (local, production) with different configuration. This is a principle of the Twelve-Factor App.

**16. How would you scale this application for 10,000 students?**
Upgrade Render to a paid instance and run several instances behind its load balancer (the app is stateless, because sessions are signed cookies). Move rate-limit storage to Redis. Use Supabase's transaction pooler and a bigger compute tier. Add a `pg_trgm` index for search. Optionally cache analytics for a minute.

**17. What is a connection pool and why do you need one?**
A set of open database connections that are reused. Opening a TLS connection to a cloud database takes 100–300 ms, so reusing connections makes each request much faster and limits the total number of connections, because the Supabase free tier has a connection cap. We use `psycopg2.pool.ThreadedConnectionPool` (1–5 connections), and Supabase adds its own pooler (Supavisor).

**18. Why the Supabase "Session pooler" connection string?**
The free direct connection is IPv6-only. Render (and many networks) use IPv4. The pooler accepts IPv4 and also multiplexes connections.

**19. What is a health check?**
An endpoint the platform calls to know whether the app is working. Our `/api/health` runs `SELECT version(), NOW()` on Supabase and returns 200 only if the database answers. Render won't switch traffic to a new deployment that fails it.

**20. What is CI/CD here?**
Continuous deployment: `autoDeploy: true` makes Render build and deploy every push to `main`. Continuous integration would add running `pytest` on every push, for example with GitHub Actions (a listed future enhancement).

## C. Database

**21. Explain your tables and constraints.**
`feedback` (one row per submission; CHECKs on rating 1–5, semester 1–8, category list and text lengths), `admins` (unique username, password hash) and `students` (unique student ID, password hash). `feedback.student_account_id` is a nullable foreign key to `students`, with `ON DELETE SET NULL`.

**22. Why have constraints in the database if Flask already validates?**
Defence in depth. Any other path into the data (SQL editor, a future app, a bug) still cannot store invalid rows.

**23. What indexes did you create and why?**
`created_at DESC` for newest-first listing and trends, `category` and `rating` for filters, `student_id` for search, and `student_account_id` for the history page. Primary keys and unique columns are indexed automatically.

**24. How is the trend chart computed?**
`generate_series` builds every date in the range, and we `LEFT JOIN` feedback grouped by date so days with zero submissions still appear as 0.

**25. What is Row Level Security and why did you enable it?**
A PostgreSQL feature that filters which rows a role can see. Supabase automatically exposes tables through a public REST API usable with the public "anon" key. Enabling RLS with no policies, plus revoking privileges from `anon`, means that API returns nothing. Our backend connects as the table owner and is unaffected.

**26. Why TIMESTAMPTZ?**
It stores an absolute moment (internally UTC), so times are correct regardless of server or viewer time zone. The browser converts to local time for display.

## D. Security

**27. How do you prevent SQL injection?**
All values are passed as parameters (`cursor.execute(sql, params)`), never concatenated into SQL. The only dynamic SQL piece, the sort column, is chosen from a whitelist and quoted with `psycopg2.sql.Identifier`. A test submits `Robert'); DROP TABLE feedback;--` and confirms it is stored as plain text.

**28. How are passwords stored?**
As scrypt hashes with a random salt, via `werkzeug.security.generate_password_hash`. We never store or log the plain password. On login, `check_password_hash` hashes the attempt the same way and compares.

**29. Why hashing and not encryption?**
Encryption is reversible with a key. If the key leaks, all passwords leak. Hashing is one-way, and we never need the original password back, only to check whether an attempt matches.

**30. How does session management work?**
After login, Flask stores `admin_id` in the session, which it serializes into a cookie signed with HMAC using `SECRET_KEY`. The browser sends it with every request. If anyone changes it, the signature fails and they are treated as logged out. The cookie is `HttpOnly` (JavaScript can't read it), `Secure` (HTTPS only in production), `SameSite=Lax` (not sent on cross-site POSTs) and expires after 120 minutes.

**31. How are admin routes protected?**
The `@admin_required` decorator returns 401 unless `admin_id` is in the verified session. The dashboard page also checks `/api/session` and redirects to the login page, but the real protection is on the server. The page alone contains no data.

**32. What is XSS and how do you prevent it?**
Cross-site scripting means injecting script through stored text, for example feedback containing `<script>`. We escape all user-supplied text before inserting it into HTML (`UI.esc`), and a Content-Security-Policy allows scripts only from our origin and jsDelivr, so injected inline scripts would not run anyway.

**33. What is CSRF and how is it mitigated?**
Cross-site request forgery: another website making the victim's browser send an authenticated request. Our cookie is `SameSite=Lax`, so it is not sent on cross-site POSTs. In addition, all state-changing endpoints require `Content-Type: application/json`, which other sites cannot send without a CORS pre-flight that our server doesn't approve.

**34. What is CORS? Do you need it?**
Cross-Origin Resource Sharing: headers that tell browsers which other origins may call an API. In our recommended deployment Flask serves the frontend itself (same origin), so CORS is disabled. It is enabled only if `CORS_ORIGINS` is set for a separately hosted frontend.

**35. How does rate limiting work?**
Flask-Limiter counts requests per client IP per route: 5 per minute and 30 per hour for submissions, and 5 per minute and 20 per hour for admin login. Beyond that it returns 429. `ProxyFix` ensures we see the real client IP behind Render's proxy.

**36. How is student information kept private?**
Students' data is returned only by admin-protected endpoints. A logged-in student can see only rows linked to their own account. The `/api/session` endpoint describes only the caller's own login. The database is not publicly reachable, and Supabase's public API is locked by RLS.

## E. Frontend

**37. How does the star rating work?**
Five `<button role="radio">` elements. Clicking sets a hidden `rating` input and colours the stars, hovering previews, and arrow keys change the value for keyboard users. Validation fails if no star is chosen.

**38. How does the frontend know the backend's address?**
`frontend/js/config.js` → `API_BASE_URL`. Empty means same origin. It contains no secrets.

**39. How is the CSV export downloaded if it needs the session cookie?**
`fetch()` with `credentials: "include"` downloads the CSV as a Blob. A temporary object URL and `<a download>` link save it.

**40. How did you make it responsive?**
Bootstrap's grid and breakpoints, a collapsible navbar, an off-canvas sidebar on screens under 992 px, `table-responsive` for the table, and `clamp()` font sizes. The end-to-end test checks for no horizontal scrolling at 390 px width.

## F. Testing

**41. How did you test the project?**
(1) 31 automated `pytest` API tests run against a **real PostgreSQL 16** server started by `pgserver`, using the same `schema.sql`. They cover validation, injection, auth, cookies, hashing, filters, statistics, CSV, rate limits and privacy. (2) An end-to-end browser test with Playwright drove Microsoft Edge through every page (form, login, dashboard, filters, charts, CSV, report, student history, mobile) and checked the database rows directly. (3) `verify_deployment.py` checks the live deployment.

**42. Why not test against Supabase directly?**
Tests empty the tables before each test, which would delete real data. A throw-away local PostgreSQL gives the same engine and SQL. Deployment verification against Supabase is a separate, non-destructive step.
