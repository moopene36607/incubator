"""Billing routes — checkout redirect and cancel.

GET  /billing/checkout?plan=solo|pro  — build ECPay form, insert pending sub
POST /billing/cancel                  — cancel active subscription
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from app.auth.session import require_user
from app.billing.ecpay import (
    ECPAY_PROD_URL,
    ECPAY_STAGE_URL,
    PLANS,
    build_create_authcheck_payload,
    make_merchant_trade_no,
)
from app.config import get_settings
from app.db import get_session
from app.models.subscription import Subscription
from app.models.user import User

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/billing")

templates = Jinja2Templates(directory="app/templates")


@router.get("/checkout")
def checkout(
    plan: str,
    request: Request,
    user: User = Depends(require_user),
):
    """Render an auto-submitting form that POSTs the user to ECPay.

    Also inserts a pending Subscription row so we can track the trade.
    """
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan!r}")

    settings = get_settings()
    plan_cfg = PLANS[plan]

    # Build ECPay payload (includes CheckMacValue)
    fields = build_create_authcheck_payload(user.id, plan, settings=settings)
    trade_no = fields["MerchantTradeNo"]

    # Insert a pending Subscription row
    with get_session() as sess:
        sub = Subscription(
            user_id=user.id,
            plan=plan,
            ecpay_merchant_trade_no=trade_no,
            ecpay_period_amount=plan_cfg["amount"],
            status="pending",
        )
        sess.add(sub)
        sess.commit()

    ecpay_url = (
        ECPAY_PROD_URL if settings.env == "prod" else ECPAY_STAGE_URL
    )

    log.info(
        "billing.checkout_started",
        user_id=user.id,
        plan=plan,
        trade_no=trade_no,
    )

    return templates.TemplateResponse(
        request,
        "billing/checkout_redirect.html",
        {"ecpay_url": ecpay_url, "fields": fields},
    )


@router.post("/cancel")
def cancel(
    request: Request,
    user: User = Depends(require_user),
):
    """Mark the user's active subscription as cancelled."""
    from datetime import UTC, datetime

    with get_session() as sess:
        sub = sess.exec(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .where(Subscription.status == "active")
        ).first()

        if sub is not None:
            sub.status = "cancelled"
            sub.cancelled_at = datetime.now(UTC)
            sess.add(sub)
            sess.commit()
            log.info("billing.cancelled", user_id=user.id, sub_id=sub.id)
        else:
            log.info("billing.cancel_no_active_sub", user_id=user.id)

    return RedirectResponse(url="/app/billing", status_code=302)
