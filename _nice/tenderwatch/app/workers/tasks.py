"""Daily ingest pipeline — invoked from APScheduler (06:00 + 14:00 Asia/Taipei).

Stages, in order:
  1. fetch today's tenders from PCC OpenData
  2. upsert tender rows
  3. for each user profile:
     a. hard-filter (pure function) — fails persist a Match with reasons
     b. embedding cosine pre-filter — below threshold skips LLM (saves tokens)
     c. LLM semantic scoring — only the survivors hit Anthropic

External callables (fetch_tenders_for_date / embed / run_semantic_score) are
imported at module level so tests can patch them in one place.
"""

from __future__ import annotations

from datetime import date

import structlog
from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine
from app.ingest.embedder import cosine, embed
from app.ingest.opendata import fetch_tenders_for_date
from app.models.match import Match
from app.models.profile import Profile
from app.models.tender import Tender
from app.scoring.filter import run_hard_filter
from app.scoring.semantic import run_semantic_score

log = structlog.get_logger(__name__)


def _upsert_tenders(rows: list[dict]) -> None:
    """Insert new tenders by case_no. Existing rows are left untouched."""
    if not rows:
        return
    with Session(engine) as s:
        for r in rows:
            if s.get(Tender, r["case_no"]) is not None:
                continue
            t = Tender(
                case_no=r["case_no"], title=r["title"], agency=r["agency"],
                category=r["category"], budget_twd=int(r["budget_twd"]),
                posted_date=date.fromisoformat(r["posted_date"]),
                deadline_date=date.fromisoformat(r["deadline_date"]),
                description=r.get("description", ""),
                required_capital_twd=int(r.get("required_capital_twd", 0)),
                required_certs=list(r.get("required_certs", [])),
                location=r.get("location", "全國"),
                raw_payload=r.get("raw_payload", {}),
            )
            s.add(t)
        s.commit()


def _profile_to_row(p: Profile) -> dict:
    return {
        "company_name": p.company_name,
        "capital_twd": p.capital_twd,
        "employee_count": p.employee_count,
        "capability_description": p.capability_description,
        "min_tender_budget_twd": p.min_tender_budget_twd,
        "max_tender_budget_twd": p.max_tender_budget_twd,
        "excluded_categories": list(p.excluded_categories),
        "iso_certifications": list(p.iso_certifications),
        "minimum_days_to_deadline": p.minimum_days_to_deadline,
    }


def run_daily_ingest(today: date) -> dict:
    settings = get_settings()
    rows = list(fetch_tenders_for_date(today))
    _upsert_tenders(rows)
    log.info("ingest.fetched", count=len(rows), date=today.isoformat())

    profiles_processed = 0
    matches_created = 0
    llm_calls = 0

    with Session(engine) as s:
        profiles = s.exec(select(Profile)).all()
        for profile in profiles:
            profile_row = _profile_to_row(profile)

            # ensure profile has an embedding (cached on first run)
            if profile.embedding is None:
                profile.embedding = embed(profile.capability_description)
                s.add(profile); s.commit(); s.refresh(profile)

            for r in rows:
                hf = run_hard_filter(r, profile_row, today)

                if not hf["passes_hard_filter"]:
                    s.add(Match(
                        user_id=profile.user_id, profile_id=profile.id,
                        tender_case_no=r["case_no"], passes_hard_filter=False,
                        fail_reasons=hf["fail_reasons"]))
                    matches_created += 1
                    continue

                # cosine prefilter: embed tender if not yet cached
                tender = s.get(Tender, r["case_no"])
                if tender.embedding is None:
                    tender.embedding = embed(
                        f"{tender.title}\n{tender.category}\n{r.get('description', '')}"
                    )
                    s.add(tender); s.commit(); s.refresh(tender)

                sim = cosine(profile.embedding, tender.embedding)
                if sim < settings.semantic_sim_threshold:
                    s.add(Match(
                        user_id=profile.user_id, profile_id=profile.id,
                        tender_case_no=r["case_no"], passes_hard_filter=True,
                        cosine_sim=sim, llm_score=None))
                    matches_created += 1
                    continue

                # LLM scoring
                sc = run_semantic_score(r, profile_row)
                llm_calls += 1
                s.add(Match(
                    user_id=profile.user_id, profile_id=profile.id,
                    tender_case_no=r["case_no"], passes_hard_filter=True,
                    cosine_sim=sim, llm_score=int(sc["score"]),
                    llm_match_level=sc.get("match_level"),
                    llm_key_match_points=list(sc.get("key_match_points", [])),
                    llm_key_gaps=list(sc.get("key_gaps", [])),
                    llm_recommendation=sc.get("recommendation")))
                matches_created += 1

            s.commit()
            profiles_processed += 1

    stats = {"profiles": profiles_processed, "matches": matches_created, "llm_calls": llm_calls}
    log.info("ingest.done", **stats)
    return stats
