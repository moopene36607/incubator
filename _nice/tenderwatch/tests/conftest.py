"""Shared fixtures.

Tests use an in-memory SQLite database so they run without a Postgres
container. Production uses Postgres via DATABASE_URL — columns are JSON
(database-agnostic) so the model code is identical across both engines.
"""

import os

# point app.config + app.db at an in-memory SQLite before any app import
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SESSION_SECRET", "test-secret")

import pytest
from sqlmodel import SQLModel


@pytest.fixture(autouse=True)
def _reset_db():
    """Drop + recreate all tables before each test so state doesn't leak."""
    from app.db import engine
    import app.models  # noqa: F401 — register tables

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
