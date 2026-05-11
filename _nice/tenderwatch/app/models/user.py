from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    line_user_id: str = Field(index=True, unique=True, max_length=64)
    display_name: str
    email: str | None = Field(default=None, index=True)
    plan: str = Field(default="free")  # free | solo | pro
    created_at: datetime = Field(default_factory=datetime.utcnow)
