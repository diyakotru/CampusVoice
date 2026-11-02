"""
Flask extensions created once and attached to the app in app.py.

Rate limiting: each client IP gets a limited number of requests to the
sensitive endpoints (login, submit). This slows down password guessing and
spam. Note: the default "memory://" storage keeps counters inside the
running process, which is fine for one Render instance. With several
instances you would point RATELIMIT_STORAGE_URI at Redis.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
