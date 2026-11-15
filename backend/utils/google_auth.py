"""
Verifying "Sign in with Google" ID tokens.

The browser shows Google's button; after the student picks an account,
Google hands the page an ID TOKEN (a JWT signed by Google). The page sends
it to us and we check it here — we never trust the browser's word for who
the user is:

  * the signature must be valid (Google's public keys, fetched and cached),
  * it must be issued by accounts.google.com,
  * it must be meant for OUR app (audience == GOOGLE_CLIENT_ID),
  * it must not be expired, and the email must be verified by Google.

Only then do we use the token's `sub` (Google's permanent, unique account ID)
to find or create the student.
"""
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

_transport = google_requests.Request()   # reused so Google's keys stay cached


class InvalidGoogleToken(Exception):
    pass


def verify_google_token(token, client_id):
    """Return {sub, email, name} for a valid token, else raise InvalidGoogleToken."""
    if not isinstance(token, str) or not token or len(token) > 4096:
        raise InvalidGoogleToken("Missing Google credential.")
    try:
        claims = id_token.verify_oauth2_token(token, _transport, client_id)
    except ValueError as exc:   # bad signature, wrong audience, expired, malformed…
        raise InvalidGoogleToken(str(exc)) from exc
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise InvalidGoogleToken("Wrong issuer.")
    if not claims.get("email_verified"):
        raise InvalidGoogleToken("Google email is not verified.")
    return {
        "sub": claims["sub"],
        "email": claims.get("email", ""),
        "name": claims.get("name", ""),
    }
