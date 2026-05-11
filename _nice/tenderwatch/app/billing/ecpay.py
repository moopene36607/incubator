"""ECPay AIO V5 helpers — CheckMacValue, form payload builder.

Reference: https://developers.ecpay.com.tw (全方位金流 AIO)
"""

from __future__ import annotations

import hashlib
import random
import string
import urllib.parse
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    pass

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Plan catalogue
# ---------------------------------------------------------------------------

PLANS: dict[str, dict] = {
    "solo": {
        "amount": 799,
        "period_type": "M",
        "frequency": 1,
        "exec_times": 99,
        "item_name": "tenderwatch Solo 月費",
    },
    "pro": {
        "amount": 2500,
        "period_type": "M",
        "frequency": 1,
        "exec_times": 99,
        "item_name": "tenderwatch Pro 月費",
    },
}

ECPAY_STAGE_URL = "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
ECPAY_PROD_URL = "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5"


# ---------------------------------------------------------------------------
# CheckMacValue helpers
# ---------------------------------------------------------------------------


def dotnet_url_encode(s: str) -> str:
    """Reproduce .NET HttpUtility.UrlEncode semantics then lower().

    Steps:
    1. urllib.parse.quote_plus (space→+, encodes most special chars)
    2. Restore chars that .NET does NOT percent-encode: - _ . ! * ( )
    3. Lowercase the entire result (ECPay requires lowercase before SHA-256)
    """
    encoded = urllib.parse.quote_plus(s, safe="")
    # .NET's UrlEncode does not encode these characters — restore them from
    # their percent-encoded form.  quote_plus always produces uppercase hex
    # (%2D etc.) so we can do a simple lowercase replacement.
    encoded = encoded.replace("%2D", "-").replace("%5F", "_")
    encoded = encoded.replace("%2E", ".").replace("%21", "!")
    encoded = encoded.replace("%2A", "*").replace("%28", "(").replace("%29", ")")
    return encoded.lower()


def compute_check_mac_value(
    params: dict[str, str], hash_key: str, hash_iv: str
) -> str:
    """Compute ECPay AIO CheckMacValue.

    Algorithm:
    1. Exclude 'CheckMacValue' from params.
    2. Sort remaining keys ascending (case-sensitive ASCII order).
    3. Build: HashKey=<key>&k1=v1&...&HashIV=<iv>
    4. Apply dotnet_url_encode to the entire string.
    5. SHA-256 → uppercase hex.
    """
    filtered = {k: v for k, v in params.items() if k != "CheckMacValue"}
    sorted_items = sorted(filtered.items(), key=lambda kv: kv[0])

    parts: list[str] = [f"HashKey={hash_key}"]
    for k, v in sorted_items:
        parts.append(f"{k}={v}")
    parts.append(f"HashIV={hash_iv}")

    raw = "&".join(parts)
    encoded = dotnet_url_encode(raw)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()
    log.debug("ecpay.check_mac_computed", raw_len=len(raw))
    return digest


# ---------------------------------------------------------------------------
# Trade number generator
# ---------------------------------------------------------------------------


def make_merchant_trade_no(user_id: int) -> str:
    """Generate a unique trade number ≤ 20 chars.

    Format: TW{user_id}{YYYYMMDDHHMMSS}{2-digit random}
    For large user_ids the timestamp portion is trimmed to stay ≤ 20 chars.
    """
    prefix = f"TW{user_id}"
    ts = datetime.now(UTC).strftime("%Y%m%d%H%M%S")  # 14 chars
    rand2 = "".join(random.choices(string.digits, k=2))
    candidate = f"{prefix}{ts}{rand2}"
    # Trim from timestamp end if somehow over 20 chars (user_id > 4 digits)
    if len(candidate) > 20:
        # Remove chars from timestamp tail first
        excess = len(candidate) - 20
        candidate = f"{prefix}{ts[excess:]}{rand2}"
    return candidate[:20]


# ---------------------------------------------------------------------------
# Form payload builder
# ---------------------------------------------------------------------------


def build_create_authcheck_payload(
    user_id: int, plan: str, *, settings
) -> dict[str, str]:
    """Build the hidden-form fields to POST to ECPay AIO V5.

    Raises KeyError if plan is unknown.
    Returns a dict where every value is a str, ready for Jinja2 rendering.
    The returned dict includes CheckMacValue as the last field.
    """
    plan_cfg = PLANS[plan]  # raises KeyError for unknown plan

    merchant_trade_no = make_merchant_trade_no(user_id)
    trade_date = datetime.now(UTC).strftime("%Y/%m/%d %H:%M:%S")

    ecpay_url = (
        ECPAY_PROD_URL if getattr(settings, "env", "dev") == "prod" else ECPAY_STAGE_URL
    )

    fields: dict[str, str] = {
        "MerchantID": settings.ecpay_merchant_id,
        "MerchantTradeNo": merchant_trade_no,
        "MerchantTradeDate": trade_date,
        "PaymentType": "aio",
        "TotalAmount": str(plan_cfg["amount"]),
        "TradeDesc": f"tenderwatch {plan} 訂閱",
        "ItemName": plan_cfg["item_name"],
        "ReturnURL": settings.ecpay_return_url,
        "ChoosePayment": "Credit",
        "EncryptType": "1",
        "ClientBackURL": settings.ecpay_client_back_url,
        "PeriodAmount": str(plan_cfg["amount"]),
        "PeriodType": plan_cfg["period_type"],
        "Frequency": str(plan_cfg["frequency"]),
        "ExecTimes": str(plan_cfg["exec_times"]),
        "PeriodReturnURL": settings.ecpay_return_url,
    }

    # CheckMacValue must be computed over all other fields and appended last
    fields["CheckMacValue"] = compute_check_mac_value(
        fields, settings.ecpay_hash_key, settings.ecpay_hash_iv
    )

    log.info(
        "ecpay.payload_built",
        user_id=user_id,
        plan=plan,
        trade_no=merchant_trade_no,
        ecpay_url=ecpay_url,
    )
    return fields
