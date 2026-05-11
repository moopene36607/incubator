"""Smoke test the FastAPI app skeleton.

We only verify the *entry points* — `/` returns the landing page, `/healthz`
returns a heartbeat. Route logic for dashboards, billing, webhooks lives in
its own modules and gets tested separately.
"""

from fastapi.testclient import TestClient


def _client() -> TestClient:
    # Defer import so test env vars (DATABASE_URL etc) are honored.
    from app.main import app
    return TestClient(app)


def test_root_returns_landing_page():
    r = _client().get("/")
    assert r.status_code == 200
    assert "tenderwatch" in r.text.lower()


def test_healthz_returns_ok():
    r = _client().get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_unknown_path_returns_404():
    r = _client().get("/this-does-not-exist")
    assert r.status_code == 404
