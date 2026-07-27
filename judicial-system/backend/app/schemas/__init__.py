"""Pydantic 请求/响应模型 — 兼容层
按领域拆分后（common/person/visit/stats/import_），本文件做两件事：
1. re-export 各新模块，保持 `from app.schemas import Xxx` 统一入口可用
2. 暂存 auth/reminders 仍被直接引用的旧模型（后续迁入独立模块后删除）
"""
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

# ---- 新模块统一 re-export ----
from app.schemas.common import (  # noqa: F401
    BizError, Envelope, ErrorCode, FieldError, MAX_PAGE_SIZE, Page, PageParams, ok,
)
from app.schemas.person import *  # noqa: F401,F403
from app.schemas.visit import *  # noqa: F401,F403
from app.schemas.stats import *  # noqa: F401,F403
from app.schemas.import_ import *  # noqa: F401,F403


# ---- auth（api/auth.py 引用中，迁入 schemas/auth.py 前暂存） ----
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    force_change_password: bool = False  # 首次登录需改密码


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    username: str
    real_name: str
    role: str
    is_active: bool
    force_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


# ---- 提醒系统（api/reminders.py 引用中，迁入 schemas/reminder.py 前暂存） ----
class ExpiringPerson(BaseModel):
    """即将到期人员"""
    id: int
    name: str
    risk_level: str
    edu_end_date: date
    days_remaining: int  # 剩余天数（负数=已超期）
    level: str  # "30天" / "7天" / "已超期"


class OverdueVisitPerson(BaseModel):
    """超期未走访人员"""
    id: int
    name: str
    risk_level: str
    last_visit_date: Optional[date] = None
    days_since_visit: int  # 距上次走访天数
    visit_interval_days: int  # 应走访间隔
    overdue_days: int  # 超期天数


class RemindersSummary(BaseModel):
    """提醒汇总"""
    expiring_30d: int  # 30天内到期
    expiring_7d: int   # 7天内到期
    overdue_expired: int  # 已超期未处理
    visit_overdue: int  # 超期未走访
    quarter_deadline_days: int  # 距本季度归档截止天数
    quarter_deadline_date: str  # 归档截止日期
    expiring_list: List[ExpiringPerson]  # 即将到期人员详情
    visit_overdue_list: List[OverdueVisitPerson]  # 超期未走访详情
