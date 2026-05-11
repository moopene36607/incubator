"""LINE Messaging API push helpers.

push_text     — low-level: POST to LINE push endpoint
push_match_alert — high-level: render + push only when matches qualify (score >= 70)
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import Settings, get_settings
from app.notify.renderer import LINE_ALERT_THRESHOLD, render_line_alert

log = structlog.get_logger(__name__)

_LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def push_text(
    line_user_id: str,
    text: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """POST a single text message to a LINE user.

    Returns the parsed JSON response body.
    Raises httpx.HTTPStatusError on any non-2xx response.
    """
    s = settings or get_settings()
    payload = {
        "to": line_user_id,
        "messages": [{"type": "text", "text": text}],
    }
    headers = {
        "Authorization": f"Bearer {s.line_bot_channel_access_token}",
        "Content-Type": "application/json",
    }
    with httpx.Client() as client:
        resp = client.post(_LINE_PUSH_URL, json=payload, headers=headers)
    resp.raise_for_status()
    log.info("line_push_sent", line_user_id=line_user_id, chars=len(text))
    return resp.json()


def push_match_alert(
    line_user_id: str,
    profile: dict[str, Any],
    matches: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    """Build a LINE alert from matches and push it.

    Returns None (without calling LINE) when no match qualifies (llm_score < 70).
    Otherwise returns the push_text response dict.
    """
    high = [m for m in matches if (m.get("llm_score") or 0) >= LINE_ALERT_THRESHOLD]
    if not high:
        log.info("line_push_skipped_no_qualifying_matches", line_user_id=line_user_id)
        return None

    text = render_line_alert(profile, scored_matches=matches)
    return push_text(line_user_id, text, settings=settings)
