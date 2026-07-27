"""走访领域契约：VisitCreate/Update/Response/QueryParams
依据 03-design.md §1/§3/§4：extra="forbid"；Update 全 Optional 且物理删除不可变字段。
"""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PageParams

VisitMethod = Literal["上门", "电话", "视频"]


class VisitCreate(BaseModel):
    """新增走访 — editor 可选，缺省 None（service 层兜底"司法所"，决议 F5 走访留痕）"""
    model_config = ConfigDict(extra="forbid")

    person_id: int
    visit_date: date
    visitor: str = Field(min_length=1, max_length=20)
    visit_method: VisitMethod
    visit_location: Optional[str] = Field(default=None, max_length=200)
    companions: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = Field(default=None, max_length=5000)
    has_abnormal: bool = False
    abnormal_detail: Optional[str] = Field(default=None, max_length=2000)
    editor: Optional[str] = None


class VisitUpdate(BaseModel):
    """修改走访 — 全 Optional；id/person_id/quarter/created_at 物理删除，不可篡改"""
    model_config = ConfigDict(extra="forbid")

    visit_date: Optional[date] = None
    visitor: Optional[str] = Field(default=None, min_length=1, max_length=20)
    visit_method: Optional[VisitMethod] = None
    visit_location: Optional[str] = Field(default=None, max_length=200)
    companions: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = Field(default=None, max_length=5000)
    has_abnormal: Optional[bool] = None
    abnormal_detail: Optional[str] = Field(default=None, max_length=2000)
    editor: Optional[str] = None


class VisitResponse(BaseModel):
    """走访响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    person_id: int
    visit_date: date
    visitor: str
    visit_method: str
    visit_location: Optional[str] = None
    companions: Optional[str] = None
    content: Optional[str] = None
    has_abnormal: bool
    abnormal_detail: Optional[str] = None
    quarter: str
    created_at: datetime


class VisitQueryParams(PageParams):
    """走访列表查询参数（Depends 参数类；page/page_size 继承 PageParams）"""
    person_id: Optional[int] = None
    visit_date_start: Optional[date] = None
    visit_date_end: Optional[date] = None
    quarter: Optional[str] = None
