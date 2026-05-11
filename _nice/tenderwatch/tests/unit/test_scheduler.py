"""Tests for app/workers/scheduler.py

TDD — written before the implementation exists.
"""
from __future__ import annotations

from datetime import date

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


# ---------------------------------------------------------------------------
# 1. start_scheduler(start=False) returns AsyncIOScheduler with 4 jobs
# ---------------------------------------------------------------------------

def test_start_scheduler_returns_async_io_scheduler():
    from app.workers.scheduler import start_scheduler

    sched = start_scheduler(start=False)
    assert isinstance(sched, AsyncIOScheduler)
    sched.shutdown(wait=False) if sched.running else None


def test_start_scheduler_registers_four_jobs():
    from app.workers.scheduler import start_scheduler

    sched = start_scheduler(start=False)
    job_ids = {j.id for j in sched.get_jobs()}
    assert job_ids == {"ingest_morning", "ingest_afternoon", "push_morning", "email_morning"}


# ---------------------------------------------------------------------------
# 2. Each job has a CronTrigger with expected hour/minute
# ---------------------------------------------------------------------------

def _get_job(sched: AsyncIOScheduler, job_id: str):
    return next(j for j in sched.get_jobs() if j.id == job_id)


def test_ingest_morning_trigger():
    from app.workers.scheduler import start_scheduler

    sched = start_scheduler(start=False)
    job = _get_job(sched, "ingest_morning")
    assert isinstance(job.trigger, CronTrigger)
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "6"
    assert fields["minute"] == "0"


def test_ingest_afternoon_trigger():
    from app.workers.scheduler import start_scheduler

    sched = start_scheduler(start=False)
    job = _get_job(sched, "ingest_afternoon")
    assert isinstance(job.trigger, CronTrigger)
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "14"
    assert fields["minute"] == "0"


def test_push_morning_trigger():
    from app.workers.scheduler import start_scheduler

    sched = start_scheduler(start=False)
    job = _get_job(sched, "push_morning")
    assert isinstance(job.trigger, CronTrigger)
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "9"
    assert fields["minute"] == "0"


def test_email_morning_trigger():
    from app.workers.scheduler import start_scheduler

    sched = start_scheduler(start=False)
    job = _get_job(sched, "email_morning")
    assert isinstance(job.trigger, CronTrigger)
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "9"
    assert fields["minute"] == "30"


# ---------------------------------------------------------------------------
# 3. Scheduler timezone is Asia/Taipei
# ---------------------------------------------------------------------------

def test_scheduler_timezone():
    from app.workers.scheduler import start_scheduler, TIMEZONE

    assert TIMEZONE == "Asia/Taipei"
    sched = start_scheduler(start=False)
    # APScheduler stores timezone as a tzinfo; stringify should contain Taipei
    assert "Taipei" in str(sched.timezone)


# ---------------------------------------------------------------------------
# 4. _ingest_job calls run_daily_ingest with date.today()
# ---------------------------------------------------------------------------

def test_ingest_job_calls_run_daily_ingest(monkeypatch):
    called: dict = {}

    def fake_ingest(today: date) -> dict:
        called["today"] = today
        return {"profiles": 0, "matches": 0, "llm_calls": 0}

    monkeypatch.setattr("app.workers.scheduler.run_daily_ingest", fake_ingest)

    from app.workers.scheduler import _ingest_job

    _ingest_job()
    assert "today" in called
    assert called["today"] == date.today()


# ---------------------------------------------------------------------------
# 5a. _push_job with no users in DB does not crash
# ---------------------------------------------------------------------------

def test_push_job_no_users_no_crash(monkeypatch):
    """When the users table is empty, _push_job should run without error."""
    push_calls: list = []

    def fake_push(line_user_id: str, matches: list) -> None:
        push_calls.append((line_user_id, matches))

    monkeypatch.setattr("app.workers.scheduler.push_match_alert", fake_push)

    from app.workers.scheduler import _push_job

    _push_job()
    assert push_calls == []


# ---------------------------------------------------------------------------
# 5b. _push_job with a seeded high-score match calls push_match_alert
# ---------------------------------------------------------------------------

def test_push_job_calls_push_match_alert_for_high_score(monkeypatch):
    """Seed a User + Tender + high-score Match; verify push_match_alert is called."""
    from datetime import date as dt

    from sqlmodel import Session

    from app.db import engine
    from app.models.match import Match
    from app.models.profile import Profile
    from app.models.tender import Tender
    from app.models.user import User

    today = dt.today()

    with Session(engine) as s:
        user = User(line_user_id="U123", display_name="Test User", email="test@example.com")
        s.add(user)
        s.commit()
        s.refresh(user)

        profile = Profile(
            user_id=user.id,
            company_name="Test Co",
            capital_twd=5_000_000,
            employee_count=10,
            capability_description="IT consulting",
            min_tender_budget_twd=100_000,
            max_tender_budget_twd=10_000_000,
            excluded_categories=[],
            iso_certifications=[],
            minimum_days_to_deadline=7,
        )
        s.add(profile)
        s.commit()
        s.refresh(profile)

        tender = Tender(
            case_no="T-2024-001",
            title="IT Consulting Services",
            agency="Test Agency",
            category="資訊",
            budget_twd=500_000,
            posted_date=today,
            deadline_date=today,
        )
        s.add(tender)
        s.commit()

        match = Match(
            user_id=user.id,
            profile_id=profile.id,
            tender_case_no="T-2024-001",
            passes_hard_filter=True,
            llm_score=85,
            llm_match_level="HIGH",
            llm_recommendation="Strongly recommended",
        )
        s.add(match)
        s.commit()

    push_calls: list = []

    def fake_push(line_user_id: str, matches: list) -> None:
        push_calls.append((line_user_id, matches))

    monkeypatch.setattr("app.workers.scheduler.push_match_alert", fake_push)

    from app.workers.scheduler import _push_job

    _push_job()

    assert len(push_calls) == 1
    line_uid, matches = push_calls[0]
    assert line_uid == "U123"
    assert len(matches) == 1
    m = matches[0]
    assert m["case_no"] == "T-2024-001"
    assert m["llm_score"] == 85
    assert m["llm_match_level"] == "HIGH"
