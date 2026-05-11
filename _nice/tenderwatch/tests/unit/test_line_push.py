"""TDD tests for app.notify.line_push.

Uses respx to mock the LINE Messaging API so no real HTTP calls are made.
"""

from __future__ import annotations

import pytest
import respx
import httpx

from app.config import Settings


@pytest.fixture
def fake_settings():
    return Settings(
        line_bot_channel_access_token="tok",
        line_bot_channel_secret="csec",
        session_secret="x",
    )


def _match(case_no="T1", score=88, title="資安顧問", budget=2_500_000,
           agency="外交部", deadline="2026-06-30"):
    return {
        "case_no": case_no,
        "title": title,
        "agency": agency,
        "budget_twd": budget,
        "deadline_date": deadline,
        "category": "資訊服務",
        "location": "台北市",
        "passes_hard_filter": True,
        "fail_reasons": [],
        "llm_score": score,
        "llm_match_level": "high",
        "llm_key_match_points": ["IT 顧問能力符合"],
        "llm_key_gaps": [],
        "llm_recommendation": "建議投標",
    }


_PROFILE = {"company_name": "Acme 顧問", "capability_description": "IT 顧問"}

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


@respx.mock
def test_push_text_posts_correct_payload(fake_settings):
    """push_text sends correct JSON body and Authorization header."""
    route = respx.post(LINE_PUSH_URL).mock(
        return_value=httpx.Response(200, json={})
    )

    from app.notify.line_push import push_text
    result = push_text("U1", "hi", settings=fake_settings)

    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer tok"

    import json
    body = json.loads(request.content)
    assert body["to"] == "U1"
    assert body["messages"] == [{"type": "text", "text": "hi"}]
    assert result == {}


@respx.mock
def test_push_text_raises_on_4xx(fake_settings):
    """push_text raises httpx.HTTPStatusError on non-2xx response."""
    respx.post(LINE_PUSH_URL).mock(
        return_value=httpx.Response(400, json={"message": "bad request"})
    )

    from app.notify.line_push import push_text
    with pytest.raises(httpx.HTTPStatusError):
        push_text("U1", "hi", settings=fake_settings)


@respx.mock
def test_push_match_alert_sends_rendered_text(fake_settings):
    """push_match_alert builds alert from renderer and calls push_text."""
    route = respx.post(LINE_PUSH_URL).mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    from app.notify.line_push import push_match_alert
    from app.notify.renderer import render_line_alert

    matches = [_match(score=88)]
    expected_text = render_line_alert(_PROFILE, scored_matches=matches)

    result = push_match_alert("U1", _PROFILE, matches, settings=fake_settings)

    assert route.called
    import json
    body = json.loads(route.calls.last.request.content)
    assert body["messages"][0]["text"] == expected_text
    assert result == {"ok": True}


@respx.mock
def test_push_match_alert_returns_none_on_empty_matches(fake_settings):
    """push_match_alert returns None and does NOT call LINE when no matches qualify."""
    route = respx.post(LINE_PUSH_URL).mock(
        return_value=httpx.Response(200, json={})
    )

    from app.notify.line_push import push_match_alert

    # Empty list — renderer returns the "0 件" message but we check the
    # spec: "If body is empty / no matches qualify, return None without calling LINE."
    # The spec says no matches qualify means llm_score < 70 for all.
    low_matches = [_match(score=40)]
    result = push_match_alert("U1", _PROFILE, low_matches, settings=fake_settings)

    assert result is None
    assert route.call_count == 0
