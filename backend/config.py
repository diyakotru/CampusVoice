"""
Application configuration.

Every secret (database URL, session key) is read from ENVIRONMENT VARIABLES,
never written in code. Locally they come from backend/.env (loaded by
python-dotenv); on Vercel they are set in Project → Settings → Environment Variables.
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# Load backend/.env if it exists (does nothing on Vercel, where no .env file exists)
load_dotenv(BASE_DIR / ".env")


def _bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


class Config:
    # "development" or "production"
    ENV_NAME = os.environ.get("FLASK_ENV", "production").lower()
    IS_PRODUCTION = ENV_NAME == "production"

    # Signs the session cookie. Must be long and random in production.
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # PostgreSQL connection string (Supabase → Project Settings → Database)
    DATABASE_URL = os.environ.get("DATABASE_URL")
    DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN", "1"))
    DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "5"))

    # ---- Session cookie hardening ----
    SESSION_COOKIE_NAME = "cfs_session"
    SESSION_COOKIE_HTTPONLY = True                      # JavaScript cannot read the cookie
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", IS_PRODUCTION)  # HTTPS only
    # "Lax" when frontend and backend share one origin (recommended setup).
    # "None" is only needed if the frontend is hosted on a different domain.
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.environ.get("SESSION_LIFETIME_MINUTES", "120"))
    )

    # ---- CORS: which other websites may call this API from a browser ----
    # Empty = same-origin only (Flask serves the frontend itself).
    CORS_ORIGINS = _list("CORS_ORIGINS")

    # ---- Serve the frontend/ folder from Flask (single-service deployment) ----
    SERVE_FRONTEND = _bool("SERVE_FRONTEND", True)
    FRONTEND_DIR = PROJECT_ROOT / "frontend"

    # ---- Rate limiting (Flask-Limiter) ----
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_ENABLED = _bool("RATELIMIT_ENABLED", True)
    RATELIMIT_HEADERS_ENABLED = True

    # ---- "Sign in with Google" for students ----
    # OAuth Client ID from Google Cloud Console (APIs & Services → Credentials).
    # It is public (it appears in the page); there is no client secret in this flow.
    # Leave empty to hide the Google button.
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()

    # Reject request bodies larger than 64 KB
    MAX_CONTENT_LENGTH = 64 * 1024

    # Number of reverse proxies in front of the app (Vercel has 1).
    # Needed so rate limiting sees the real client IP, not the proxy's.
    PROXY_COUNT = int(os.environ.get("PROXY_COUNT", "1" if IS_PRODUCTION else "0"))

    @classmethod
    def validate(cls):
        """Fail fast with a clear message instead of crashing on the first request."""
        problems = []
        if not cls.DATABASE_URL:
            problems.append("DATABASE_URL is not set (see backend/.env.example).")
        if not cls.SECRET_KEY:
            if cls.IS_PRODUCTION:
                problems.append("SECRET_KEY is not set. Generate one with: "
                                "python -c \"import secrets; print(secrets.token_hex(32))\"")
            else:
                # Development convenience only — sessions reset on every restart.
                cls.SECRET_KEY = os.urandom(32).hex()
        elif cls.IS_PRODUCTION and len(cls.SECRET_KEY) < 32:
            problems.append("SECRET_KEY must be at least 32 characters in production.")
        if problems:
            raise RuntimeError("Configuration error:\n  - " + "\n  - ".join(problems))
