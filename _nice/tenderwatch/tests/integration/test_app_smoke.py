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


def test_login_redirects_to_line_authorize():
    r = _client().get("/login", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "access.line.me" in r.headers["location"]


def test_onboarding_requires_login():
    r = _client().get("/onboarding")
    assert r.status_code == 401


def test_app_today_requires_login():
    r = _client().get("/app/today", follow_redirects=False)
    assert r.status_code == 401


def test_billing_checkout_requires_login():
    r = _client().get("/billing/checkout", params={"plan": "solo"})
    assert r.status_code == 401


def test_line_webhook_rejects_missing_signature():
    r = _client().post("/webhook/line", content=b"{}")
    assert r.status_code == 400


def test_ecpay_webhook_rejects_invalid_mac():
    r = _client().post("/webhook/ecpay", data={"foo": "bar"})
    assert r.status_code == 200
    assert "InvalidCheckMacValue" in r.text
