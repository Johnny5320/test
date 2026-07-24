"""Pydantic 请求/响应模型"""
from pydantic import BaseModel, Field
from typing import Optional, List, Union
from datetime import date, datetime


# ========== 认证 ==========
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


# ========== 人员 ==========
class PersonCreate(BaseModel):
    """新增人员 — 必填字段"""
    name: str = Field(max_length=20)
    id_card: str = Field(max_length=18)
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    household_addr: Optional[str] = None
    current_addr: Optional[str] = None
    phone: Optional[str] = None
    original_crime: Optional[str] = None
    original_sentence: Optional[str] = None
    release_date: Optional[date] = None
    edu_start_date: Optional[date] = None
    edu_end_date: Optional[date] = None
    responsible_person: Optional[str] = None
    status: Optional[str] = "在帮"
    family_name: Optional[str] = None
    family_phone: Optional[str] = None
    marital_status: Optional[str] = None
    education_level: Optional[str] = None
    employment: Optional[str] = None
    employment_unit: Optional[str] = None
    health_status: Optional[str] = None
    has_housing: Optional[bool] = True
    has_drug_history: Optional[bool] = False
    is_recidivist: Optional[bool] = False
    risk_level: Optional[str] = "低"
    visit_interval_days: Optional[int] = None  # 不填时根据风险等级自动设置
    family_name2: Optional[str] = None
    family_phone2: Optional[str] = None
    has_subsidy: Optional[bool] = False
    economic_status: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    responsible_org: Optional[str] = None


class PersonUpdate(BaseModel):
    """修改人员 — 所有字段可选"""
    name: Optional[str] = None
    id_card: Optional[str] = None
    visit_interval_days: Optional[int] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    household_addr: Optional[str] = None
    current_addr: Optional[str] = None
    phone: Optional[str] = None
    original_crime: Optional[str] = None
    original_sentence: Optional[str] = None
    release_date: Optional[date] = None
    edu_start_date: Optional[date] = None
    edu_end_date: Optional[date] = None
    responsible_person: Optional[str] = None
    status: Optional[str] = None
    family_name: Optional[str] = None
    family_phone: Optional[str] = None
    marital_status: Optional[str] = None
    education_level: Optional[str] = None
    employment: Optional[str] = None
    employment_unit: Optional[str] = None
    health_status: Optional[str] = None
    has_housing: Optional[bool] = None
    has_drug_history: Optional[bool] = None
    is_recidivist: Optional[bool] = None
    risk_level: Optional[str] = None
    family_name2: Optional[str] = None
    family_phone2: Optional[str] = None
    has_subsidy: Optional[bool] = None
    economic_status: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    responsible_org: Optional[str] = None


class PersonResponse(BaseModel):
    """人员详情响应"""
    id: int
    name: str
    id_card: str
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    household_addr: Optional[str] = None
    current_addr: Optional[str] = None
    phone: Optional[str] = None
    original_crime: Optional[str] = None
    original_sentence: Optional[str] = None
    release_date: Optional[date] = None
    edu_start_date: Optional[date] = None
    edu_end_date: Optional[date] = None
    responsible_person: Optional[str] = None
    status: str
    risk_level: str
    visit_interval_days: int = 90
    family_name: Optional[str] = None
    family_phone: Optional[str] = None
    marital_status: Optional[str] = None
    education_level: Optional[str] = None
    employment: Optional[str] = None
    employment_unit: Optional[str] = None
    health_status: Optional[str] = None
    has_housing: Optional[bool] = None
    has_drug_history: Optional[bool] = None
    is_recidivist: Optional[bool] = None
    family_name2: Optional[str] = None
    family_phone2: Optional[str] = None
    has_subsidy: Optional[bool] = None
    economic_status: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    responsible_org: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ========== 走访 ==========
class VisitCreate(BaseModel):
    person_id: int
    visit_date: date
    visitor: str
    visit_method: str
    visit_location: Optional[str] = None
    companions: Optional[str] = None
    content: Optional[str] = None
    has_abnormal: bool = False
    abnormal_detail: Optional[str] = None


class VisitResponse(BaseModel):
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


# ========== 通用 ==========
class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int

class ApiResponse(BaseModel):
    code: str = "SUCCESS"
    message: str = "操作成功"
    data: Optional[Union[dict, list]] = None


# ========== 修改历史 ==========
class EditLogResponse(BaseModel):
    """修改记录响应"""
    id: int
    table_name: str
    record_id: int
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    editor: str
    edited_at: datetime


class ResponsibleDistribution(BaseModel):
    """责任人分布"""
    name: str
    count: int


class StatsSummary(BaseModel):
    """统计汇总"""
    total: int
    在帮: int
    已解除: int
    脱管: int
    重点关注: int
    risk_high: int
    risk_medium: int
    risk_low: int
    expiring_soon: int
    monthly_new: int = 0  # 本月新增
    quarterly_new: int = 0  # 本季度新增
    responsible_distribution: List[ResponsibleDistribution] = []


# ========== Excel 导入 ==========
class ImportErrorDetail(BaseModel):
    """导入错误详情"""
    row: int
    field: str
    message: str


class ImportResult(BaseModel):
    """导入结果"""
    success: bool
    total_rows: int
    imported: int
    skipped: int
    errors: List[ImportErrorDetail]


# ========== 提醒系统 ==========
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
