"""TDD tests for app.notify.email_digest.

Pure-function tests for build_digest + send_daily_digest integration tests
with resend.Emails.send mocked via monkeypatch.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.config import Settings


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _match(
    case_no: str = "T-001",
    title: str = "資安顧問服務採購",
    agency: str = "數位部",
    budget_twd: int = 2_500_000,
    deadline_date: str = "2026-06-30",
    llm_score: int = 92,
    llm_match_level: str = "高匹配",
    llm_recommendation: str = "建議投標",
) -> dict:
    return {
        "case_no": case_no,
        "title": title,
        "agency": agency,
        "budget_twd": budget_twd,
        "deadline_date": deadline_date,
        "llm_score": llm_score,
        "llm_match_level": llm_match_level,
        "llm_recommendation": llm_recommendation,
    }


_FAKE_SETTINGS = Settings(resend_api_key="re_test_key", session_secret="x")

TODAY = date(2026, 5, 10)


# ---------------------------------------------------------------------------
# build_digest tests
# ---------------------------------------------------------------------------

def test_build_digest_empty_matches_subject_contains_0_and_date():
    from app.notify.email_digest import build_digest

    result = build_digest("a@x.tw", [], TODAY)

    assert "0 件" in result["subject"]
    assert "2026-05-10" in result["subject"]
    assert result["html"]   # non-empty
    assert result["text"]   # non-empty


def test_build_digest_one_match_subject_and_html_content():
    from app.notify.email_digest import build_digest

    m = _match(case_no="PCC-2026-001", title="雲端平台建置", llm_score=92)
    result = build_digest("a@x.tw", [m], TODAY)

    assert "1 件" in result["subject"]
    assert "PCC-2026-001" in result["html"]
    assert "雲端平台建置" in result["html"]
    assert "92" in result["html"]


def test_build_digest_from_address():
    from app.notify.email_digest import build_digest

    result = build_digest("a@x.tw", [], TODAY)

    assert result["from"] == "tenderwatch <hi@tenderwatch.tw>"


def test_build_digest_to_contains_user_email():
    from app.notify.email_digest import build_digest

    result = build_digest("recipient@company.tw", [_match()], TODAY)

    assert "recipient@company.tw" in result["to"]


# ---------------------------------------------------------------------------
# send_daily_digest tests
# ---------------------------------------------------------------------------

def test_send_calls_resend(monkeypatch):
    import resend
    from app.notify.email_digest import build_digest, send_daily_digest

    sent: list[dict] = []

    def fake_send(payload):
        sent.append(payload)
        return {"id": "abc-123"}

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))

    m = _match()
    result = send_daily_digest("a@x.tw", [m], TODAY, settings=_FAKE_SETTINGS)

    assert len(sent) == 1
    expected_payload = build_digest("a@x.tw", [m], TODAY)
    assert sent[0] == expected_payload
    assert result == {"id": "abc-123"}


def test_send_no_op_when_matches_empty(monkeypatch):
    import resend
    from app.notify.email_digest import send_daily_digest

    called = []

    def fake_send(payload):
        called.append(payload)
        return {"id": "should-not-happen"}

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))

    result = send_daily_digest("a@x.tw", [], TODAY, settings=_FAKE_SETTINGS)

    assert result is None
    assert called == []


def test_send_no_op_when_email_empty(monkeypatch):
    import resend
    from app.notify.email_digest import send_daily_digest

    called = []

    def fake_send(payload):
        called.append(payload)
        return {"id": "should-not-happen"}

    monkeypatch.setattr(resend.Emails, "send", staticmethod(fake_send))

    result = send_daily_digest("", [_match()], TODAY, settings=_FAKE_SETTINGS)

    assert result is None
    assert called == []


def test_send_sets_resend_api_key(monkeypatch):
    import resend
    from app.notify.email_digest import send_daily_digest

    monkeypatch.setattr(resend.Emails, "send", staticmethod(lambda p: {"id": "x"}))

    # Reset api_key to a known different value first
    resend.api_key = "old_key"

    send_daily_digest("a@x.tw", [_match()], TODAY, settings=_FAKE_SETTINGS)

    assert resend.api_key == "re_test_key"
