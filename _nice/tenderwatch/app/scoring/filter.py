"""Adapter — converts dict rows (DB / API shape) into the prototype's
dataclasses and invokes tender_filter.filter_tender. We keep the prototype as
the source of truth for hard-condition logic so it stays runnable on its own.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# add prototype dir to sys.path so we can import tender_filter without
# repackaging it. Prototype lives two levels up from app/scoring/.
PROTOTYPE_DIR = Path(__file__).resolve().parents[2]
if str(PROTOTYPE_DIR) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE_DIR))

from tender_filter import Tender, UserProfile, filter_tender  # noqa: E402


def run_hard_filter(tender_row: dict, profile_row: dict, today: date) -> dict:
    tender = Tender(
        case_no=tender_row["case_no"],
        title=tender_row["title"],
        agency=tender_row["agency"],
        category=tender_row["category"],
        budget_twd=int(tender_row["budget_twd"]),
        posted_date=tender_row["posted_date"],
        deadline_date=tender_row["deadline_date"],
        description=tender_row["description"],
        required_capital_twd=int(tender_row.get("required_capital_twd", 0)),
        required_certs=tuple(tender_row.get("required_certs", [])),
        location=tender_row.get("location", "全國"),
    )
    profile = UserProfile(
        company_name=profile_row["company_name"],
        capital_twd=int(profile_row["capital_twd"]),
        employee_count=int(profile_row["employee_count"]),
        capability_description=profile_row["capability_description"],
        min_tender_budget_twd=int(profile_row.get("min_tender_budget_twd", 0)),
        max_tender_budget_twd=profile_row.get("max_tender_budget_twd"),
        excluded_categories=tuple(profile_row.get("excluded_categories", [])),
        iso_certifications=tuple(profile_row.get("iso_certifications", [])),
        minimum_days_to_deadline=int(profile_row.get("minimum_days_to_deadline", 7)),
    )
    fr = filter_tender(tender, profile, today)
    return {
        "case_no": tender.case_no,
        "passes_hard_filter": fr.passes_hard_filter,
        "fail_reasons": list(fr.fail_reasons),
    }
