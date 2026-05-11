"""LINE webhook receiver.

POST /webhook/line
  - Verifies X-Line-Signature (HMAC-SHA256 over raw body, base64-encoded)
  - Handles follow events: upsert User row with line_user_id
  - All other event types are acknowledged silently
"""

from __future__ import annotations

import base64
import hashlib
import hmac

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine
from app.models.user import User

log = structlog.get_logger(__name__)

router = APIRouter()


def _verify_signature(body: bytes, secret: str, header_sig: str) -> bool:
    computed = base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(computed, header_sig)


@router.post("/webhook/line")
async def linebot_webhook(request: Request) -> JSONResponse:
    settings = get_settings()

    raw_body = await request.body()
    sig_header = request.headers.get("X-Line-Signature", "")

    if not _verify_signature(raw_body, settings.line_bot_channel_secret, sig_header):
        log.warning("linebot_invalid_signature")
        return JSONResponse({"error": "invalid_signature"}, status_code=400)

    payload = await request.json()
    events = payload.get("events", [])

    for event in events:
        event_type = event.get("type")
        if event_type == "follow":
            user_id = event["source"]["userId"]
            _upsert_user(user_id)
            log.info("linebot_follow", line_user_id=user_id)
        elif event_type == "unfollow":
            user_id = event["source"].get("userId", "")
            log.info("linebot_unfollow", line_user_id=user_id)
        else:
            log.debug("linebot_event_ignored", event_type=event_type)

    return JSONResponse({"ok": True})


def _upsert_user(line_user_id: str) -> None:
    """Insert User if not already present; no-op if already exists."""
    with Session(engine) as session:
        existing = session.exec(
            select(User).where(User.line_user_id == line_user_id)
        ).first()
        if existing is None:
            user = User(line_user_id=line_user_id, display_name="LINE User")
            session.add(user)
            session.commit()
            log.info("linebot_user_created", line_user_id=line_user_id)
