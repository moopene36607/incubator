from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    company_name: str
    capital_twd: int
    employee_count: int
    capability_description: str  # free-form, embedded for semantic match
    min_tender_budget_twd: int = 0
    max_tender_budget_twd: int | None = None
    excluded_categories: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    iso_certifications: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    minimum_days_to_deadline: int = 7
    embedding: list[float] | None = Field(default=None, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=datetime.utcnow)
