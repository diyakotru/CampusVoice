"""
Entry point of the Flask backend.

Locally:      python app.py                      → http://localhost:5000
On Vercel:    api/index.py imports this app (see vercel.json)

create_app() builds the application: loads config, connects the database
layer, registers the API blueprints, and (optionally) serves the frontend
folder so the whole system runs from a single URL.
"""
import logging

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from database import DatabaseUnavailable, init_db
from extensions import limiter
from routes import ALL_BLUEPRINTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

# Content-Security-Policy: the browser may only load scripts/styles/fonts
# from our own origin and the two CDNs we use. This blunts XSS attacks.
CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def create_app(overrides=None):
    Config.validate()
    frontend_dir = str(Config.FRONTEND_DIR)
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    # Vercel (and most clouds) put a proxy in front of the app. ProxyFix makes
    # request.remote_addr / request.scheme reflect the real client and HTTPS.
    if app.config["PROXY_COUNT"]:
        n = app.config["PROXY_COUNT"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)

    init_db(app)
    limiter.init_app(app)

    # CORS is only needed when the frontend lives on a different domain.
    if app.config["CORS_ORIGINS"]:
        CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
             supports_credentials=True, methods=["GET", "POST", "OPTIONS"],
             allow_headers=["Content-Type"])

    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    # ------------------------------------------------------------ frontend
    if app.config["SERVE_FRONTEND"]:
        @app.get("/")
        def index():
            return send_from_directory(frontend_dir, "index.html")

        @app.get("/<path:filename>")
        def frontend_files(filename):
            if filename.startswith("api/"):
                return jsonify(error="Endpoint not found."), 404
            return send_from_directory(frontend_dir, filename)

    # ------------------------------------------------------------ headers
    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")  # never cache student data
        else:
            response.headers.setdefault("Content-Security-Policy", CSP)
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    # ------------------------------------------------------------ errors
    # Every API error is returned as JSON: {"error": "..."} with a proper status code.
    @app.errorhandler(DatabaseUnavailable)
    def db_unavailable(exc):
        log.error("Database unavailable: %s", exc)
        return jsonify(error="The database is temporarily unavailable. Please try again shortly."), 503

    @app.errorhandler(429)
    def too_many_requests(exc):
        return jsonify(error="Too many requests. Please wait a minute and try again."), 429

    @app.errorhandler(HTTPException)
    def http_error(exc):
        if request.path.startswith("/api/") or not app.config["SERVE_FRONTEND"]:
            return jsonify(error=exc.description if exc.code != 404 else "Endpoint not found."), exc.code
        if exc.code == 404:
            return send_from_directory(frontend_dir, "404.html"), 404
        return exc

    @app.errorhandler(Exception)
    def unexpected_error(exc):
        log.exception("Unhandled error on %s %s", request.method, request.path)
        return jsonify(error="An unexpected server error occurred."), 500

    return app


app = create_app()

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)),
            debug=not Config.IS_PRODUCTION)
