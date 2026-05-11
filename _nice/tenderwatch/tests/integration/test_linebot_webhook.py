"""Integration tests for app.routes.linebot (LINE webhook).

Spins up a real FastAPI test client with the linebot router mounted.
Uses an in-memory SQLite DB (via conftest autouse fixture).
Computes valid LINE signatures in-test so we can verify both the
happy-path and the tamper-rejection path.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import Settings
from app.db import engine
from app.models.user import User


def sign(body: bytes, secret: str) -> str:
    return base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()


@pytest.fixture
def fake_settings(monkeypatch):
    s = Settings(
        line_bot_channel_access_token="tok",
        line_bot_channel_secret="csec",
        session_secret="x",
    )
    monkeypatch.setattr("app.routes.linebot.get_settings", lambda: s)
    return s


@pytest.fixture
def client(fake_settings):
    from app.routes import linebot

    app = FastAPI()
    app.include_router(linebot.router)
    return TestClient(app)


def _follow_body(user_id: str = "Uabc123") -> bytes:
    payload = {
        "destination": "Ctest",
        "events": [
            {
                "type": "follow",
                "source": {"type": "user", "userId": user_id},
                "timestamp": 1715000000000,
                "replyToken": "dummy",
            }
        ],
    }
    return json.dumps(payload).encode()


def _message_body(user_id: str = "Umsg456", text: str = "hello") -> bytes:
    payload = {
        "destination": "Ctest",
        "events": [
            {
                "type": "message",
                "source": {"type": "user", "userId": user_id},
                "timestamp": 1715000000001,
                "replyToken": "dummy",
                "message": {"type": "text", "id": "m1", "text": text},
            }
        ],
    }
    return json.dumps(payload).encode()


def _unfollow_body(user_id: str = "Uunf789") -> bytes:
    payload = {
        "destination": "Ctest",
        "events": [
            {
                "type": "unfollow",
                "source": {"type": "user", "userId": user_id},
                "timestamp": 1715000000002,
            }
        ],
    }
    return json.dumps(payload).encode()


# ---------------------------------------------------------------------------
# Test 1: valid signature + follow event → 200, user row created
# ---------------------------------------------------------------------------

def test_follow_event_creates_user(client, fake_settings):
    body = _follow_body("Uabc123")
    sig = sign(body, fake_settings.line_bot_channel_secret)

    resp = client.post(
        "/webhook/line",
        content=body,
        headers={"X-Line-Signature": sig, "Content-Type": "application/json"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    with Session(engine) as session:
        user = session.exec(select(User).where(User.line_user_id == "Uabc123")).first()
    assert user is not None
    assert user.line_user_id == "Uabc123"


# ---------------------------------------------------------------------------
# Test 2: invalid signature → 400
# ---------------------------------------------------------------------------

def test_invalid_signature_returns_400(client, fake_settings):
    body = _follow_body("Uxyz")
    bad_sig = "invalidsignature=="

    resp = client.post(
        "/webhook/line",
        content=body,
        headers={"X-Line-Signature": bad_sig, "Content-Type": "application/json"},
    )

    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_signature"


# ---------------------------------------------------------------------------
# Test 3: duplicate follow event → 200, no duplicate user row
# ---------------------------------------------------------------------------

def test_follow_event_deduplicates_user(client, fake_settings):
    body = _follow_body("Udup999")
    sig = sign(body, fake_settings.line_bot_channel_secret)
    headers = {"X-Line-Signature": sig, "Content-Type": "application/json"}

    # First follow
    resp1 = client.post("/webhook/line", content=body, headers=headers)
    assert resp1.status_code == 200

    # Second follow (same userId)
    resp2 = client.post("/webhook/line", content=body, headers=headers)
    assert resp2.status_code == 200

    with Session(engine) as session:
        users = session.exec(select(User).where(User.line_user_id == "Udup999")).all()
    assert len(users) == 1


# ---------------------------------------------------------------------------
# Test 4: unhandled event type → 200, no DB changes
# ---------------------------------------------------------------------------

def test_unhandled_event_type_returns_ok_no_db_change(client, fake_settings):
    body = _message_body("Umsg456", "hello")
    sig = sign(body, fake_settings.line_bot_channel_secret)

    resp = client.post(
        "/webhook/line",
        content=body,
        headers={"X-Line-Signature": sig, "Content-Type": "application/json"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    with Session(engine) as session:
        user = session.exec(select(User).where(User.line_user_id == "Umsg456")).first()
    assert user is None
