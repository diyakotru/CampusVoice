"""
Verify a DEPLOYED instance end-to-end over the internet.

    python verify_deployment.py https://campusvoice.onrender.com

What it proves:
  1. The server is reachable from this machine (remote accessibility).
  2. The server is connected to the cloud database (/api/health).
  3. A feedback submitted over HTTPS is written to the database and can be
     read back through the protected admin API (full round trip).
  4. Admin routes reject requests without a session.

It submits ONE real feedback row whose student ID starts with VERIFY-, so
you can recognise it in the dashboard. Uses only the Python standard library.
"""
import getpass
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request

if len(sys.argv) != 2:
    sys.exit("Usage: python verify_deployment.py https://your-app.onrender.com")

BASE = sys.argv[1].rstrip("/")
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
failures = 0


def call(method, path, body=None, timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read() or b"null")
        except ValueError:
            return err.code, None


def step(name, ok, detail=""):
    global failures
    failures += 0 if ok else 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


print(f"Verifying {BASE}\n(the first request can take ~60 s if the free Render instance is asleep)\n")

start = time.time()
status, body = call("GET", "/api/health")
step("Server reachable over the internet", status in (200, 503), f"HTTP {status} in {time.time() - start:.1f}s")
step("Backend connected to cloud database", status == 200 and body and body.get("database") == "connected",
     body.get("database_engine", body) if isinstance(body, dict) else str(body))

status, _ = call("GET", "/api/feedback")
step("Admin API rejects anonymous access", status == 401, f"HTTP {status}")

marker = f"VERIFY-{int(time.time()) % 100000}"
status, body = call("POST", "/api/feedback", {
    "student_name": "Deployment Check", "student_id": marker, "department": "Other", "semester": 1,
    "category": "Overall College Experience", "rating": 5,
    "description": "Automated deployment verification submission.", "suggestions": "",
})
step("Feedback accepted by deployed API", status == 201, f"HTTP {status}, id={body.get('feedback', {}).get('id') if body else None}")

username = input("\nAdmin username (blank to skip the read-back check): ").strip()
if username:
    password = getpass.getpass("Admin password: ")
    status, _ = call("POST", "/api/admin/login", {"username": username, "password": password})
    step("Admin login over HTTPS", status == 200, f"HTTP {status}")
    if status == 200:
        status, body = call("GET", f"/api/feedback?search={marker}")
        found = status == 200 and body["pagination"]["total"] == 1
        step("Submitted row read back from cloud database", found, marker)
        call("POST", "/api/admin/logout", {})

print("\nAll checks passed." if failures == 0 else f"\n{failures} check(s) failed.")
sys.exit(1 if failures else 0)
