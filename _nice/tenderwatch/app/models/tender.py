"""Tender table — one row per PCC OpenData announcement.

JSON columns (instead of Postgres ARRAY/JSONB) keep the schema portable to
SQLite for tests. Production uses Postgres; both engines treat JSON columns
identically from SQLModel's perspective.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Tender(SQLModel, table=True):
    __tablename__ = "tenders"

    case_no: str = Field(primary_key=True, max_length=64)
    title: str
    agency: str
    category: str
    budget_twd: int
    posted_date: date
    deadline_date: date
    description: str = ""
    required_capital_twd: int = 0
    required_certs: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    location: str = "全國"
    raw_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    embedding: list[float] | None = Field(default=None, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
