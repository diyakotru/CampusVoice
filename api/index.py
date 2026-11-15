"""
Vercel entry point.

Vercel runs Python files in api/ as serverless functions. This file puts
backend/ on the import path and exposes the existing Flask app, which serves
both the REST API (/api/...) and the frontend pages from one URL.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app import app  # noqa: E402,F401  (Vercel looks for the WSGI object named "app")
