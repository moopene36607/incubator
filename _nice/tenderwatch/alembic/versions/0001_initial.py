"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("line_user_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String, nullable=False),
        sa.Column("email", sa.String, nullable=True, index=True),
        sa.Column("plan", sa.String, nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "tenders",
        sa.Column("case_no", sa.String(64), primary_key=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("agency", sa.String, nullable=False),
        sa.Column("category", sa.String, nullable=False),
        sa.Column("budget_twd", sa.Integer, nullable=False),
        sa.Column("posted_date", sa.Date, nullable=False),
        sa.Column("deadline_date", sa.Date, nullable=False),
        sa.Column("description", sa.String, nullable=False, server_default=""),
        sa.Column("required_capital_twd", sa.Integer, nullable=False, server_default="0"),
        sa.Column("required_certs", sa.JSON, nullable=False),
        sa.Column("location", sa.String, nullable=False, server_default="全國"),
        sa.Column("raw_payload", sa.JSON, nullable=False),
        sa.Column("embedding", sa.JSON, nullable=True),
        sa.Column("fetched_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("company_name", sa.String, nullable=False),
        sa.Column("capital_twd", sa.Integer, nullable=False),
        sa.Column("employee_count", sa.Integer, nullable=False),
        sa.Column("capability_description", sa.String, nullable=False),
        sa.Column("min_tender_budget_twd", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_tender_budget_twd", sa.Integer, nullable=True),
        sa.Column("excluded_categories", sa.JSON, nullable=False),
        sa.Column("iso_certifications", sa.JSON, nullable=False),
        sa.Column("minimum_days_to_deadline", sa.Integer, nullable=False, server_default="7"),
        sa.Column("embedding", sa.JSON, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("profile_id", sa.Integer, sa.ForeignKey("profiles.id"), nullable=False),
        sa.Column("tender_case_no", sa.String(64), sa.ForeignKey("tenders.case_no"), nullable=False, index=True),
        sa.Column("passes_hard_filter", sa.Boolean, nullable=False),
        sa.Column("fail_reasons", sa.JSON, nullable=False),
        sa.Column("cosine_sim", sa.Float, nullable=True),
        sa.Column("llm_score", sa.Integer, nullable=True),
        sa.Column("llm_match_level", sa.String, nullable=True),
        sa.Column("llm_key_match_points", sa.JSON, nullable=False),
        sa.Column("llm_key_gaps", sa.JSON, nullable=False),
        sa.Column("llm_recommendation", sa.String, nullable=True),
        sa.Column("pushed_to_line", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("plan", sa.String, nullable=False),
        sa.Column("ecpay_merchant_trade_no", sa.String(64), nullable=False, unique=True),
        sa.Column("ecpay_period_amount", sa.Integer, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("next_charge_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("cancelled_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_table("matches")
    op.drop_table("profiles")
    op.drop_table("tenders")
    op.drop_table("users")
