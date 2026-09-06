"""Authentication and deployment safety controls for private owner APIs."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, Request, Response

load_dotenv(Path(__file__).parent.parent / ".env")

COOKIE_NAME = "ai_middleman_session"
SESSION_SECONDS = 8 * 60 * 60
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_ATTEMPTS = 8
_attempts: dict[str, deque[float]] = defaultdict(deque)


def setting(name: str, default: str = "") -> str:
    return os.getenv(name, "").strip() or default


def is_example(value: str) -> bool:
    return not value or value.lower().startswith("your_") or value.lower() in {"changeme", "replace_me"}


def is_production() -> bool:
    return setting("APP_ENV", "production").lower() == "production"


def local_demo_bypass_enabled() -> bool:
    """Allow an explicit localhost-only demo without owner-login setup.

    This can never activate in production.  The launcher also refuses to
    start ngrok while it is enabled, preventing accidental public exposure.
    """
    return (
        not is_production()
        and setting("LOCAL_DEMO_BYPASS_AUTH").lower() in {"1", "true", "yes"}
    )


@dataclass(frozen=True)
class SecuritySettings:
    password_hash: str
    session_secret: str
    frontend_origins: tuple[str, ...]
    secure_cookies: bool
    max_request_bytes: int


def security_settings() -> SecuritySettings:
    origins = tuple(origin.strip().rstrip("/") for origin in setting(
        "CORS_ALLOWED_ORIGINS", "http://localhost:5174"
    ).split(",") if origin.strip())
    secure = is_production() or setting("ALLOW_INSECURE_LOCAL_AUTH").lower() not in {"1", "true", "yes"}
    try:
        max_request_bytes = int(setting("MAX_REQUEST_BYTES", str(10 * 1024 * 1024)))
    except ValueError as exc:
        raise RuntimeError("MAX_REQUEST_BYTES must be an integer") from exc
    return SecuritySettings(
        password_hash=setting("ADMIN_PASSWORD_HASH"),
        session_secret=setting("SESSION_SIGNING_SECRET"),
        frontend_origins=origins,
        secure_cookies=secure,
        max_request_bytes=max_request_bytes,
    )


def validate_production_configuration() -> None:
    """Fail closed before the app can expose contact data or mutate records."""
    settings = security_settings()
    errors = []
    if not local_demo_bypass_enabled() and (
        is_example(settings.password_hash) or not settings.password_hash.startswith("scrypt$")
    ):
        errors.append("ADMIN_PASSWORD_HASH must be an scrypt hash")
    if not local_demo_bypass_enabled() and (
        len(settings.session_secret) < 32 or is_example(settings.session_secret)
    ):
        errors.append("SESSION_SIGNING_SECRET must be a random value of at least 32 characters")
    if not settings.frontend_origins or "*" in settings.frontend_origins:
        errors.append("CORS_ALLOWED_ORIGINS must list explicit HTTPS frontend origins")
    if is_production() and any(not origin.startswith("https://") for origin in settings.frontend_origins):
        errors.append("production CORS_ALLOWED_ORIGINS must use HTTPS")
    if not 1 <= settings.max_request_bytes <= 25 * 1024 * 1024:
        errors.append("MAX_REQUEST_BYTES must be between 1 byte and 25 MiB")
    if is_production():
        for name in ("WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN"):
            if is_example(setting(name)):
                errors.append(f"{name} must be configured")
    if errors:
        raise RuntimeError("Unsafe deployment configuration: " + "; ".join(errors))


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    if not password:
        raise ValueError("Password cannot be blank")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    encode = lambda value: base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
    return "scrypt$16384$8$1$" + encode(salt) + "$" + encode(digest)


def _decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = stored.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=_decode(salt),
                                n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, _decode(expected))
    except (ValueError, TypeError):
        return False


def _signature(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()


def make_session(secret: str, now: int | None = None) -> str:
    expiry = int(now if now is not None else time.time()) + SESSION_SECONDS
    payload = base64.urlsafe_b64encode(f"owner:{expiry}:{secrets.token_urlsafe(16)}".encode()).decode().rstrip("=")
    return f"{payload}.{_signature(payload, secret)}"


def valid_session(token: str | None, secret: str, now: int | None = None) -> bool:
    try:
        payload, signature = (token or "").split(".", 1)
        if not hmac.compare_digest(_signature(payload, secret), signature):
            return False
        subject, expiry, _nonce = _decode(payload).decode("utf-8").split(":", 2)
        return subject == "owner" and int(expiry) >= int(now if now is not None else time.time())
    except (ValueError, UnicodeDecodeError):
        return False


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def can_attempt_login(request: Request, now: float | None = None) -> bool:
    now = now if now is not None else time.monotonic()
    entries = _attempts[client_key(request)]
    while entries and entries[0] <= now - LOGIN_WINDOW_SECONDS:
        entries.popleft()
    return len(entries) < LOGIN_ATTEMPTS


def record_failed_login(request: Request, now: float | None = None) -> None:
    _attempts[client_key(request)].append(now if now is not None else time.monotonic())


def clear_login_attempts(request: Request) -> None:
    _attempts.pop(client_key(request), None)


async def require_admin(request: Request) -> None:
    if local_demo_bypass_enabled():
        return
    settings = security_settings()
    if not valid_session(request.cookies.get(COOKIE_NAME), settings.session_secret):
        raise HTTPException(status_code=401, detail="Owner authentication required")


def set_session_cookie(response: Response) -> None:
    settings = security_settings()
    response.set_cookie(
        COOKIE_NAME, make_session(settings.session_secret), max_age=SESSION_SECONDS,
        httponly=True, secure=settings.secure_cookies, samesite="strict", path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True,
                           secure=security_settings().secure_cookies, samesite="strict")
