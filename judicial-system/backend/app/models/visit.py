"""走访记录模型"""
from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone, date


class Visit(SQLModel, table=True):
    __tablename__ = "visits"

    id: Optional[int] = Field(default=None, primary_key=True)
    person_id: int = Field(foreign_key="persons.id", index=True)

    visit_date: date                                              # 走访日期
    visitor: str = Field(max_length=20)                           # 走访人
    visit_method: str = Field(max_length=20)                      # 方式：上门/电话/视频
    visit_location: Optional[str] = Field(default=None, max_length=200)  # 地点
    companions: Optional[str] = Field(default=None, max_length=200)      # 在场人员
    content: Optional[str] = Field(default=None, max_length=5000)        # 走访内容
    has_abnormal: bool = Field(default=False)                            # 有无异常
    abnormal_detail: Optional[str] = Field(default=None, max_length=2000) # 异常详情
    photo_paths: Optional[str] = Field(default=None, max_length=2000)    # 照片路径JSON
    quarter: str = Field(max_length=10)                                  # 季度标记 如 2025-Q3

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
