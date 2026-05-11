"""TDD tests for app.auth.line_login — pure functions + httpx wrappers.

Red → Green → Refactor cycle:
  Run tests BEFORE implementing to confirm failures are import-errors / AttributeErrors,
  then implement minimal code to turn each red test green.
"""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx


@pytest.fixture()
def fake_settings(monkeypatch):
    from app.config import Settings

    s = Settings(
        line_login_channel_id="cid",
        line_login_channel_secret="csec",
        line_login_redirect_uri="https://t.tw/auth/callback",
        session_secret="x",
    )
    monkeypatch.setattr("app.auth.line_login.get_settings", lambda: s)
    return s


# ---------------------------------------------------------------------------
# 1. build_authorize_url
# ---------------------------------------------------------------------------


def test_build_authorize_url_contains_required_params(fake_settings):
    from app.auth.line_login import build_authorize_url

    url = build_authorize_url("abc", settings=fake_settings)

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    assert url.startswith("https://access.line.me/oauth2/v2.1/authorize")
    assert qs["client_id"] == ["cid"]
    assert qs["state"] == ["abc"]
    assert qs["redirect_uri"] == ["https://t.tw/auth/callback"]
    assert qs["response_type"] == ["code"]
    # scope may be space-encoded as "profile+openid" or "profile%20openid"
    scope_raw = qs["scope"][0]
    assert "profile" in scope_raw
    assert "openid" in scope_raw


# ---------------------------------------------------------------------------
# 2. exchange_code_for_token
# ---------------------------------------------------------------------------


@respx.mock
def test_exchange_code_for_token_posts_correct_form(fake_settings):
    from app.auth.line_login import LINE_TOKEN_URL, exchange_code_for_token

    route = respx.post(LINE_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "token_type": "Bearer"})
    )

    result = exchange_code_for_token("auth_code", settings=fake_settings)

    assert route.called
    raw = route.calls[0].request.content.decode()
    fields = dict(pair.split("=", 1) for pair in raw.split("&"))

    assert fields["grant_type"] == "authorization_code"
    assert fields["code"] == "auth_code"
    assert "redirect_uri" in fields
    assert fields["client_id"] == "cid"
    assert fields["client_secret"] == "csec"

    assert result == {"access_token": "tok", "token_type": "Bearer"}


@respx.mock
def test_exchange_code_for_token_raises_on_non_2xx(fake_settings):
    from app.auth.line_login import LINE_TOKEN_URL, exchange_code_for_token

    respx.post(LINE_TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "bad"}))

    with pytest.raises(httpx.HTTPStatusError):
        exchange_code_for_token("bad_code", settings=fake_settings)


# ---------------------------------------------------------------------------
# 3. fetch_profile
# ---------------------------------------------------------------------------


@respx.mock
def test_fetch_profile_sends_bearer_and_returns_json(fake_settings):
    from app.auth.line_login import LINE_PROFILE_URL, fetch_profile

    respx.get(LINE_PROFILE_URL).mock(
        return_value=httpx.Response(
            200, json={"userId": "U123", "displayName": "Alice"}
        )
    )

    result = fetch_profile("tok")

    assert result == {"userId": "U123", "displayName": "Alice"}

    # Verify Authorization header was sent
    req = respx.calls[0].request
    assert req.headers["authorization"] == "Bearer tok"


# ---------------------------------------------------------------------------
# 4. upsert_user_from_line_profile — create + update idempotency
# ---------------------------------------------------------------------------


def test_upsert_creates_new_user():
    from app.auth.line_login import upsert_user_from_line_profile
    from app.db import get_session
    from app.models.user import User
    from sqlmodel import select

    profile = {"userId": "U999", "displayName": "Bob"}
    user = upsert_user_from_line_profile(profile)

    assert user.id is not None
    assert user.line_user_id == "U999"
    assert user.display_name == "Bob"

    # Verify it's persisted
    with get_session() as sess:
        db_user = sess.exec(select(User).where(User.line_user_id == "U999")).first()
    assert db_user is not None
    assert db_user.display_name == "Bob"


def test_upsert_updates_display_name_on_second_call():
    from app.auth.line_login import upsert_user_from_line_profile

    profile = {"userId": "U999", "displayName": "Bob"}
    user1 = upsert_user_from_line_profile(profile)

    profile2 = {"userId": "U999", "displayName": "Robert"}
    user2 = upsert_user_from_line_profile(profile2)

    # Same row (same primary key)
    assert user1.id == user2.id
    assert user2.display_name == "Robert"
