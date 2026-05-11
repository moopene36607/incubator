"""TDD tests for app.ingest.opendata.

We mock the PCC endpoint with respx so unit tests don't hit the network.
Normalization is the contract under test: the fetcher must produce
dict rows shaped like Tender's columns (so the worker can upsert them
without further translation).
"""

from datetime import date

import pytest
import respx
from httpx import Response

from app.ingest.opendata import fetch_tenders_for_date


SAMPLE_JSON = {
    "tenders": [
        {
            "case_no": "11401001",
            "title": "資安顧問服務",
            "agency": "外交部",
            "category": "資訊服務",
            "budget_twd": 2_500_000,
            "posted_date": "2026-05-10",
            "deadline_date": "2026-05-30",
            "description": "提供 ISO 27001 顧問服務",
            "required_capital_twd": 5_000_000,
            "required_certs": ["ISO 27001"],
            "location": "台北市",
        }
    ]
}

ENDPOINT = "https://web.pcc.gov.tw/prkms/tender/common/bulletion/listTenderByDate"


@respx.mock
def test_fetch_normalizes_pcc_payload():
    respx.get(ENDPOINT).mock(return_value=Response(200, json=SAMPLE_JSON))
    out = list(fetch_tenders_for_date(date(2026, 5, 10)))
    assert len(out) == 1
    row = out[0]
    assert row["case_no"] == "11401001"
    assert row["title"] == "資安顧問服務"
    assert row["budget_twd"] == 2_500_000
    assert row["required_certs"] == ["ISO 27001"]
    assert row["location"] == "台北市"


@respx.mock
def test_fetch_defaults_missing_optional_fields():
    """raw payload missing description / certs / location → safe defaults."""
    minimal = {"tenders": [{
        "case_no": "X1",
        "title": "T",
        "agency": "A",
        "category": "C",
        "budget_twd": 100_000,
        "posted_date": "2026-05-10",
        "deadline_date": "2026-06-01",
    }]}
    respx.get(ENDPOINT).mock(return_value=Response(200, json=minimal))
    out = list(fetch_tenders_for_date(date(2026, 5, 10)))
    assert out[0]["description"] == ""
    assert out[0]["required_certs"] == []
    assert out[0]["location"] == "全國"
    assert out[0]["required_capital_twd"] == 0


@respx.mock
def test_fetch_empty_response_returns_empty_iterator():
    respx.get(ENDPOINT).mock(return_value=Response(200, json={"tenders": []}))
    assert list(fetch_tenders_for_date(date(2026, 5, 10))) == []


@respx.mock
def test_fetch_retries_on_429():
    """rate-limit on first attempt is retried; second attempt succeeds."""
    route = respx.get(ENDPOINT)
    route.side_effect = [Response(429), Response(200, json=SAMPLE_JSON)]
    out = list(fetch_tenders_for_date(date(2026, 5, 10), sleep_fn=lambda _: None))
    assert len(out) == 1
    assert route.call_count == 2


@respx.mock
def test_fetch_gives_up_after_three_429s():
    route = respx.get(ENDPOINT)
    route.side_effect = [Response(429), Response(429), Response(429)]
    with pytest.raises(RuntimeError, match="rate limit"):
        list(fetch_tenders_for_date(date(2026, 5, 10), sleep_fn=lambda _: None))
    assert route.call_count == 3


@respx.mock
def test_fetch_raises_on_5xx():
    respx.get(ENDPOINT).mock(return_value=Response(500))
    with pytest.raises(Exception):
        list(fetch_tenders_for_date(date(2026, 5, 10), sleep_fn=lambda _: None))
