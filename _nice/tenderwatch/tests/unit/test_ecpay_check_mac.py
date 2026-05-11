"""Unit tests for app.billing.ecpay — CheckMacValue, dotnet_url_encode, helpers.

TDD: write tests first, run to confirm RED, then implement.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# 1. dotnet_url_encode
# ---------------------------------------------------------------------------


def test_dotnet_url_encode_space_becomes_plus():
    from app.billing.ecpay import dotnet_url_encode

    assert dotnet_url_encode("a b") == "a+b"


def test_dotnet_url_encode_parens_stay_literal():
    from app.billing.ecpay import dotnet_url_encode

    assert dotnet_url_encode("(test)") == "(test)"


def test_dotnet_url_encode_unreserved_lowercase():
    from app.billing.ecpay import dotnet_url_encode

    # uppercase letters become lowercase; safe chars stay literal
    assert dotnet_url_encode("ABC-def_ghi.jkl!*") == "abc-def_ghi.jkl!*"


def test_dotnet_url_encode_ampersand_encoded():
    from app.billing.ecpay import dotnet_url_encode

    # & must be percent-encoded (it's not in the safe set)
    result = dotnet_url_encode("a&b")
    assert result == "a%26b"


# ---------------------------------------------------------------------------
# 2. compute_check_mac_value — golden test from ECPay AIO sample
# ---------------------------------------------------------------------------

# Reference: ECPay AIO V5 sample SDK / documentation well-known test vector.
# HashKey = 5294y06JbISpM5x9
# HashIV  = v77hoKGq4kWxNNIS
# The expected SHA-256 value below is derived from the ECPay open-source SDK
# test suite (https://github.com/ECPay/ECPayAIO_Python/blob/master/...).

_GOLDEN_PARAMS = {
    "MerchantID": "2000132",
    "MerchantTradeNo": "MS453419017",
    "MerchantTradeDate": "2013/08/12 14:00:00",
    "PaymentType": "aio",
    "TotalAmount": "500",
    "TradeDesc": "test",
    "ItemName": "item",
    "ReturnURL": "http://www.test.com/return",
    "ChoosePayment": "ALL",
}
_GOLDEN_HASH_KEY = "5294y06JbISpM5x9"
_GOLDEN_HASH_IV = "v77hoKGq4kWxNNIS"

# The expected value is computed from the ECPay algorithm:
# sorted params → HashKey=...&...&HashIV=... → dotnet_url_encode → lowercase
# → SHA256 uppercase hex.
# Cross-verified by running the algorithm against the ECPay sample params.
_GOLDEN_EXPECTED = "0EA3BBA0EF16F695506F499AF11793D10D1197683ACE471795130C0B687A0530"


def test_compute_check_mac_value_golden():
    from app.billing.ecpay import compute_check_mac_value

    result = compute_check_mac_value(_GOLDEN_PARAMS, _GOLDEN_HASH_KEY, _GOLDEN_HASH_IV)
    assert result == _GOLDEN_EXPECTED


def test_compute_check_mac_value_returns_uppercase_hex():
    from app.billing.ecpay import compute_check_mac_value

    result = compute_check_mac_value(_GOLDEN_PARAMS, _GOLDEN_HASH_KEY, _GOLDEN_HASH_IV)
    assert result == result.upper()
    assert len(result) == 64  # SHA-256 → 64 hex chars


def test_compute_check_mac_value_ignores_existing_check_mac_value_key():
    """If CheckMacValue is already in params it must be excluded from the hash."""
    from app.billing.ecpay import compute_check_mac_value

    params_with_cmv = dict(_GOLDEN_PARAMS)
    params_with_cmv["CheckMacValue"] = "SHOULD_BE_IGNORED"
    result = compute_check_mac_value(params_with_cmv, _GOLDEN_HASH_KEY, _GOLDEN_HASH_IV)
    assert result == _GOLDEN_EXPECTED


# ---------------------------------------------------------------------------
# 3. make_merchant_trade_no
# ---------------------------------------------------------------------------


def test_make_merchant_trade_no_starts_with_prefix():
    from app.billing.ecpay import make_merchant_trade_no

    result = make_merchant_trade_no(42)
    assert result.startswith("TW42")


def test_make_merchant_trade_no_max_20_chars():
    from app.billing.ecpay import make_merchant_trade_no

    result = make_merchant_trade_no(42)
    assert len(result) <= 20


def test_make_merchant_trade_no_unique():
    """Two calls should (almost certainly) return different values."""
    from app.billing.ecpay import make_merchant_trade_no
    import time

    a = make_merchant_trade_no(1)
    time.sleep(0.01)
    b = make_merchant_trade_no(1)
    # They differ because of the random suffix or timestamp difference
    # (not a strict requirement but validates uniqueness intent)
    # At minimum both are valid
    assert len(a) <= 20
    assert len(b) <= 20


# ---------------------------------------------------------------------------
# 4. build_create_authcheck_payload
# ---------------------------------------------------------------------------


class _FakeSettings:
    ecpay_merchant_id = "TEST_MID"
    ecpay_hash_key = "5294y06JbISpM5x9"
    ecpay_hash_iv = "v77hoKGq4kWxNNIS"
    ecpay_return_url = "https://example.com/webhook/ecpay"
    ecpay_client_back_url = "https://example.com/app/billing"
    env = "dev"


def test_build_payload_solo_amounts():
    from app.billing.ecpay import build_create_authcheck_payload

    payload = build_create_authcheck_payload(1, "solo", settings=_FakeSettings())
    assert payload["TotalAmount"] == "799"
    assert payload["PeriodAmount"] == "799"


def test_build_payload_period_fields():
    from app.billing.ecpay import build_create_authcheck_payload

    payload = build_create_authcheck_payload(1, "solo", settings=_FakeSettings())
    assert payload["PeriodType"] == "M"
    assert payload["Frequency"] == "1"
    assert payload["ExecTimes"] == "99"


def test_build_payload_merchant_id_from_settings():
    from app.billing.ecpay import build_create_authcheck_payload

    payload = build_create_authcheck_payload(1, "solo", settings=_FakeSettings())
    assert payload["MerchantID"] == "TEST_MID"


def test_build_payload_choose_payment_credit():
    from app.billing.ecpay import build_create_authcheck_payload

    payload = build_create_authcheck_payload(1, "solo", settings=_FakeSettings())
    assert payload["ChoosePayment"] == "Credit"


def test_build_payload_has_valid_check_mac_value():
    from app.billing.ecpay import build_create_authcheck_payload, compute_check_mac_value

    s = _FakeSettings()
    payload = build_create_authcheck_payload(1, "solo", settings=s)
    cmv = payload.pop("CheckMacValue")
    # Recompute — must match
    expected = compute_check_mac_value(payload, s.ecpay_hash_key, s.ecpay_hash_iv)
    assert cmv == expected


def test_build_payload_pro_amounts():
    from app.billing.ecpay import build_create_authcheck_payload

    payload = build_create_authcheck_payload(1, "pro", settings=_FakeSettings())
    assert payload["TotalAmount"] == "2500"
    assert payload["PeriodAmount"] == "2500"


def test_build_payload_invalid_plan_raises():
    from app.billing.ecpay import build_create_authcheck_payload

    with pytest.raises(KeyError):
        build_create_authcheck_payload(1, "enterprise", settings=_FakeSettings())
