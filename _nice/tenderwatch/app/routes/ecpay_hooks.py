"""ECPay AIO webhook endpoint.

POST /webhook/ecpay — receives application/x-www-form-urlencoded from ECPay.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.billing.webhooks import apply_callback, verify_callback
from app.config import get_settings

log = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/webhook/ecpay", response_class=PlainTextResponse)
async def ecpay_webhook(request: Request) -> str:
    """Receive ECPay payment notification.

    Verifies CheckMacValue, then updates the Subscription status.
    ECPay requires the response body to be exactly '1|OK' on success,
    or '0|<reason>' on failure.
    """
    settings = get_settings()
    form = await request.form()
    form_data: dict[str, str] = {k: str(v) for k, v in form.items()}

    log.info(
        "ecpay.webhook.received",
        trade_no=form_data.get("MerchantTradeNo"),
        rtn_code=form_data.get("RtnCode"),
    )

    if not verify_callback(form_data, settings.ecpay_hash_key, settings.ecpay_hash_iv):
        return "0|InvalidCheckMacValue"

    apply_callback(form_data)
    return "1|OK"
