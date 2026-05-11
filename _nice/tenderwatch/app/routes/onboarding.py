"""Onboarding routes — wizard + done."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import select

from app.auth.session import require_user
from app.db import get_session
from app.models.profile import Profile
from app.models.user import User
from app.templates_env import templates

log = structlog.get_logger(__name__)

router = APIRouter()


def _parse_csv(value: str) -> list[str]:
    """Split comma-separated string into a trimmed, non-empty list."""
    return [item.strip() for item in value.split(",") if item.strip()]


@router.get("/onboarding")
def get_onboarding(request: Request, user: User = Depends(require_user)):
    with get_session() as s:
        existing = s.exec(
            select(Profile).where(Profile.user_id == user.id)
        ).first()

    if existing is not None:
        log.info("onboarding.already_has_profile", user_id=user.id)
        return RedirectResponse(url="/app/today", status_code=302)

    return templates.TemplateResponse(
        request, "onboarding/wizard.html", {"user": user}
    )


@router.post("/onboarding")
def post_onboarding(
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

    profile = Profile(
        user_id=user.id,
        company_name=company_name,
        capital_twd=capital_twd,
        employee_count=employee_count,
        capability_description=capability_description,
        min_tender_budget_twd=min_tender_budget_twd,
        max_tender_budget_twd=max_budget,
        excluded_categories=_parse_csv(excluded_categories),
        iso_certifications=_parse_csv(iso_certifications),
        minimum_days_to_deadline=minimum_days_to_deadline,
    )

    with get_session() as s:
        s.add(profile)
        s.commit()

    log.info("onboarding.profile_created", user_id=user.id)
    return RedirectResponse(url="/app/today", status_code=302)
