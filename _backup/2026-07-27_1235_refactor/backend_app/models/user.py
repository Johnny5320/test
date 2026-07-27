"""用户模型"""
from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(max_length=50, unique=True, index=True)
    hashed_password: str
    real_name: str = Field(max_length=20)  # 真实姓名
    role: str = Field(default="clerk", max_length=20)  # clerk / deputy / director
    is_active: bool = Field(default=True)
    force_change_password: bool = Field(default=False)  # 首次登录强制改密码
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
