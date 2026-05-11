"""Integration tests for GET /billing/checkout and POST /billing/cancel.

TDD: tests written first (RED), then implementation makes them GREEN.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import select
from starlette.middleware.sessions import SessionMiddleware

from app.auth.session import require_user
from app.config import get_settings
from app.models.user import User


# ---------------------------------------------------------------------------
# Minimal app factory
# ---------------------------------------------------------------------------


def _make_user() -> User:
    from app.db import get_session

    with get_session() as sess:
        u = User(line_user_id="Ubilling1", display_name="Billing User")
        sess.add(u)
        sess.commit()
        sess.refresh(u)
        return u


def _app(fake_user: User | None = None) -> FastAPI:
    from app.routes import billing

    a = FastAPI()
    a.add_middleware(SessionMiddleware, secret_key=get_settings().session_secret)
    a.include_router(billing.router)

    if fake_user is not None:
        a.dependency_overrides[require_user] = lambda: fake_user

    return a


def _client(fake_user: User | None = None) -> TestClient:
    return TestClient(_app(fake_user), follow_redirects=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_ecpay_settings(monkeypatch):
    monkeypatch.setenv("ECPAY_HASH_KEY", "5294y06JbISpM5x9")
    monkeypatch.setenv("ECPAY_HASH_IV", "v77hoKGq4kWxNNIS")
    monkeypatch.setenv("ECPAY_MERCHANT_ID", "2000132")
    monkeypatch.setenv("ECPAY_RETURN_URL", "https://example.com/webhook/ecpay")
    monkeypatch.setenv("ECPAY_CLIENT_BACK_URL", "https://example.com/app/billing")


# ---------------------------------------------------------------------------
# GET /billing/checkout
# ---------------------------------------------------------------------------


def test_checkout_solo_logged_in_renders_form():
    """GET /billing/checkout?plan=solo returns 200 HTML with hidden form fields."""
    user = _make_user()
    client = _client(fake_user=user)

    r = client.get("/billing/checkout?plan=solo")
    assert r.status_code == 200
    assert "TotalAmount" in r.text
    assert "799" in r.text
    assert "CheckMacValue" in r.text


def test_checkout_solo_inserts_pending_subscription():
    """A pending Subscription row is inserted when checkout is called."""
    from app.db import get_session
    from app.models.subscription import Subscription

    user = _make_user()
    client = _client(fake_user=user)

    client.get("/billing/checkout?plan=solo")

    with get_session() as sess:
        subs = sess.exec(
            select(Subscription).where(Subscription.user_id == user.id)
        ).all()
    assert len(subs) == 1
    assert subs[0].status == "pending"
    assert subs[0].plan == "solo"
    assert subs[0].ecpay_period_amount == 799


def test_checkout_invalid_plan_returns_400():
    """GET /billing/checkout?plan=invalid → 400."""
    user = _make_user()
    client = _client(fake_user=user)

    r = client.get("/billing/checkout?plan=invalid")
    assert r.status_code == 400


def test_checkout_without_login_returns_401():
    """GET /billing/checkout without login → 401."""
    # No fake_user override → require_user raises 401
    client = _client(fake_user=None)
    r = client.get("/billing/checkout?plan=solo")
    assert r.status_code == 401


def test_checkout_pro_amounts():
    """GET /billing/checkout?plan=pro returns 2500 in body."""
    user = _make_user()
    client = _client(fake_user=user)

    r = client.get("/billing/checkout?plan=pro")
    assert r.status_code == 200
    assert "2500" in r.text


# ---------------------------------------------------------------------------
# POST /billing/cancel
# ---------------------------------------------------------------------------


def _seed_active_subscription(user_id: int) -> int:
    """Create an active subscription for the user. Returns sub id."""
    from app.db import get_session
    from app.models.subscription import Subscription

    with get_session() as sess:
        sub = Subscription(
            user_id=user_id,
            plan="solo",
            ecpay_merchant_trade_no=f"TWCANCEL{user_id}",
            ecpay_period_amount=799,
            status="active",
        )
        sess.add(sub)
        sess.commit()
        sess.refresh(sub)
        return sub.id


def test_cancel_logged_in_redirects_and_sets_cancelled():
    """POST /billing/cancel (logged in, active sub) → redirect, status=cancelled."""
    from app.db import get_session
    from app.models.subscription import Subscription

    user = _make_user()
    sub_id = _seed_active_subscription(user.id)

    client = _client(fake_user=user)
    r = client.post("/billing/cancel")

    assert r.status_code in (302, 303)
    assert "/app/billing" in r.headers["location"]

    with get_session() as sess:
        sub = sess.get(Subscription, sub_id)
        assert sub.status == "cancelled"
        assert sub.cancelled_at is not None


def test_cancel_without_login_returns_401():
    """POST /billing/cancel without login → 401."""
    client = _client(fake_user=None)
    r = client.post("/billing/cancel")
    assert r.status_code == 401
