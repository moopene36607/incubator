"""Integration test for the daily ingest worker.

External dependencies (OpenData HTTP, OpenAI embeddings, Anthropic scoring)
are stubbed at the module boundary — we want to verify the *pipeline*: which
matches are persisted with which flags, given a deterministic profile and a
deterministic tender row.
"""

from datetime import date
from unittest.mock import patch

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models.match import Match
from app.models.profile import Profile
from app.models.user import User
from app.workers.tasks import run_daily_ingest


def _seed_user_with_profile(capability="IT 顧問,擅長 ISO 27001 + 雲端遷移"):
    init_db()
    with Session(engine) as s:
        u = User(line_user_id=f"U-{date.today().toordinal()}", display_name="Test", plan="solo")
        s.add(u); s.commit(); s.refresh(u)
        p = Profile(
            user_id=u.id, company_name="X", capital_twd=5_000_000, employee_count=5,
            capability_description=capability,
            min_tender_budget_twd=500_000,
            embedding=[1.0, 0.0, 0.0],
        )
        s.add(p); s.commit(); s.refresh(p)
        return u.id, p.id


def _good_tender():
    return {
        "case_no": "T-INGEST-1",
        "title": "資安顧問", "agency": "外交部", "category": "資訊服務",
        "budget_twd": 2_500_000,
        "posted_date": "2026-05-10", "deadline_date": "2026-06-30",
        "description": "ISO 27001 顧問",
        "required_capital_twd": 0, "required_certs": [], "location": "台北市",
        "raw_payload": {},
    }


def test_run_daily_ingest_persists_passing_match_with_llm_score():
    user_id, _ = _seed_user_with_profile()
    # cosine([1,0,0],[1,0,0])=1.0 → above 0.3 threshold → LLM runs
    with patch("app.workers.tasks.fetch_tenders_for_date", return_value=[_good_tender()]), \
         patch("app.workers.tasks.embed", return_value=[1.0, 0.0, 0.0]), \
         patch("app.workers.tasks.run_semantic_score", return_value={
             "score": 88, "match_level": "high",
             "key_match_points": ["ISO 27001 match"], "key_gaps": [],
             "recommendation": "建議投標"}):
        stats = run_daily_ingest(date(2026, 5, 10))

    assert stats["llm_calls"] == 1
    with Session(engine) as s:
        m = s.exec(select(Match).where(Match.user_id == user_id)).first()
        assert m is not None
        assert m.passes_hard_filter is True
        assert m.llm_score == 88
        assert m.llm_match_level == "high"
        assert m.llm_recommendation == "建議投標"


def test_run_daily_ingest_skips_llm_when_cosine_below_threshold():
    user_id, _ = _seed_user_with_profile()
    # profile embedding [1,0,0] vs tender embedding [0,1,0] → cosine 0 < 0.3 → skip LLM
    with patch("app.workers.tasks.fetch_tenders_for_date", return_value=[_good_tender()]), \
         patch("app.workers.tasks.embed", return_value=[0.0, 1.0, 0.0]), \
         patch("app.workers.tasks.run_semantic_score") as mock_llm:
        stats = run_daily_ingest(date(2026, 5, 10))

    assert stats["llm_calls"] == 0
    mock_llm.assert_not_called()
    with Session(engine) as s:
        m = s.exec(select(Match).where(Match.user_id == user_id)).first()
        assert m.passes_hard_filter is True
        assert m.llm_score is None  # was skipped by prefilter
        assert m.cosine_sim is not None
        assert m.cosine_sim < 0.3


def test_run_daily_ingest_records_hard_filter_failures_without_llm():
    user_id, _ = _seed_user_with_profile()
    bad_tender = _good_tender()
    bad_tender["case_no"] = "T-BAD"
    bad_tender["budget_twd"] = 1  # below profile.min_tender_budget_twd=500k

    with patch("app.workers.tasks.fetch_tenders_for_date", return_value=[bad_tender]), \
         patch("app.workers.tasks.embed") as mock_embed, \
         patch("app.workers.tasks.run_semantic_score") as mock_llm:
        run_daily_ingest(date(2026, 5, 10))

    mock_llm.assert_not_called()
    mock_embed.assert_not_called()  # cosine prefilter never reached
    with Session(engine) as s:
        m = s.exec(select(Match).where(Match.tender_case_no == "T-BAD")).first()
        assert m is not None
        assert m.passes_hard_filter is False
        assert len(m.fail_reasons) >= 1
        assert m.llm_score is None
