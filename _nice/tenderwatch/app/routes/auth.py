"""LINE Login OAuth2 routes.

GET  /login          — start OAuth flow; redirects to LINE
GET  /auth/callback  — LINE returns here with code + state
POST /logout         — clear session; redirect to /
"""

from __future__ import annotations

import secrets

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth.line_login import (
    build_authorize_url,
    exchange_code_for_token,
    fetch_profile,
    upsert_user_from_line_profile,
)

log = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/login")
def login(request: Request) -> RedirectResponse:
    """Generate a CSRF state token, store in session, redirect to LINE."""
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    authorize_url = build_authorize_url(state)
    log.info("auth.login_started")
    return RedirectResponse(url=authorize_url, status_code=302)


@router.get("/auth/callback")
def callback(code: str, state: str, request: Request) -> RedirectResponse:
    """Handle the LINE OAuth callback.

    Validates CSRF state, exchanges the code for a token, fetches the LINE
    profile, upserts the User row, stores user_id in session, then routes to
    /onboarding (no profile yet) or /app (profile exists).
    """
    expected_state = request.session.get("oauth_state")
    if not expected_state or state != expected_state:
        log.warning("auth.state_mismatch", received=state)
        raise HTTPException(status_code=400, detail="invalid_state")

    # Exchange code for access token
    token_data = exchange_code_for_token(code)
    access_token: str = token_data["access_token"]

    # Fetch LINE profile
    profile = fetch_profile(access_token)

    # Persist user
    user = upsert_user_from_line_profile(profile)

    # Store user_id in session; clear oauth_state
    request.session["user_id"] = user.id
    request.session.pop("oauth_state", None)

    log.info("auth.callback_success", user_id=user.id)

    # Determine redirect destination
    from app.db import get_session
    from app.models.profile import Profile
    from sqlmodel import select

    with get_session() as sess:
        has_profile = sess.exec(
            select(Profile).where(Profile.user_id == user.id)
        ).first() is not None

    dest = "/app" if has_profile else "/onboarding"
    return RedirectResponse(url=dest, status_code=302)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    """Clear session and redirect to landing page."""
    request.session.clear()
    log.info("auth.logout")
    return RedirectResponse(url="/", status_code=302)
