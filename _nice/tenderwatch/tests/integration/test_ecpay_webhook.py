"""Integration tests for POST /webhook/ecpay.

TDD: tests written first (RED), then implementation makes them GREEN.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import select

from app.billing.ecpay import compute_check_mac_value
from app.config import get_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HASH_KEY = "5294y06JbISpM5x9"
_HASH_IV = "v77hoKGq4kWxNNIS"


def _app() -> FastAPI:
    from app.routes import ecpay_hooks

    a = FastAPI()
    a.include_router(ecpay_hooks.router)
    return a


def _client() -> TestClient:
    return TestClient(_app())


def _signed_form(params: dict[str, str]) -> dict[str, str]:
    params = dict(params)
    params["CheckMacValue"] = compute_check_mac_value(params, _HASH_KEY, _HASH_IV)
    return params


def _seed_subscription(trade_no: str, status: str = "pending"):
    """Insert a Subscription row into the test DB."""
    from app.db import get_session
    from app.models.subscription import Subscription
    from app.models.user import User

    with get_session() as sess:
        u = User(line_user_id="Uwebhook1", display_name="WH User")
        sess.add(u)
        sess.commit()
        sess.refresh(u)
        sub = Subscription(
            user_id=u.id,
            plan="solo",
            ecpay_merchant_trade_no=trade_no,
            ecpay_period_amount=799,
            status=status,
        )
        sess.add(sub)
        sess.commit()
        sess.refresh(sub)
        return sub.id


# ---------------------------------------------------------------------------
# Override hash key/iv via env / settings — use the test constants
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch):
    monkeypatch.setenv("ECPAY_HASH_KEY", _HASH_KEY)
    monkeypatch.setenv("ECPAY_HASH_IV", _HASH_IV)
    monkeypatch.setenv("ECPAY_MERCHANT_ID", "2000132")
    monkeypatch.setenv("ECPAY_RETURN_URL", "https://example.com/webhook/ecpay")
    monkeypatch.setenv("ECPAY_CLIENT_BACK_URL", "https://example.com/app/billing")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_webhook_valid_rtn1_sets_active():
    """Valid signature + RtnCode=1 → '1|OK', status=active, next_charge_at set."""
    trade_no = "TWTEST00000001"
    sub_id = _seed_subscription(trade_no, status="pending")

    form = _signed_form({
        "MerchantID": "2000132",
        "MerchantTradeNo": trade_no,
        "RtnCode": "1",
        "RtnMsg": "Succeeded",
        "TradeNo": "ECPAY_TRADE_001",
        "TradeAmt": "799",
        "PaymentDate": "2024/01/01 12:00:00",
        "PaymentType": "Credit_CreditCard",
        "PaymentTypeChargeFee": "8",
        "TradeDate": "2024/01/01 11:00:00",
        "SimulatePaid": "0",
    })

    client = _client()
    r = client.post(
        "/webhook/ecpay",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert r.text == "1|OK"

    from app.db import get_session
    from app.models.subscription import Subscription

    with get_session() as sess:
        sub = sess.get(Subscription, sub_id)
        assert sub.status == "active"
        assert sub.next_charge_at is not None


def test_webhook_invalid_signature_rejected():
    """Tampered CheckMacValue → '0|InvalidCheckMacValue', DB unchanged."""
    trade_no = "TWTEST00000002"
    sub_id = _seed_subscription(trade_no, status="pending")

    form = {
        "MerchantID": "2000132",
        "MerchantTradeNo": trade_no,
        "RtnCode": "1",
        "RtnMsg": "Succeeded",
        "CheckMacValue": "BADBADBADBADBADBADBADBADBADBADBADBADBADBADBADBADBADBADBADBADBADB",
    }

    client = _client()
    r = client.post(
        "/webhook/ecpay",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert r.text == "0|InvalidCheckMacValue"

    from app.db import get_session
    from app.models.subscription import Subscription

    with get_session() as sess:
        sub = sess.get(Subscription, sub_id)
        assert sub.status == "pending"  # unchanged


def test_webhook_failed_rtn_sets_failed():
    """Valid signature + RtnCode != 1 → status=failed."""
    trade_no = "TWTEST00000003"
    sub_id = _seed_subscription(trade_no, status="pending")

    form = _signed_form({
        "MerchantID": "2000132",
        "MerchantTradeNo": trade_no,
        "RtnCode": "10100073",
        "RtnMsg": "Card Declined",
        "TradeNo": "ECPAY_TRADE_002",
        "TradeAmt": "799",
        "PaymentDate": "2024/01/01 12:00:00",
        "PaymentType": "Credit_CreditCard",
        "PaymentTypeChargeFee": "8",
        "TradeDate": "2024/01/01 11:00:00",
        "SimulatePaid": "0",
    })

    client = _client()
    r = client.post(
        "/webhook/ecpay",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert r.text == "1|OK"

    from app.db import get_session
    from app.models.subscription import Subscription

    with get_session() as sess:
        sub = sess.get(Subscription, sub_id)
        assert sub.status == "failed"


def test_webhook_unknown_trade_no_returns_ok_silently():
    """MerchantTradeNo not in DB → '1|OK', no crash."""
    form = _signed_form({
        "MerchantID": "2000132",
        "MerchantTradeNo": "NONEXISTENT999",
        "RtnCode": "1",
        "RtnMsg": "Succeeded",
        "TradeNo": "ECPAY_TRADE_003",
        "TradeAmt": "799",
        "PaymentDate": "2024/01/01 12:00:00",
        "PaymentType": "Credit_CreditCard",
        "PaymentTypeChargeFee": "8",
        "TradeDate": "2024/01/01 11:00:00",
        "SimulatePaid": "0",
    })

    client = _client()
    r = client.post(
        "/webhook/ecpay",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert r.text == "1|OK"
