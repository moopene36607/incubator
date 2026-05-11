"""Session-based authentication dependency for FastAPI routes."""

from __future__ import annotations

import structlog
from fastapi import HTTPException, Request

from app.db import get_session
from app.models.user import User

log = structlog.get_logger(__name__)


def require_user(request: Request) -> User:
    """FastAPI dependency — returns the logged-in User or raises 401.

    Reads ``user_id`` from the signed session cookie.  Raises
    ``HTTPException(401)`` if the session has no user_id or the row no
    longer exists in the database.
    """
    user_id = request.session.get("user_id")
    if user_id is None:
        log.info("auth.unauthenticated")
        raise HTTPException(status_code=401, detail="not_logged_in")

    with get_session() as sess:
        user = sess.get(User, user_id)

    if user is None:
        log.warning("auth.user_not_found", user_id=user_id)
        raise HTTPException(status_code=401, detail="not_logged_in")

    return user
