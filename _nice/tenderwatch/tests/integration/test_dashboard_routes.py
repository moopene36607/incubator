"""TDD integration tests for app.routes.dashboard."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import engine
from app.models.user import User


def _app_with_user(user: User) -> FastAPI:
    from app.routes import dashboard
    from app.auth.session import require_user

    a = FastAPI()
    a.add_middleware(SessionMiddleware, secret_key=get_settings().session_secret)
    a.include_router(dashboard.router)
    a.dependency_overrides[require_user] = lambda: user
    return a


@pytest.fixture()
def user() -> User:
    with Session(engine) as s:
        u = User(line_user_id="U_dash", display_name="Dash User")
        s.add(u)
        s.commit()
        s.refresh(u)
        return u


@pytest.fixture()
def user_with_profile(user: User):
    from app.models.profile import Profile

    with Session(engine) as s:
        p = Profile(
            user_id=user.id,
            company_name="Acme IT",
            capital_twd=3_000_000,
            employee_count=15,
            capability_description="雲端服務",
        )
        s.add(p)
        s.commit()
        s.refresh(p)
    return user, p


def _seed_tender(case_no: str, title: str = "Test Tender") -> None:
    from app.models.tender import Tender

    with Session(engine) as s:
        t = Tender(
            case_no=case_no,
            title=title,
            agency="台北市政府",
            category="資訊",
            budget_twd=1_000_000,
            posted_date=date.today(),
            deadline_date=date.today() + timedelta(days=30),
        )
        s.add(t)
        s.commit()


def _seed_match(
    user_id: int,
    profile_id: int,
    case_no: str,
    llm_score: int = 85,
    created_at: datetime | None = None,
    passes_hard_filter: bool = True,
):
    from app.models.match import Match

    with Session(engine) as s:
        m = Match(
            user_id=user_id,
            profile_id=profile_id,
            tender_case_no=case_no,
            passes_hard_filter=passes_hard_filter,
            llm_score=llm_score,
            llm_recommendation="建議投標",
            created_at=created_at or datetime.utcnow(),
        )
        s.add(m)
        s.commit()


# ---------------------------------------------------------------------------
# 1. GET /app redirects to /app/today
# ---------------------------------------------------------------------------


def test_get_app_redirects_to_today(user):
    client = TestClient(_app_with_user(user), follow_redirects=False)
    r = client.get("/app")
    assert r.status_code == 302
    assert r.headers["location"] == "/app/today"


# ---------------------------------------------------------------------------
# 2. GET /app/today with no matches → 200 + "今日無高匹配標案"
# ---------------------------------------------------------------------------


def test_get_today_with_no_matches_shows_empty_message(user):
    client = TestClient(_app_with_user(user), follow_redirects=False)
    r = client.get("/app/today")
    assert r.status_code == 200
    assert "今日無高匹配標案" in r.text


# ---------------------------------------------------------------------------
# 3. GET /app/today with high-score match seeded → 200 + case_no visible
# ---------------------------------------------------------------------------


def test_get_today_with_high_score_match_shows_case(user_with_profile):
    user, profile = user_with_profile
    _seed_tender("CASE-001", "政府雲端標案")
    _seed_match(user.id, profile.id, "CASE-001", llm_score=85)

    client = TestClient(_app_with_user(user), follow_redirects=False)
    r = client.get("/app/today")
    assert r.status_code == 200
    assert "CASE-001" in r.text
    assert "85" in r.text


# ---------------------------------------------------------------------------
# 4. GET /app/today filters out low-score matches (score=50 should NOT appear)
# ---------------------------------------------------------------------------


def test_get_today_filters_low_score_matches(user_with_profile):
    user, profile = user_with_profile
    _seed_tender("CASE-LOW", "低分標案")
    _seed_match(user.id, profile.id, "CASE-LOW", llm_score=50)

    client = TestClient(_app_with_user(user), follow_redirects=False)
    r = client.get("/app/today")
    assert r.status_code == 200
    assert "CASE-LOW" not in r.text
    assert "今日無高匹配標案" in r.text


# ---------------------------------------------------------------------------
# 5. GET /app/history with seeded matches in last 30 days → 200, contains them
# ---------------------------------------------------------------------------


def test_get_history_shows_recent_matches(user_with_profile):
    user, profile = user_with_profile
    _seed_tender("HIST-001", "歷史標案")
    past = datetime.utcnow() - timedelta(days=15)
    _seed_match(user.id, profile.id, "HIST-001", llm_score=80, created_at=past)

    client = TestClient(_app_with_user(user), follow_redirects=False)
    r = client.get("/app/history")
    assert r.status_code == 200
    assert "HIST-001" in r.text


# ---------------------------------------------------------------------------
# 6. GET /app/profile with no profile → 302 to /onboarding
# ---------------------------------------------------------------------------


def test_get_profile_without_profile_redirects_to_onboarding(user):
    client = TestClient(_app_with_user(user), follow_redirects=False)
    r = client.get("/app/profile")
    assert r.status_code == 302
    assert r.headers["location"] == "/onboarding"


# ---------------------------------------------------------------------------
# 7. GET /app/profile with profile → 200, form pre-filled with company_name
# ---------------------------------------------------------------------------


def test_get_profile_with_profile_shows_form(user_with_profile):
    user, profile = user_with_profile
    client = TestClient(_app_with_user(user), follow_redirects=False)
    r = client.get("/app/profile")
    assert r.status_code == 200
    assert "Acme IT" in r.text
    assert 'name="company_name"' in r.text


# ---------------------------------------------------------------------------
# 8. POST /app/profile updates existing profile + resets embedding to None
# ---------------------------------------------------------------------------


def test_post_profile_updates_and_resets_embedding(user_with_profile):
    from app.models.profile import Profile
    from sqlmodel import select

    user, profile = user_with_profile

    # Give the profile an embedding so we can verify reset
    with Session(engine) as s:
        p = s.get(Profile, profile.id)
        p.embedding = [0.1, 0.2, 0.3]
        s.add(p)
        s.commit()

    client = TestClient(_app_with_user(user), follow_redirects=False)
    r = client.post(
        "/app/profile",
        data={
            "company_name": "Updated Corp",
            "capital_twd": "8000000",
            "employee_count": "30",
            "capability_description": "資安顧問",
            "min_tender_budget_twd": "300000",
            "max_tender_budget_twd": "",
            "excluded_categories": "印刷",
            "iso_certifications": "ISO 27001, ISO 9001",
            "minimum_days_to_deadline": "14",
        },
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/app/profile"

    with Session(engine) as s:
        p = s.exec(select(Profile).where(Profile.user_id == user.id)).first()
    assert p.company_name == "Updated Corp"
    assert p.capital_twd == 8_000_000
    assert p.embedding is None
    assert p.iso_certifications == ["ISO 27001", "ISO 9001"]


# ---------------------------------------------------------------------------
# 9. GET /app/billing with no subscription → 200 + "免費方案"
# ---------------------------------------------------------------------------


def test_get_billing_with_no_subscription(user):
    client = TestClient(_app_with_user(user), follow_redirects=False)
    r = client.get("/app/billing")
    assert r.status_code == 200
    assert "免費方案" in r.text


# ---------------------------------------------------------------------------
# 10. GET /app/billing with active subscription → 200 + plan name visible
# ---------------------------------------------------------------------------


def test_get_billing_with_active_subscription(user):
    from app.models.subscription import Subscription

    with Session(engine) as s:
        sub = Subscription(
            user_id=user.id,
            plan="solo",
            ecpay_merchant_trade_no="TW20240101001",
            ecpay_period_amount=799,
            status="active",
            next_charge_at=datetime(2026, 6, 1),
        )
        s.add(sub)
        s.commit()

    client = TestClient(_app_with_user(user), follow_redirects=False)
    r = client.get("/app/billing")
    assert r.status_code == 200
    assert "solo" in r.text
