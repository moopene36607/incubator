"""Dashboard routes — today, history, profile, billing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import select

from app.auth.session import require_user
from app.db import get_session
from app.models.match import Match
from app.models.profile import Profile
from app.models.subscription import Subscription
from app.models.tender import Tender
from app.models.user import User
from app.templates_env import templates

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/app")

_MIN_LLM_SCORE = 70


@dataclass
class MatchRow:
    match: Match
    tender: Tender


def _parse_csv(value: str) -> list[str]:
    """Split comma-separated string into a trimmed, non-empty list."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _load_matches(user_id: int, since: datetime) -> list[MatchRow]:
    """Load high-score matches for a user since a given UTC datetime."""
    with get_session() as s:
        matches = s.exec(
            select(Match).where(
                Match.user_id == user_id,
                Match.created_at >= since,
                Match.passes_hard_filter == True,  # noqa: E712
                Match.llm_score >= _MIN_LLM_SCORE,
            )
        ).all()

        rows: list[MatchRow] = []
        for m in matches:
            tender = s.get(Tender, m.tender_case_no)
            if tender is not None:
                rows.append(MatchRow(match=m, tender=tender))
    return rows


# ---------------------------------------------------------------------------
# GET /app → redirect to /app/today
# ---------------------------------------------------------------------------


@router.get("")
def get_app_root():
    return RedirectResponse(url="/app/today", status_code=302)


# ---------------------------------------------------------------------------
# GET /app/today
# ---------------------------------------------------------------------------


@router.get("/today")
def get_today(request: Request, user: User = Depends(require_user)):
    today = date.today()
    today_midnight = datetime.combine(today, datetime.min.time())
    matches = _load_matches(user.id, since=today_midnight)

    return templates.TemplateResponse(
        request, "dashboard/today.html", {"user": user, "matches": matches, "today": today}
    )


# ---------------------------------------------------------------------------
# GET /app/history
# ---------------------------------------------------------------------------


@router.get("/history")
def get_history(request: Request, user: User = Depends(require_user)):
    since = datetime.now(UTC) - timedelta(days=30)
    matches = _load_matches(user.id, since=since)

    return templates.TemplateResponse(
        request, "dashboard/history.html", {"user": user, "matches": matches}
    )


# ---------------------------------------------------------------------------
# GET /app/profile
# ---------------------------------------------------------------------------


@router.get("/profile")
def get_profile(request: Request, user: User = Depends(require_user)):
    with get_session() as s:
        profile = s.exec(
            select(Profile).where(Profile.user_id == user.id)
        ).first()

    if profile is None:
        return RedirectResponse(url="/onboarding", status_code=302)

    return templates.TemplateResponse(
        request, "dashboard/profile_edit.html", {"user": user, "profile": profile}
    )


# ---------------------------------------------------------------------------
# POST /app/profile
# ---------------------------------------------------------------------------


@router.post("/profile")
def post_profile(
    request: Request,
    user: User = Depends(require_user),
    company_name: str = Form(...),
    capital_twd: int = Form(...),
    employee_count: int = Form(...),
    capability_description: str = Form(...),
    min_tender_budget_twd: int = Form(100_000),
    max_tender_budget_twd: str = Form(""),
    excluded_categories: str = Form(""),
    iso_certifications: str = Form(""),
    minimum_days_to_deadline: int = Form(7),
):
    max_budget: int | None = None
    if max_tender_budget_twd.strip():
        max_budget = int(max_tender_budget_twd.strip())

    with get_session() as s:
        profile = s.exec(
            select(Profile).where(Profile.user_id == user.id)
        ).first()

        if profile is None:
            log.warning("dashboard.profile_not_found", user_id=user.id)
            return RedirectResponse(url="/onboarding", status_code=302)

        profile.company_name = company_name
        profile.capital_twd = capital_twd
        profile.employee_count = employee_count
        profile.capability_description = capability_description
        profile.min_tender_budget_twd = min_tender_budget_twd
        profile.max_tender_budget_twd = max_budget
        profile.excluded_categories = _parse_csv(excluded_categories)
        profile.iso_certifications = _parse_csv(iso_certifications)
        profile.minimum_days_to_deadline = minimum_days_to_deadline
        profile.embedding = None  # force re-embed on next ingest run
        profile.updated_at = datetime.now(UTC)

        s.add(profile)
        s.commit()

    log.info("dashboard.profile_updated", user_id=user.id)
    return RedirectResponse(url="/app/profile", status_code=302)


# ---------------------------------------------------------------------------
# GET /app/billing
# ---------------------------------------------------------------------------


@router.get("/billing")
def get_billing(request: Request, user: User = Depends(require_user)):
    with get_session() as s:
        subscription = s.exec(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.created_at.desc())
        ).first()

    return templates.TemplateResponse(
        request, "dashboard/billing.html", {"user": user, "subscription": subscription}
    )
