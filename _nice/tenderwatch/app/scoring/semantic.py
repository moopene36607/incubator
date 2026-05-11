"""Adapter — wraps prototype's llm_score_tender(profile, tender)."""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

PROTOTYPE_DIR = Path(__file__).resolve().parents[2]
if str(PROTOTYPE_DIR) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE_DIR))

from tender_filter import Tender, UserProfile  # noqa: E402
from tenderwatch import llm_score_tender  # noqa: E402


def run_semantic_score(tender_row: dict, profile_row: dict) -> dict:
    tender = Tender(
        case_no=tender_row["case_no"], title=tender_row["title"],
        agency=tender_row["agency"], category=tender_row["category"],
        budget_twd=int(tender_row["budget_twd"]),
        posted_date=tender_row["posted_date"], deadline_date=tender_row["deadline_date"],
        description=tender_row.get("description", ""),
        required_capital_twd=int(tender_row.get("required_capital_twd", 0)),
        required_certs=tuple(tender_row.get("required_certs", [])),
        location=tender_row.get("location", "全國"),
    )
    profile = UserProfile(
        company_name=profile_row["company_name"],
        capital_twd=int(profile_row["capital_twd"]),
        employee_count=int(profile_row["employee_count"]),
        capability_description=profile_row["capability_description"],
    )
    score = llm_score_tender(profile, tender)
    return asdict(score)
