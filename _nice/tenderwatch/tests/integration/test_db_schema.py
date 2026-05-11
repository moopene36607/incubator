"""Integration test for SQLModel schema.

We don't test ORM-level behavior here — we test the *contract* with the
worker: init_db() creates all required tables, and rows round-trip with
list/dict JSON columns intact (since the worker stores embeddings as
list[float] and fail_reasons as list[str]).
"""

from datetime import date

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models.match import Match
from app.models.profile import Profile
from app.models.subscription import Subscription
from app.models.tender import Tender
from app.models.user import User


def test_tables_created_after_init_db():
    init_db()
    with Session(engine) as s:
        assert s.exec(select(Tender)).all() == []
        assert s.exec(select(User)).all() == []
        assert s.exec(select(Profile)).all() == []
        assert s.exec(select(Match)).all() == []
        assert s.exec(select(Subscription)).all() == []


def test_tender_round_trips_with_list_fields():
    """required_certs (list[str]) and embedding (list[float]) survive a save+load."""
    init_db()
    with Session(engine) as s:
        s.add(Tender(
            case_no="11401001", title="資安顧問", agency="外交部",
            category="資訊服務", budget_twd=2_500_000,
            posted_date=date(2026, 5, 10), deadline_date=date(2026, 5, 30),
            description="ISO 27001 顧問",
            required_capital_twd=5_000_000,
            required_certs=["ISO 27001", "ISO 9001"],
            embedding=[0.1, 0.2, 0.3],
        ))
        s.commit()
    with Session(engine) as s:
        t = s.get(Tender, "11401001")
        assert t is not None
        assert t.required_certs == ["ISO 27001", "ISO 9001"]
        assert t.embedding == [0.1, 0.2, 0.3]


def test_user_unique_line_id():
    """Two users with the same line_user_id should not both be persistable."""
    init_db()
    import sqlalchemy.exc
    import pytest

    with Session(engine) as s:
        s.add(User(line_user_id="U1", display_name="A"))
        s.commit()

    with Session(engine) as s:
        s.add(User(line_user_id="U1", display_name="B"))
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            s.commit()


def test_profile_belongs_to_user():
    init_db()
    with Session(engine) as s:
        u = User(line_user_id="U2", display_name="Test")
        s.add(u)
        s.commit()
        s.refresh(u)
        p = Profile(
            user_id=u.id,
            company_name="Acme",
            capital_twd=5_000_000,
            employee_count=5,
            capability_description="IT 顧問",
            excluded_categories=["工程"],
            iso_certifications=["ISO 27001"],
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        assert p.user_id == u.id
        assert p.excluded_categories == ["工程"]


def test_match_persists_llm_score_and_reasons():
    init_db()
    with Session(engine) as s:
        u = User(line_user_id="U3", display_name="Test")
        s.add(u); s.commit(); s.refresh(u)
        p = Profile(user_id=u.id, company_name="X", capital_twd=1, employee_count=1,
                    capability_description="x")
        s.add(p); s.commit(); s.refresh(p)
        s.add(Tender(
            case_no="T1", title="t", agency="a", category="c",
            budget_twd=1, posted_date=date(2026, 5, 10),
            deadline_date=date(2026, 6, 1), description=""))
        s.commit()
        s.add(Match(
            user_id=u.id, profile_id=p.id, tender_case_no="T1",
            passes_hard_filter=True,
            fail_reasons=[],
            llm_score=88, llm_match_level="high",
            llm_key_match_points=["ISO 27001 match"],
            llm_key_gaps=[],
            llm_recommendation="建議投標",
        ))
        s.commit()
    with Session(engine) as s:
        m = s.exec(select(Match).where(Match.tender_case_no == "T1")).first()
        assert m is not None
        assert m.llm_score == 88
        assert m.llm_key_match_points == ["ISO 27001 match"]
