"""Daily email digest via Resend.

Pure-function builder (build_digest) + thin IO wrapper (send_daily_digest).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_FROM = "tenderwatch <hi@tenderwatch.tw>"
_HIGHLIGHT_THRESHOLD = 85


def _fmt_budget(budget: int) -> str:
    return f"NT${budget:,}"


def _html_row(m: dict[str, Any]) -> str:
    score: int = m.get("llm_score") or 0
    highlight = score >= _HIGHLIGHT_THRESHOLD
    style = (
        'style="font-weight:bold;color:#b91c1c;"'
        if highlight
        else 'style="color:#374151;"'
    )
    return (
        f"<tr>"
        f'<td style="padding:6px 10px;border:1px solid #e5e7eb;">{m.get("case_no","")}</td>'
        f'<td style="padding:6px 10px;border:1px solid #e5e7eb;">{m.get("title","")}</td>'
        f'<td style="padding:6px 10px;border:1px solid #e5e7eb;">{m.get("agency","")}</td>'
        f'<td style="padding:6px 10px;border:1px solid #e5e7eb;">{_fmt_budget(m.get("budget_twd") or 0)}</td>'
        f'<td style="padding:6px 10px;border:1px solid #e5e7eb;">{m.get("deadline_date","")}</td>'
        f'<td style="padding:6px 10px;border:1px solid #e5e7eb;" {style}>{score}</td>'
        f'<td style="padding:6px 10px;border:1px solid #e5e7eb;">{m.get("llm_recommendation","")}</td>'
        f"</tr>"
    )


def _build_html(matches: list[dict[str, Any]], today: date) -> str:
    rows = "\n".join(_html_row(m) for m in matches)
    table = (
        '<table style="border-collapse:collapse;width:100%;font-family:sans-serif;font-size:14px;">'
        "<thead>"
        "<tr>"
        + "".join(
            f'<th style="padding:8px 10px;border:1px solid #e5e7eb;background:#f9fafb;text-align:left;">{h}</th>'
            for h in ["案號", "標題", "機關", "預算", "截止", "分數", "建議"]
        )
        + "</tr>"
        "</thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    )
    return (
        "<!DOCTYPE html><html><body>"
        f'<h2 style="font-family:sans-serif;">tenderwatch 今日標案摘要 — {today}</h2>'
        + table
        + f'<p style="font-family:sans-serif;font-size:12px;color:#9ca3af;">由 tenderwatch 自動產生，分數 ≥ {_HIGHLIGHT_THRESHOLD} 以粗體紅字標示。</p>'
        "</body></html>"
    )


def _build_text(matches: list[dict[str, Any]], today: date) -> str:
    lines = [f"tenderwatch 今日標案摘要 — {today}", ""]
    for m in matches:
        score = m.get("llm_score") or 0
        case_no = m.get("case_no", "")
        title = m.get("title", "")
        deadline = m.get("deadline_date", "")
        lines.append(f"[{score}] {case_no} — {title} (截止 {deadline})")
    if not matches:
        lines.append("（今日無高匹配標案）")
    return "\n".join(lines)


def build_digest(user_email: str, matches: list[dict], today: date) -> dict:
    """Build the Resend payload — pure function, no IO.

    Returns:
        {
          "from": "tenderwatch <hi@tenderwatch.tw>",
          "to": [user_email],
          "subject": "tenderwatch — 今日高匹配標案 N 件 (YYYY-MM-DD)",
          "html": "<html>...</html>",
          "text": "...",
        }
    """
    n = len(matches)
    date_str = today.strftime("%Y-%m-%d")
    return {
        "from": _FROM,
        "to": [user_email],
        "subject": f"tenderwatch — 今日高匹配標案 {n} 件 ({date_str})",
        "html": _build_html(matches, today),
        "text": _build_text(matches, today),
    }


def send_daily_digest(
    user_email: str,
    matches: list[dict],
    today: date,
    *,
    settings: Any = None,
) -> dict | None:
    """Call resend.Emails.send with the build_digest payload.

    Returns Resend's response dict (containing 'id').
    No-op (returns None) if matches is empty or user_email is empty.
    """
    if not matches or not user_email:
        log.info("email_digest.skip", reason="no_matches_or_email", email=user_email)
        return None

    if settings is None:
        from app.config import get_settings
        settings = get_settings()

    import resend

    resend.api_key = settings.resend_api_key

    payload = build_digest(user_email, matches, today)
    log.info("email_digest.send", to=user_email, count=len(matches), date=str(today))
    return resend.Emails.send(payload)
