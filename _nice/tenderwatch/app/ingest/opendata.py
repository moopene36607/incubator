"""PCC OpenData fetcher.

Hits the government e-procurement OpenData endpoint and yields normalized
tender rows. The endpoint is rate-limited so we retry on 429 with simple
exponential backoff. `sleep_fn` is injected so tests stay sub-second.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Callable, Iterator

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

PATH = "/prkms/tender/common/bulletion/listTenderByDate"
MAX_ATTEMPTS = 3


def fetch_tenders_for_date(
    d: date,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Iterator[dict]:
    settings = get_settings()
    url = f"{settings.pcc_opendata_base_url}{PATH}"
    params = {"date": d.isoformat()}

    payload: dict | None = None
    with httpx.Client(timeout=30.0) as client:
        for attempt in range(MAX_ATTEMPTS):
            resp = client.get(url, params=params)
            if resp.status_code == 429:
                log.warning("pcc.opendata.rate_limited", attempt=attempt)
                if attempt == MAX_ATTEMPTS - 1:
                    break
                sleep_fn(2**attempt * 5)
                continue
            resp.raise_for_status()
            payload = resp.json()
            break

    if payload is None:
        raise RuntimeError("pcc opendata rate limit not recoverable after retries")

    for raw in payload.get("tenders", []):
        yield _normalize(raw)


def _normalize(raw: dict) -> dict:
    return {
        "case_no": str(raw["case_no"]),
        "title": raw["title"],
        "agency": raw["agency"],
        "category": raw["category"],
        "budget_twd": int(raw.get("budget_twd", 0)),
        "posted_date": raw["posted_date"],
        "deadline_date": raw["deadline_date"],
        "description": raw.get("description", ""),
        "required_capital_twd": int(raw.get("required_capital_twd", 0)),
        "required_certs": list(raw.get("required_certs", [])),
        "location": raw.get("location", "全國"),
        "raw_payload": raw,
    }
