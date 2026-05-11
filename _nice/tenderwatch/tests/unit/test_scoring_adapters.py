"""TDD tests for app.scoring.filter — adapter over prototype tender_filter.

We don't re-test tender_filter's hard-condition logic (already covered by the
prototype's own smoke tests in README). What we test is the *adapter contract*:
dict-in → dict-out, with the boolean + reason list the worker depends on.
"""

from datetime import date

from app.scoring.filter import run_hard_filter


_PROFILE = {
    "company_name": "Test Co",
    "capital_twd": 5_000_000,
    "employee_count": 5,
    "capability_description": "IT 顧問",
    "min_tender_budget_twd": 500_000,
    "max_tender_budget_twd": None,
    "excluded_categories": [],
    "iso_certifications": [],
    "minimum_days_to_deadline": 7,
}


def _tender(**overrides) -> dict:
    base = {
        "case_no": "T1",
        "title": "x",
        "agency": "y",
        "category": "資訊服務",
        "budget_twd": 2_000_000,
        "posted_date": "2026-05-10",
        "deadline_date": "2026-06-30",
        "description": "",
        "required_capital_twd": 0,
        "required_certs": [],
        "location": "全國",
    }
    base.update(overrides)
    return base


def test_passes_when_all_conditions_met():
    out = run_hard_filter(_tender(), _PROFILE, today=date(2026, 5, 10))
    assert out["passes_hard_filter"] is True
    assert out["fail_reasons"] == []
    assert out["case_no"] == "T1"


def test_rejects_underbudget_tender():
    out = run_hard_filter(_tender(budget_twd=100_000), _PROFILE, today=date(2026, 5, 10))
    assert out["passes_hard_filter"] is False
    assert any("低於" in r for r in out["fail_reasons"])


def test_rejects_when_deadline_too_close():
    # only 5 days until deadline (default min is 7)
    out = run_hard_filter(
        _tender(deadline_date="2026-05-15"),
        _PROFILE,
        today=date(2026, 5, 10),
    )
    assert out["passes_hard_filter"] is False
    assert any("截止" in r or "天" in r for r in out["fail_reasons"])


def test_rejects_when_capital_requirement_exceeds_user():
    out = run_hard_filter(
        _tender(required_capital_twd=10_000_000),
        _PROFILE,
        today=date(2026, 5, 10),
    )
    assert out["passes_hard_filter"] is False
    assert any("資本額" in r for r in out["fail_reasons"])


def test_rejects_excluded_category():
    profile = {**_PROFILE, "excluded_categories": ["工程施作"]}
    out = run_hard_filter(_tender(category="工程施作"), profile, today=date(2026, 5, 10))
    assert out["passes_hard_filter"] is False
    assert any("工程施作" in r for r in out["fail_reasons"])


def test_rejects_missing_required_cert():
    out = run_hard_filter(
        _tender(required_certs=["ISO 27001"]),
        _PROFILE,
        today=date(2026, 5, 10),
    )
    assert out["passes_hard_filter"] is False
    assert any("ISO 27001" in r for r in out["fail_reasons"])


def test_multiple_failures_all_listed():
    # under budget AND too close to deadline → both reasons appear
    out = run_hard_filter(
        _tender(budget_twd=100_000, deadline_date="2026-05-13"),
        _PROFILE,
        today=date(2026, 5, 10),
    )
    assert out["passes_hard_filter"] is False
    assert len(out["fail_reasons"]) >= 2
