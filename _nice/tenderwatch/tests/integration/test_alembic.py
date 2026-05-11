"""Integration tests for Alembic migrations.

Uses a temporary SQLite file (not in-memory) because Alembic needs a persistent
connection URL it can open across migration steps. DATABASE_URL is injected into
the subprocess environment so env.py / get_settings() picks it up automatically.
"""

import os
import subprocess

from sqlalchemy import create_engine, inspect


PROJECT_ROOT = "/home/deploy/incubator/_nice/tenderwatch"
EXPECTED_TABLES = {"users", "profiles", "tenders", "matches", "subscriptions"}


def _run_alembic(args: list[str], db_url: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    return subprocess.run(
        ["uv", "run", "alembic"] + args,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_alembic_upgrade_head_creates_all_tables(tmp_path):
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"

    result = _run_alembic(["upgrade", "head"], url)
    assert result.returncode == 0, f"alembic upgrade head failed:\n{result.stderr}"

    engine = create_engine(url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert EXPECTED_TABLES <= tables, f"Missing tables: {EXPECTED_TABLES - tables}"


def test_alembic_downgrade_drops_all_tables(tmp_path):
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"

    # First upgrade to head
    up = _run_alembic(["upgrade", "head"], url)
    assert up.returncode == 0, f"alembic upgrade head failed:\n{up.stderr}"

    # Then downgrade to base
    down = _run_alembic(["downgrade", "base"], url)
    assert down.returncode == 0, f"alembic downgrade base failed:\n{down.stderr}"

    engine = create_engine(url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    # Only alembic_version table may remain; none of our app tables should exist
    app_tables = EXPECTED_TABLES & tables
    assert not app_tables, f"Tables still present after downgrade: {app_tables}"


def test_alembic_upgrade_is_idempotent(tmp_path):
    """Running upgrade head twice should be a no-op (exit 0)."""
    db_path = tmp_path / "test.db"
    url = f"sqlite:///{db_path}"

    r1 = _run_alembic(["upgrade", "head"], url)
    assert r1.returncode == 0, r1.stderr

    r2 = _run_alembic(["upgrade", "head"], url)
    assert r2.returncode == 0, r2.stderr

    engine = create_engine(url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert EXPECTED_TABLES <= tables
