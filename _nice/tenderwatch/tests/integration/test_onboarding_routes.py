"""TDD integration tests for app.routes.onboarding."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import engine
from app.models.user import User


def _app_with_user(user: User) -> FastAPI:
    from app.routes import onboarding
    from app.auth.session import require_user

    a = FastAPI()
    a.add_middleware(SessionMiddleware, secret_key=get_settings().session_secret)
    a.include_router(onboarding.router)
    a.dependency_overrides[require_user] = lambda: user
    return a


def _app_no_auth() -> FastAPI:
    """App without dependency override — require_user raises 401."""
    from app.routes import onboarding

    a = FastAPI()
    a.add_middleware(SessionMiddleware, secret_key=get_settings().session_secret)
    a.include_router(onboarding.router)
    return a


@pytest.fixture()
def logged_in_user() -> User:
    with Session(engine) as s:
        u = User(line_user_id="U1", display_name="Test")
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


# ---------------------------------------------------------------------------
# 1. GET /onboarding without login → 401
# ---------------------------------------------------------------------------


def test_get_onboarding_without_login_returns_401():
    client = TestClient(_app_no_auth(), follow_redirects=False)
    r = client.get("/onboarding")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 2. GET /onboarding with logged-in user (no profile) → 200 + form
# ---------------------------------------------------------------------------


def test_get_onboarding_with_user_no_profile_returns_form(logged_in_user):
    client = TestClient(_app_with_user(logged_in_user), follow_redirects=False)
    r = client.get("/onboarding")
    assert r.status_code == 200
    body = r.text
    assert "form" in body.lower()
    assert 'action="/onboarding"' in body
    assert 'name="company_name"' in body


# ---------------------------------------------------------------------------
# 3. GET /onboarding with user that HAS a profile → 302 to /app/today
# ---------------------------------------------------------------------------


def test_get_onboarding_with_profile_redirects_to_today(logged_in_user):
    from app.models.profile import Profile

    with Session(engine) as s:
        p = Profile(
            user_id=logged_in_user.id,
            company_name="Acme",
            capital_twd=1_000_000,
            employee_count=10,
            capability_description="IT consulting",
        )
        s.add(p)
        s.commit()

    client = TestClient(_app_with_user(logged_in_user), follow_redirects=False)
    r = client.get("/onboarding")
    assert r.status_code == 302
    assert r.headers["location"] == "/app/today"


# ---------------------------------------------------------------------------
# 4. POST /onboarding with valid form → creates Profile, redirects to /app/today
# ---------------------------------------------------------------------------


def test_post_onboarding_creates_profile_and_redirects(logged_in_user):
    from app.models.profile import Profile
    from sqlmodel import select

    client = TestClient(_app_with_user(logged_in_user), follow_redirects=False)
    r = client.post(
        "/onboarding",
        data={
            "company_name": "TechCorp",
            "capital_twd": "5000000",
            "employee_count": "25",
            "capability_description": "雲端遷移、HIS 介接",
            "min_tender_budget_twd": "200000",
            "max_tender_budget_twd": "5000000",
            "excluded_categories": "印刷, 工程",
            "iso_certifications": "ISO 27001",
            "minimum_days_to_deadline": "10",
        },
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/app/today"

    with Session(engine) as s:
        profile = s.exec(
            select(Profile).where(Profile.user_id == logged_in_user.id)
        ).first()
    assert profile is not None
    assert profile.company_name == "TechCorp"
    assert profile.capital_twd == 5_000_000
    assert profile.employee_count == 25


# ---------------------------------------------------------------------------
# 5. POST /onboarding parses comma-separated excluded_categories correctly
# ---------------------------------------------------------------------------


def test_post_onboarding_parses_excluded_categories(logged_in_user):
    from app.models.profile import Profile
    from sqlmodel import select

    client = TestClient(_app_with_user(logged_in_user), follow_redirects=False)
    client.post(
        "/onboarding",
        data={
            "company_name": "Corp",
            "capital_twd": "1000000",
            "employee_count": "5",
            "capability_description": "軟體開發",
            "min_tender_budget_twd": "100000",
            "excluded_categories": "印刷, 工程, 餐飲",
            "iso_certifications": "",
            "minimum_days_to_deadline": "7",
        },
    )

    with Session(engine) as s:
        profile = s.exec(
            select(Profile).where(Profile.user_id == logged_in_user.id)
        ).first()

    assert profile is not None
    assert profile.excluded_categories == ["印刷", "工程", "餐飲"]
