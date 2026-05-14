"""Marketing + Legal + Pricing public routes.

These are unauthenticated pages a visitor sees before signing up. They must:
- return 200 with rich HTML (not just a placeholder)
- include core copy keywords so SEO and humans understand the page
- not leak app navigation that requires login

The dashboard, billing, and onboarding pages each have their own test files;
this file is only about the public marketing surface.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------


def test_landing_returns_200_with_rich_html():
    r = _client().get("/")
    assert r.status_code == 200
    body = r.text
    # The landing page must actually be a landing page — not the 1-line stub.
    assert len(body) > 2000, f"landing page too short ({len(body)} chars)"
    # Brand and value proposition
    assert "tenderwatch" in body.lower()
    assert "政府電子採購網" in body or "政採網" in body
    # Above-fold pricing CTA
    assert "/pricing" in body
    # LINE 推播是核心賣點
    assert "LINE" in body


def test_landing_shows_three_key_benefits():
    """Hero + 3-feature flat-design layout requires 3 benefit blocks."""
    body = _client().get("/").text
    for kw in ("AI", "LINE", "即時"):
        assert kw in body, f"missing benefit keyword: {kw}"


# ---------------------------------------------------------------------------
# Pricing page
# ---------------------------------------------------------------------------


def test_pricing_lists_three_tiers_and_amounts():
    r = _client().get("/pricing")
    assert r.status_code == 200
    body = r.text
    # Tiers
    assert "Free" in body
    assert "Solo" in body
    assert "Pro" in body
    # Real amounts in NT$
    assert "799" in body
    assert "2,500" in body or "2500" in body
    # Each paid tier must link to checkout
    assert "/billing/checkout?plan=solo" in body
    assert "/billing/checkout?plan=pro" in body


def test_pricing_marks_solo_as_recommended():
    """Solo is the PLG sweet spot — must be visually highlighted."""
    body = _client().get("/pricing").text.lower()
    # We use a "推薦" / "recommended" badge near the Solo card
    assert "推薦" in _client().get("/pricing").text or "recommended" in body


# ---------------------------------------------------------------------------
# FAQ page
# ---------------------------------------------------------------------------


def test_faq_returns_200_with_questions():
    r = _client().get("/faq")
    assert r.status_code == 200
    body = r.text
    # Questions a real visitor asks
    for q in ("退費", "免費", "LINE", "資料"):
        assert q in body, f"FAQ missing topic: {q}"


# ---------------------------------------------------------------------------
# Legal pages
# ---------------------------------------------------------------------------


def test_tos_returns_200_with_required_clauses():
    r = _client().get("/tos")
    assert r.status_code == 200
    body = r.text
    # 中華民國消保法核心要件 + tenderwatch 名稱
    assert "服務條款" in body
    assert "tenderwatch" in body.lower()
    # 不負中標結果 — 必須白紙黑字
    assert "中標" in body or "決標" in body


def test_privacy_returns_200_with_pdpa_clauses():
    r = _client().get("/privacy")
    assert r.status_code == 200
    body = r.text
    assert "隱私" in body
    # PDPA：必須列舉收集的個資範圍 + 利用目的 + 期間
    assert "個人資料" in body or "個資" in body
    assert "LINE" in body  # 我們唯一的登入提供者
    assert "目的" in body
    # 使用者權利：查閱 / 刪除
    assert "刪除" in body or "停止" in body


def test_refund_returns_200_with_policy():
    r = _client().get("/refund")
    assert r.status_code == 200
    body = r.text
    assert "退費" in body or "退款" in body
    # Trial / refund 規則必須清楚
    assert "14" in body or "試用" in body


# ---------------------------------------------------------------------------
# Cross-cutting: footer + nav consistency
# ---------------------------------------------------------------------------


def test_landing_footer_links_to_all_legal_pages():
    body = _client().get("/").text
    assert "/tos" in body
    assert "/privacy" in body
    assert "/refund" in body


def test_marketing_pages_do_not_show_logged_in_nav():
    """Logged-out visitors must not see 登出 / 今日標案 in the header."""
    for path in ("/", "/pricing", "/faq", "/tos", "/privacy", "/refund"):
        body = _client().get(path).text
        assert "登出" not in body, f"{path} leaks logged-in nav"
