from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Match(SQLModel, table=True):
    __tablename__ = "matches"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    profile_id: int = Field(foreign_key="profiles.id")
    tender_case_no: str = Field(foreign_key="tenders.case_no", index=True)
    passes_hard_filter: bool
    fail_reasons: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    cosine_sim: float | None = None
    llm_score: int | None = None
    llm_match_level: str | None = None
    llm_key_match_points: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    llm_key_gaps: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    llm_recommendation: str | None = None
    pushed_to_line: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
