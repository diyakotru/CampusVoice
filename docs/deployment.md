# Deployment Guide — Supabase + Vercel

This guide takes the project from your laptop to a public HTTPS URL that anyone can open from any device.
**Both the frontend and the backend are deployed on Vercel** as one project: Flask runs as a Python
serverless function and serves the REST API (`/api/...`) and the HTML/CSS/JS pages from the same URL.

```
 GitHub repo ──(auto-deploy on push)──▶ Vercel project (Flask serverless function + frontend)
                                              │  DATABASE_URL (env var, TLS)
                                              ▼
                                    Supabase PostgreSQL (cloud DB)
```

Total cost: **₹0 / $0** on the free tiers (see [Limits](#7-free-tier-limits-and-possible-charges)).

---

## 1. Create the cloud database (Supabase)

1. Go to <https://supabase.com> → **Start your project** → sign in with GitHub.
2. **New project**
   - Name: `campusvoice`
   - Database password: click **Generate a password** and **save it somewhere safe**. You need it in step 3.
   - Region: the one closest to you (e.g. *South Asia (Mumbai)*). Later, set the Vercel function region to the same area if possible.
   - Plan: **Free**.
3. Wait ~2 minutes for provisioning. Then click **Connect** (top bar of the project page).
4. Under **Connection string**, choose **Transaction pooler**. Copy the URI. It looks like:
   ```
   postgresql://postgres.abcdefghijkl:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
   ```
   Replace `[YOUR-PASSWORD]` with your database password. If the password contains any of `@ : / ? # %`, URL-encode them (e.g. `@` → `%40`), or reset the password to one with only letters and digits.

   > **Why the Transaction pooler and not the "Direct connection"?** On the free plan the direct host (`db.xxxx.supabase.co`) is reachable only over **IPv6**. Vercel functions and many home networks use IPv4, so the direct URL fails with "could not translate host name" or "Network is unreachable". The pooler supports IPv4. The *transaction* mode (port 6543) is designed for serverless platforms like Vercel, where many short-lived function instances each open a few connections.

## 2. Create the tables

Pick **one** option.

**Option A: Supabase SQL Editor (easiest)**
Supabase dashboard → **SQL Editor** → **New query** → paste all of [`database/schema.sql`](../database/schema.sql) → **Run**. You should see "Success. No rows returned". Check **Table Editor**: `feedback`, `admins` and `students` now exist.

**Option B: from your computer**
```bash
cd backend
copy .env.example .env          # macOS/Linux: cp .env.example .env
# edit .env → paste DATABASE_URL, set SECRET_KEY
python manage.py init-db
python manage.py check-db       # prints the server version and the 3 tables
```

The schema also **enables Row Level Security** and revokes access from Supabase's public `anon` role. Supabase automatically publishes every table through a REST API that works with the public "anon key". These two settings make sure nobody can read student data through that API. Only our backend, which holds the private connection string, can access the tables.

## 3. Create the first admin account

Admins are never created from the website (that would let anyone become an admin). Run this once from your computer, with `DATABASE_URL` in `backend/.env` pointing at Supabase:

```bash
cd backend
python manage.py create-admin
# Admin username: admin
# Admin password: ********   (min 8 chars, letters + digits)
```

The same command resets the password of an existing admin.

## 4. Test locally against Supabase (optional but recommended)

```bash
cd backend
python app.py
```
Open <http://localhost:5000>, submit feedback, then log in at <http://localhost:5000/login.html>. In Supabase → **Table Editor → feedback**, you can see the row appear. This proves your laptop talks to the cloud database.

## 5. Push the code to GitHub

```bash
cd Cloud_Feedback_System
git init
git add .
git status            # make sure backend/.env is NOT listed (it is in .gitignore)
git commit -m "Cloud feedback system"
git branch -M main
git remote add origin https://github.com/<your-username>/cloud-feedback-system.git
git push -u origin main
```
Create the empty repository on GitHub first (**New repository**, no README).

## 6. Deploy frontend + backend (Vercel)

The repository already contains everything Vercel needs:

| File | Purpose |
|---|---|
| [`vercel.json`](../vercel.json) | Sends every request to the Flask function and bundles the `backend/` and `frontend/` folders with it. |
| [`api/index.py`](../api/index.py) | Vercel entry point. Adds `backend/` to the import path and exposes the Flask `app`. |
| [`requirements.txt`](../requirements.txt) | Python packages Vercel installs (keep in sync with `backend/requirements.txt`). |

1. Go to <https://vercel.com> → sign in with GitHub.
2. **Add New → Project** → import your repository.
3. Configure the project:
   - **Project Name**: lowercase only, e.g. `campusvoice`.
   - **Root Directory**: the repository root (`./`), **not** `backend`. Otherwise Vercel cannot see `frontend/`, `vercel.json` or `api/`.
   - **Application Preset**: **Other**.
   - **Build and Output Settings**: leave empty.
4. Open **Environment Variables** and add:

   | Key | Value |
   |---|---|
   | `FLASK_ENV` | `production` |
   | `SECRET_KEY` | output of `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `DATABASE_URL` | the Supabase Transaction pooler URI from step 1 (with your password) |
   | `DB_POOL_MIN` | `1` |
   | `DB_POOL_MAX` | `2` |
   | `SESSION_LIFETIME_MINUTES` | `120` |

5. Click **Deploy**. The first build takes 1–2 minutes.
6. Open the URL shown, e.g. `https://campusvoice.vercel.app`.
   - `https://campusvoice.vercel.app/api/health` should show `"database": "connected"`.

`FLASK_ENV=production` turns on `Secure` cookies and HSTS. Every later `git push` to `main` redeploys automatically, and every other branch gets its own preview URL.

### Verify the deployment

From your computer:
```bash
cd backend
python verify_deployment.py https://campusvoice.vercel.app
```
The script checks that the site is reachable over the internet and that the backend reports a live database connection. It then submits one feedback (student ID `VERIFY-…`), logs in as admin and reads that row back from Supabase. It finishes by confirming that anonymous users get `401`. Then open the URL on your **phone using mobile data** (not Wi-Fi) to demonstrate remote access from a different network.

## 7. Free-tier limits and possible charges

| Service | Free tier | What to watch |
|---|---|---|
| **Vercel (Hobby)** | Free for personal, non-commercial projects, with monthly function and bandwidth quotas | Functions scale to zero when idle, so the first request after a quiet period has a short **cold start (~1–3 s)**. The Hobby plan never bills you; if quotas run out, Vercel pauses the project instead. |
| **Supabase** | 500 MB database, 5 GB egress, 2 free projects | Free projects are **paused after 7 days of inactivity**. Restore them from the dashboard (data is kept). No charges on the Free plan. Spend caps are on by default for paid plans. |
| **GitHub** | Free public/private repos | — |

Neither service needs a credit card for the free tier as of writing. Check their pricing pages before upgrading anything.

## 8. Why one Vercel project for both frontend and backend?

Flask serves the frontend and the API from the **same origin**, so the admin/student session cookie is a normal first-party cookie and no CORS setup is needed.

If you split them into two Vercel projects that call each other directly, note that `vercel.app` is a "public suffix": two sub-domains count as **different sites**, the session cookie becomes a *third-party cookie*, and Safari (and Chrome/Edge in some privacy modes) block it, so login fails. If you do need two projects, keep the browser on one origin by proxying the API through the frontend project:

1. Backend project: set `SERVE_FRONTEND=false`.
2. Frontend project: **Root Directory** = `frontend`, and add `frontend/vercel.json`:
   ```json
   { "rewrites": [{ "source": "/api/:path*", "destination": "https://<backend-project>.vercel.app/api/:path*" }] }
   ```
3. Keep `API_BASE_URL: ""` in `frontend/js/config.js`.

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `/api/health` → `503 "database": "unreachable"` | Wrong `DATABASE_URL`, wrong password, or the Supabase project is paused. Use the **Transaction pooler** URI. Check **Vercel → Project → Logs** for the exact psycopg2 error. |
| Pages return 404 but `/api/health` works | The project's Root Directory is `backend`. Change it to the repository root in **Settings → Build and Deployment** and redeploy. |
| `500` with `Configuration error` in the logs | `SECRET_KEY` or `DATABASE_URL` is missing. Add it under **Settings → Environment Variables**, then **Redeploy**. |
| `password authentication failed` | The password in the URI is wrong or contains un-encoded special characters. |
| Admin login works locally but not on Vercel | You created the admin in a different database. Run `create-admin` with the **Supabase** `DATABASE_URL`. |
| `429 Too many requests` | Rate limit hit (5 submissions or 5 admin logins per minute per IP). Wait one minute. |
| First request is slow (1–3 s) | Serverless cold start after the function was idle. This is expected. |
