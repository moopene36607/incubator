"""APScheduler daily job configuration.

Three daily jobs (Asia/Taipei time):
  06:00 + 14:00  — run_daily_ingest (fetch + filter + LLM-score new tenders)
  09:00          — push LINE alerts for high-score matches
  09:30          — send Resend email digest

Called from app/main.py lifespan as:
    app.state.scheduler = start_scheduler()
"""

from __future__ import annotations

from datetime import date

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Module-level import so tests can monkeypatch at this location
from app.workers.tasks import run_daily_ingest
from app.notify.line_push import push_match_alert

log = structlog.get_logger(__name__)

TIMEZONE = "Asia/Taipei"


def _ingest_job() -> None:
    """Run the daily ingest pipeline (fetched + filtered + LLM-scored)."""
    stats = run_daily_ingest(date.today())
    log.info("scheduler.ingest.done", **stats)


def _push_job() -> None:
    """Push 09:00 daily LINE alerts for every user with high-score matches."""
    from sqlmodel import Session, select

    from app.db import engine
    from app.models.match import Match
    from app.models.tender import Tender
    from app.models.user import User

    with Session(engine) as s:
        users = s.exec(select(User)).all()
        for u in users:
            rows = s.exec(
                select(Match, Tender)
                .join(Tender, Tender.case_no == Match.tender_case_no)
                .where(
                    Match.user_id == u.id,
                    Match.passes_hard_filter == True,  # noqa: E712
                    Match.llm_score != None,  # noqa: E711
                    Match.llm_score >= 70,
                )
            ).all()
            matches = [
                {
                    "case_no": t.case_no,
                    "title": t.title,
                    "agency": t.agency,
                    "budget_twd": t.budget_twd,
                    "deadline_date": t.deadline_date.isoformat(),
                    "llm_score": m.llm_score,
                    "llm_match_level": m.llm_match_level,
                    "llm_recommendation": m.llm_recommendation,
                }
                for m, t in rows
            ]
            if matches:
                try:
                    push_match_alert(u.line_user_id, matches)
                except Exception as e:
                    log.error("scheduler.push.fail", user=u.id, err=str(e))


def _email_job() -> None:
    """Daily 09:30 Resend email digest — defensive import for parallel-agent."""
    try:
        from app.notify.email_digest import send_daily_digest  # noqa: F401
    except ImportError:
        log.warning("scheduler.email.module_missing")
        return

    from sqlmodel import Session, select

    from app.db import engine
    from app.models.user import User

    with Session(engine) as s:
        users = s.exec(select(User)).all()
        for u in users:
            try:
                send_daily_digest(u)
            except Exception as e:
                log.error("scheduler.email.fail", user=u.id, err=str(e))


def start_scheduler(start: bool = True) -> AsyncIOScheduler:
    """Build the daily APScheduler with 4 jobs and optionally start it.

    Pass ``start=False`` in unit tests (no running event loop required).
    """
    sched = AsyncIOScheduler(timezone=TIMEZONE)
    sched.add_job(
        _ingest_job,
        CronTrigger(hour=6, minute=0, timezone=TIMEZONE),
        id="ingest_morning",
        replace_existing=True,
    )
    sched.add_job(
        _ingest_job,
        CronTrigger(hour=14, minute=0, timezone=TIMEZONE),
        id="ingest_afternoon",
        replace_existing=True,
    )
    sched.add_job(
        _push_job,
        CronTrigger(hour=9, minute=0, timezone=TIMEZONE),
        id="push_morning",
        replace_existing=True,
    )
    sched.add_job(
        _email_job,
        CronTrigger(hour=9, minute=30, timezone=TIMEZONE),
        id="email_morning",
        replace_existing=True,
    )
    if start:
        sched.start()
        log.info("scheduler.started", jobs=[j.id for j in sched.get_jobs()])
    return sched
