"""Cookie-based session authentication for protected file routes."""

import secrets
import time
from threading import Lock

from config import (
    FILE_AUTH_PASSWORD,
    FILE_AUTH_USERNAME,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE,
)

_sessions = {}
_sessions_lock = Lock()


def is_auth_configured():
    """Return True when file auth credentials are set in the environment."""
    return bool(FILE_AUTH_USERNAME and FILE_AUTH_PASSWORD)


def _purge_expired_sessions():
    now = time.time()
    expired = [
        token
        for token, expiry in _sessions.items()
        if expiry <= now
    ]
    for token in expired:
        del _sessions[token]


def get_cookie(handler, name):
    """Return a cookie value from the request, or None."""
    cookie_header = handler.headers.get("Cookie", "")
    prefix = f"{name}="

    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(prefix):
            return part[len(prefix):]

    return None


def is_https(handler):
    """Return True when the request arrived over HTTPS."""
    if handler.headers.get("X-Forwarded-Proto", "").lower() == "https":
        return True

    return handler.server.server_port == 443


def set_session_cookie(handler, token):
    """Attach a session cookie to the response."""
    cookie = (
        f"{SESSION_COOKIE_NAME}={token}; "
        f"Max-Age={SESSION_MAX_AGE}; "
        "Path=/; HttpOnly; SameSite=Lax"
    )

    if is_https(handler):
        cookie += "; Secure"

    handler.send_header("Set-Cookie", cookie)


def clear_session_cookie(handler):
    """Expire the session cookie in the browser."""
    cookie = f"{SESSION_COOKIE_NAME}=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax"

    if is_https(handler):
        cookie += "; Secure"

    handler.send_header("Set-Cookie", cookie)


def create_session():
    """Create a new session and return its token."""
    token = secrets.token_urlsafe(32)
    expiry = time.time() + SESSION_MAX_AGE

    with _sessions_lock:
        _purge_expired_sessions()
        _sessions[token] = expiry

    return token


def destroy_session(token):
    """Remove a session token."""
    if not token:
        return

    with _sessions_lock:
        _sessions.pop(token, None)


def is_authenticated(handler):
    """Return True when the request has a valid session cookie."""
    token = get_cookie(handler, SESSION_COOKIE_NAME)
    if not token:
        return False

    now = time.time()

    with _sessions_lock:
        expiry = _sessions.get(token)
        if expiry is None or expiry <= now:
            _sessions.pop(token, None)
            return False

    return True


def verify_credentials(username, password):
    """Return True when username and password match configured values."""
    if not is_auth_configured():
        return False

    username_ok = secrets.compare_digest(username, FILE_AUTH_USERNAME)
    password_ok = secrets.compare_digest(password, FILE_AUTH_PASSWORD)
    return username_ok and password_ok
