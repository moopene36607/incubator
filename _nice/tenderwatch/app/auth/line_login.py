"""LINE Login OAuth2 helpers — pure functions + thin httpx wrappers.

All network-touching functions accept an optional `settings` kwarg so unit
tests can inject fake credentials without touching the real singleton.
"""

from __future__ import annotations

import urllib.parse

import httpx
import structlog

from app.config import get_settings
from app.db import get_session
from app.models.user import User

log = structlog.get_logger(__name__)

LINE_AUTHORIZE_URL = "https://access.line.me/oauth2/v2.1/authorize"
LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
LINE_PROFILE_URL = "https://api.line.me/v2/profile"


def build_authorize_url(state: str, *, settings=None) -> str:
    """Return the LINE OAuth2 authorization URL for the given CSRF state."""
    if settings is None:
        settings = get_settings()

    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": settings.line_login_channel_id,
            "redirect_uri": settings.line_login_redirect_uri,
            "scope": "profile openid",
            "state": state,
        }
    )
    return f"{LINE_AUTHORIZE_URL}?{params}"


def exchange_code_for_token(code: str, *, settings=None) -> dict:
    """POST to LINE token endpoint; return parsed JSON.

    Raises `httpx.HTTPStatusError` on non-2xx responses.
    """
    if settings is None:
        settings = get_settings()

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.line_login_redirect_uri,
        "client_id": settings.line_login_channel_id,
        "client_secret": settings.line_login_channel_secret,
    }

    with httpx.Client() as client:
        resp = client.post(LINE_TOKEN_URL, data=data)
        resp.raise_for_status()
        return resp.json()


def fetch_profile(access_token: str) -> dict:
    """GET the LINE user profile using Bearer token.

    Returns dict with at minimum ``userId`` and ``displayName``.
    """
    with httpx.Client() as client:
        resp = client.get(
            LINE_PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


def upsert_user_from_line_profile(profile: dict, *, settings=None) -> User:
    """Insert-or-update a User row from a LINE profile dict.

    Looks up by ``profile["userId"]``. If the row already exists, updates
    ``display_name``. Commits and returns the refreshed User instance.
    """
    from sqlmodel import select

    line_user_id: str = profile["userId"]
    display_name: str = profile["displayName"]

    with get_session() as sess:
        existing = sess.exec(
            select(User).where(User.line_user_id == line_user_id)
        ).first()

        if existing:
            existing.display_name = display_name
            sess.add(existing)
            sess.commit()
            sess.refresh(existing)
            log.info("user.updated", line_user_id=line_user_id)
            return existing
        else:
            user = User(line_user_id=line_user_id, display_name=display_name)
            sess.add(user)
            sess.commit()
            sess.refresh(user)
            log.info("user.created", line_user_id=line_user_id)
            return user
