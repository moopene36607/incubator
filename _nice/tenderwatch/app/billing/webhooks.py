"""ECPay AIO webhook verification and callback application."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta

import structlog
from sqlmodel import select

from app.billing.ecpay import compute_check_mac_value
from app.config import get_settings
from app.db import get_session
from app.models.subscription import Subscription

log = structlog.get_logger(__name__)


def verify_callback(
    form_data: dict[str, str], hash_key: str, hash_iv: str
) -> bool:
    """Recompute CheckMacValue and compare timing-safe to form_data value.

    Returns True if the signature is valid, False otherwise.
    """
    received = form_data.get("CheckMacValue", "")
    expected = compute_check_mac_value(form_data, hash_key, hash_iv)
    valid = hmac.compare_digest(received.upper(), expected.upper())
    if not valid:
        log.warning(
            "ecpay.webhook.invalid_signature",
            trade_no=form_data.get("MerchantTradeNo"),
        )
    return valid


def apply_callback(form_data: dict[str, str]) -> Subscription | None:
    """Update Subscription status from ECPay callback.

    - RtnCode == '1' → status='active', next_charge_at = now + 30 days
    - other          → status='failed'

    Returns the updated Subscription, or None if trade no not found (silently
    ignored per ECPay integration spec).
    """
    trade_no = form_data.get("MerchantTradeNo", "")
    rtn_code = form_data.get("RtnCode", "")

    with get_session() as sess:
        sub = sess.exec(
            select(Subscription).where(
                Subscription.ecpay_merchant_trade_no == trade_no
            )
        ).first()

        if sub is None:
            log.info("ecpay.webhook.unknown_trade_no", trade_no=trade_no)
            return None

        if rtn_code == "1":
            sub.status = "active"
            sub.next_charge_at = datetime.now(UTC) + timedelta(days=30)
            log.info("ecpay.webhook.activated", trade_no=trade_no, sub_id=sub.id)
        else:
            sub.status = "failed"
            log.warning(
                "ecpay.webhook.payment_failed",
                trade_no=trade_no,
                rtn_code=rtn_code,
                sub_id=sub.id,
            )

        sess.add(sub)
        sess.commit()
        sess.refresh(sub)
        return sub
