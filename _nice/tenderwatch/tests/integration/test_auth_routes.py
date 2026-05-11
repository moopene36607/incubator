"""TDD integration tests for app.routes.auth (LINE Login OAuth flow).

We build a minimal FastAPI app that includes ONLY the auth router so tests
are isolated from the main app's lifespan hooks.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings


def _app() -> FastAPI:
    """Minimal app with SessionMiddleware + auth router only."""
    from app.routes import auth

    a = FastAPI()
    a.add_middleware(SessionMiddleware, secret_key=get_settings().session_secret)
    a.include_router(auth.router)
    return a


def _client() -> TestClient:
    return TestClient(_app(), follow_redirects=False)


# ---------------------------------------------------------------------------
# 1. GET /login → 302 to access.line.me + session cookie set
# ---------------------------------------------------------------------------


def test_login_redirects_to_line():
    r = _client().get("/login")
    assert r.status_code == 302
    loc = r.headers["location"]
    assert "access.line.me" in loc


def test_login_sets_oauth_state_in_location():
    r = _client().get("/login")
    loc = r.headers["location"]
    qs = parse_qs(urlparse(loc).query)
    assert "state" in qs
    assert len(qs["state"][0]) > 8  # cryptographically random, not empty


# ---------------------------------------------------------------------------
# 2. GET /auth/callback — mismatched state → 400
# ---------------------------------------------------------------------------


def test_callback_with_wrong_state_returns_400():
    client = _client()
    # Start login to seed session cookie
    client.get("/login")
    # Supply wrong state
    r = client.get("/auth/callback?code=xxx&state=WRONG_STATE")
    assert r.status_code == 400


def test_callback_without_state_in_session_returns_400():
    client = _client()
    # Call callback without ever calling /login (no session state)
    r = client.get("/auth/callback?code=xxx&state=anything")
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 3. GET /auth/callback — happy path
# ---------------------------------------------------------------------------


@respx.mock
def test_callback_happy_path_creates_user_and_redirects_to_onboarding():
    from app.auth.line_login import LINE_PROFILE_URL, LINE_TOKEN_URL
    from app.db import get_session
    from app.models.user import User
    from sqlmodel import select

    # Mock LINE token + profile endpoints
    respx.post(LINE_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "token_type": "Bearer"})
    )
    respx.get(LINE_PROFILE_URL).mock(
        return_value=httpx.Response(
            200, json={"userId": "Uhappy", "displayName": "HappyUser"}
        )
    )

    client = _client()

    # 1. Hit /login — sets oauth_state in session
    login_r = client.get("/login")
    assert login_r.status_code == 302
    loc = login_r.headers["location"]
    state = parse_qs(urlparse(loc).query)["state"][0]

    # 2. Simulate LINE callback with matching state
    r = client.get(f"/auth/callback?code=authcode123&state={state}")
    assert r.status_code == 302
    # No profile rows yet → redirect to /onboarding
    assert r.headers["location"] == "/onboarding"

    # 3. Verify User was persisted
    with get_session() as sess:
        user = sess.exec(select(User).where(User.line_user_id == "Uhappy")).first()
    assert user is not None
    assert user.display_name == "HappyUser"


@respx.mock
def test_callback_redirects_to_app_when_profile_exists():
    from app.auth.line_login import LINE_PROFILE_URL, LINE_TOKEN_URL
    from app.db import get_session
    from app.models.profile import Profile
    from app.models.user import User

    # Pre-create a user + profile so callback sees them
    with get_session() as sess:
        u = User(line_user_id="Uprofile", display_name="WithProfile")
        sess.add(u)
        sess.commit()
        sess.refresh(u)
        p = Profile(
            user_id=u.id,
            company_name="Acme",
            capital_twd=1_000_000,
            employee_count=10,
            capability_description="IT consulting",
        )
        sess.add(p)
        sess.commit()

    respx.post(LINE_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok2", "token_type": "Bearer"})
    )
    respx.get(LINE_PROFILE_URL).mock(
        return_value=httpx.Response(
            200, json={"userId": "Uprofile", "displayName": "WithProfile"}
        )
    )

    client = _client()
    login_r = client.get("/login")
    state = parse_qs(urlparse(login_r.headers["location"]).query)["state"][0]

    r = client.get(f"/auth/callback?code=code2&state={state}")
    assert r.status_code == 302
    assert r.headers["location"] == "/app"


# ---------------------------------------------------------------------------
# 4. POST /logout clears session
# ---------------------------------------------------------------------------


def test_logout_clears_session():
    client = _client()
    r = client.post("/logout")
    assert r.status_code == 302
    assert r.headers["location"] == "/"


@respx.mock
def test_after_logout_callback_rejects_stale_state():
    from app.auth.line_login import LINE_PROFILE_URL, LINE_TOKEN_URL

    respx.post(LINE_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok3", "token_type": "Bearer"})
    )
    respx.get(LINE_PROFILE_URL).mock(
        return_value=httpx.Response(
            200, json={"userId": "Ustale", "displayName": "Stale"}
        )
    )

    client = _client()

    # Login to capture state
    login_r = client.get("/login")
    state = parse_qs(urlparse(login_r.headers["location"]).query)["state"][0]

    # Logout clears session (including oauth_state)
    client.post("/logout")

    # Now attempt callback with the now-stale state
    r = client.get(f"/auth/callback?code=oldcode&state={state}")
    assert r.status_code == 400
