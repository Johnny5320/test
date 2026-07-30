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
    real_name: str
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

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class CreateUserRequest(BaseModel):
    """管理员新增用户"""
    real_name: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=6, max_length=128)
    role: str = "clerk"  # clerk/deputy/director


class AdminResetPasswordRequest(BaseModel):
    """管理员重置用户密码"""
    user_id: int
    new_password: str = Field(min_length=6, max_length=128)


class UpdateUserRequest(BaseModel):
    """管理员编辑用户（PATCH 语义，只改传了的字段）"""
    real_name: Optional[str] = Field(None, min_length=1, max_length=20)
    role: Optional[str] = None
    is_active: Optional[bool] = None


# ---- 提醒系统（api/reminders.py 引用中，迁入 schemas/reminder.py 前暂存） ----
class DismissPerson(BaseModel):
    """即将解除人员（帮教截止日期 edu_end_date 临近；含已到期未解除）"""
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


class VisitDueSoonPerson(BaseModel):
    """临期未走访人员（距下次应访日 ≤ 阈值 且未超期）"""
    id: int
    name: str
    risk_level: str
    last_visit_date: Optional[date] = None
    days_since_visit: int  # 距上次走访天数（从未走访则距帮教起始）
    visit_interval_days: int  # 应走访间隔
    due_in_days: int  # 距下次应访日天数（≥0）
    due_date: str  # 下次应访日 ISO


class RemindersSummary(BaseModel):
    """提醒汇总"""
    dismiss_30d: int  # 30天内即将解除
    dismiss_7d: int   # 7天内即将解除
    overdue_expired: int  # 已到期未解除（待办）
    visit_overdue: int  # 超期未走访
    visit_due_soon: int  # 临期未走访
    quarter_deadline_days: int  # 距本季度归档截止天数
    quarter_deadline_date: str  # 归档截止日期
    dismiss_list: List[DismissPerson]  # 即将解除人员详情（含已到期）
    visit_overdue_list: List[OverdueVisitPerson]  # 超期未走访详情
    visit_due_soon_list: List[VisitDueSoonPerson]  # 临期未走访详情
