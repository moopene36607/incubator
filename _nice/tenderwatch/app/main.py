"""FastAPI entry. Mounted by uvicorn in production, imported by tests.

Sentry is wired up only when SENTRY_DSN is set.
APScheduler is started only in `env=prod` so test runs don't fire jobs.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.routes import auth, billing, dashboard, ecpay_hooks, linebot, onboarding, public

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    if settings.sentry_dsn:
        import sentry_sdk  # local import keeps test startup fast
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)

    if settings.env == "prod":
        from app.workers.scheduler import start_scheduler
        app.state.scheduler = start_scheduler()

    yield

    sched = getattr(app.state, "scheduler", None)
    if sched:
        sched.shutdown()


app = FastAPI(title="tenderwatch", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=get_settings().session_secret)
app.include_router(public.router)
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(dashboard.router)
app.include_router(linebot.router)
app.include_router(billing.router)
app.include_router(ecpay_hooks.router)
