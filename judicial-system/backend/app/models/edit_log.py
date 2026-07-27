"""修改留痕模型"""
from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone


class EditLog(SQLModel, table=True):
    __tablename__ = "edit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    table_name: str = Field(max_length=50)      # 哪张表
    record_id: int                               # 哪条记录
    field_name: str = Field(max_length=50)       # 哪个字段
    old_value: Optional[str] = Field(default=None, max_length=2000)  # 原值
    new_value: Optional[str] = Field(default=None, max_length=2000)  # 新值
    editor: str = Field(max_length=50)           # 修改人
    edited_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
