"""预警记录模型"""
from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone


class Warning(SQLModel, table=True):
    __tablename__ = "warnings"

    id: Optional[int] = Field(default=None, primary_key=True)
    person_id: int = Field(index=True)
    warning_type: str = Field(max_length=20)  # expiring / visit_overdue / risk / data_error
    priority: str = Field(max_length=10)       # high / medium / low
    message: str = Field(max_length=500)
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
