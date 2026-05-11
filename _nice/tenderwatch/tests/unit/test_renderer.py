"""TDD tests for app.notify.renderer.

Pure functions: dict-in / string-out. No external dependencies. We test the
*structure* of the produced strings (key headings, line patterns) so cosmetic
refactors don't break tests, but content correctness is preserved.
"""

from app.notify.renderer import render_line_alert, render_markdown_report


def _match(case_no="T1", score=88, level="high", title="資安顧問", budget=2_500_000,
           agency="外交部", deadline="2026-06-30", key_match_points=None, key_gaps=None,
           recommendation="建議投標", passes=True):
    return {
        "case_no": case_no,
        "title": title,
        "agency": agency,
        "budget_twd": budget,
        "deadline_date": deadline,
        "category": "資訊服務",
        "location": "台北市",
        "passes_hard_filter": passes,
        "fail_reasons": [],
        "llm_score": score,
        "llm_match_level": level,
        "llm_key_match_points": key_match_points or [],
        "llm_key_gaps": key_gaps or [],
        "llm_recommendation": recommendation,
    }


_PROFILE = {"company_name": "Acme 顧問", "capability_description": "IT 顧問"}


def test_markdown_report_shows_company_name_header():
    out = render_markdown_report(_PROFILE, today="2026-05-10",
                                 passed_matches=[_match()], failed_matches=[])
    assert "Acme 顧問" in out
    assert "# " in out  # has H1


def test_markdown_report_includes_high_match_section_when_score_above_80():
    out = render_markdown_report(_PROFILE, today="2026-05-10",
                                 passed_matches=[_match(score=88)], failed_matches=[])
    assert "88/100" in out
    assert "🔥" in out  # high-match emoji


def test_markdown_report_sorts_by_llm_score_descending():
    matches = [_match(case_no="LOW", score=55, title="低分"),
               _match(case_no="HIGH", score=92, title="高分")]
    out = render_markdown_report(_PROFILE, today="2026-05-10",
                                 passed_matches=matches, failed_matches=[])
    assert out.index("HIGH") < out.index("LOW")


def test_markdown_report_lists_failed_matches_with_reasons():
    failed = [{
        "case_no": "BAD", "title": "壞案", "agency": "X", "budget_twd": 100,
        "category": "工程", "passes_hard_filter": False,
        "fail_reasons": ["預算太低", "排除類別"],
    }]
    out = render_markdown_report(_PROFILE, today="2026-05-10",
                                 passed_matches=[], failed_matches=failed)
    assert "BAD" in out
    assert "預算太低" in out
    assert "排除類別" in out


def test_line_alert_lists_only_score_70_and_above():
    matches = [_match(case_no="HIGH", score=88),
               _match(case_no="MEDIUM", score=55),
               _match(case_no="EXACT70", score=70)]
    out = render_line_alert(_PROFILE, scored_matches=matches)
    assert "HIGH" in out
    assert "EXACT70" in out
    assert "MEDIUM" not in out


def test_line_alert_says_nothing_when_no_high_matches():
    matches = [_match(case_no="LOW", score=40)]
    out = render_line_alert(_PROFILE, scored_matches=matches)
    assert "0 件" in out or "0件" in out
    assert "LOW" not in out


def test_line_alert_includes_case_no_and_budget_per_item():
    out = render_line_alert(_PROFILE, scored_matches=[_match(case_no="T-CASE-123", budget=3_000_000)])
    assert "T-CASE-123" in out
    assert "3,000,000" in out
