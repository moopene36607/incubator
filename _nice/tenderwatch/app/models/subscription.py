from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class Subscription(SQLModel, table=True):
    __tablename__ = "subscriptions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    plan: str  # solo | pro
    ecpay_merchant_trade_no: str = Field(max_length=64, unique=True)
    ecpay_period_amount: int  # NTD
    status: str  # active | failed | cancelled
    next_charge_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    cancelled_at: datetime | None = None
