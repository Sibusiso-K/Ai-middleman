"""Private-console controls: session integrity, route protection and safe config."""
import os

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import auth, dashboard_api, friend, pipeline
from app.security import (
    COOKIE_NAME, _attempts, hash_password, make_session, valid_session,
    validate_production_configuration, verify_password,
)


TEST_SECRET = "a-test-session-secret-that-is-longer-than-thirty-two-characters"


@pytest.fixture(autouse=True)
def secure_test_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_INSECURE_LOCAL_AUTH", "true")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5174")
    monkeypatch.setenv("SESSION_SIGNING_SECRET", TEST_SECRET)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password("correct horse battery staple", salt=b"0123456789abcdef"))
    monkeypatch.setenv("MAX_REQUEST_BYTES", "1024")
    _attempts.clear()


def owner_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(dashboard_api.router)
    app.include_router(friend.router)
    app.include_router(pipeline.router)
    return app


def test_password_hash_is_salted_and_constant_time_checkable():
    stored = hash_password("secret", salt=b"0123456789abcdef")
    assert stored.startswith("scrypt$16384$8$1$")
    assert verify_password("secret", stored)
    assert not verify_password("not secret", stored)
    assert not verify_password("secret", "plain-text-secret")


def test_session_rejects_tampering_and_expiry():
    token = make_session(TEST_SECRET, now=100)
    assert valid_session(token, TEST_SECRET, now=101)
    assert not valid_session(token + "x", TEST_SECRET, now=101)
    assert not valid_session(token, TEST_SECRET, now=100 + 8 * 60 * 60 + 1)


def test_private_routes_reject_before_accessing_database():
    with TestClient(owner_app()) as client:
        for method, path in [
            ("get", "/api/analytics/sectors"), ("get", "/friend/thread"),
            ("get", "/pipeline/events"), ("post", "/friend/send"),
        ]:
            response = client.request(method.upper(), path, json={"text": "hello"} if method == "post" else None)
            assert response.status_code == 401


def test_login_sets_http_only_session_and_allows_private_route():
    with TestClient(owner_app()) as client:
        response = client.post("/auth/login", json={"password": "correct horse battery staple"})
        assert response.status_code == 204
        cookie = response.headers["set-cookie"].lower()
        assert COOKIE_NAME in cookie and "httponly" in cookie and "samesite=strict" in cookie
        assert client.get("/auth/session").json() == {"authenticated": True}
        assert client.post("/auth/logout").status_code == 204
        assert client.get("/auth/session").status_code == 401


def test_login_rate_limit_blocks_guessing():
    with TestClient(owner_app()) as client:
        for _ in range(8):
            assert client.post("/auth/login", json={"password": "wrong"}).status_code == 401
        assert client.post("/auth/login", json={"password": "correct horse battery staple"}).status_code == 429


@pytest.mark.parametrize("name,value", [
    ("ADMIN_PASSWORD_HASH", ""), ("SESSION_SIGNING_SECRET", "short"),
    ("CORS_ALLOWED_ORIGINS", "*"), ("MAX_REQUEST_BYTES", "not-a-number"),
])
def test_unsafe_configuration_fails_closed(monkeypatch, name, value):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        validate_production_configuration()


def test_production_requires_https_origins(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://example.com")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "secret")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "token")
    with pytest.raises(RuntimeError, match="HTTPS"):
        validate_production_configuration()


@pytest.mark.asyncio
async def test_api_adds_private_response_headers_without_starting_database():
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.example.test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_startup_rejects_unsafe_config_before_touching_database(monkeypatch):
    from app.main import app, lifespan

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "")
    with pytest.raises(RuntimeError, match="Unsafe deployment configuration"):
        async with lifespan(app):
            pass
