"""The owner's approval boundary must reject forged webhook callbacks."""

import hashlib
import hmac

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routes import whatsapp_webhook as webhook


@pytest.mark.parametrize(
    "secret,signature,status",
    [
        (None, "", 503),
        ("your_app_secret_here", "", 503),
        ("test-secret", "", 403),
        ("test-secret", "sha256=forged", 403),
    ],
)
def test_invalid_signatures_never_dispatch(monkeypatch, secret, signature, status):
    monkeypatch.setattr(webhook, "APP_SECRET", secret)
    app = FastAPI()
    app.include_router(webhook.router)
    with TestClient(app) as client:
        response = client.post(
            "/webhook/whatsapp",
            content=b"not even json",
            headers={"X-Hub-Signature-256": signature},
        )
    assert response.status_code == status


def test_valid_signature_reaches_handler(monkeypatch):
    secret = "test-secret"
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    monkeypatch.setattr(webhook, "APP_SECRET", secret)
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    app = FastAPI()
    app.include_router(webhook.router)
    with TestClient(app) as client:
        response = client.post(
            "/webhook/whatsapp",
            content=body,
            headers={"X-Hub-Signature-256": signature},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "received"}
