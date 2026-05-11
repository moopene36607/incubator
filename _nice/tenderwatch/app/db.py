"""SQLModel engine + init.

Test envs override DATABASE_URL to `sqlite:///:memory:` (via tests/conftest.py).
For SQLite an in-memory DB is per-connection, so we use a StaticPool so the
test process keeps the same connection across sessions.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_settings = get_settings()

_engine_kwargs: dict = {"echo": False}
if _settings.database_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool
else:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(_settings.database_url, **_engine_kwargs)


def init_db() -> None:
    """Register all models then CREATE TABLE IF NOT EXISTS for the full schema."""
    import app.models  # noqa: F401 — side-effect: register tables
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
