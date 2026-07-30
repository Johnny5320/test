"""人员领域契约（替代 schemas/__init__.py 中的 Person 段）
依据 03-design.md §2/§4：Create/Update 分离、Update 全 Optional、全部 extra="forbid"。
字段与原 schemas/__init__.py:36-230 的 PersonCreate/PersonUpdate/PersonResponse 全对齐，
另补模型已有但响应未含的 risk_score / last_visit_date（N+1 消除所需的冗余字段）。
"""
import re
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.schemas.common import PageParams

# ---------- 枚举（值仍是中文，键全英文） ----------

PersonStatus = Literal["在帮", "已解除", "脱管", "重点关注"]
RiskLevel = Literal["高", "中", "低"]
SortOrder = Literal["asc", "desc"]

# 排序白名单收编为资源级常量（原 persons.py:73 正则白名单 + 设计新增可排序列）
PERSON_SORT_FIELDS = ("name", "id_card", "status", "risk_level", "edu_end_date",
                      "created_at", "updated_at", "release_date", "risk_score",
                      "last_visit_date")
PersonSortField = Literal["name", "id_card", "status", "risk_level", "edu_end_date",
                          "created_at", "updated_at", "release_date", "risk_score",
                          "last_visit_date"]


def _check_id_card_format(v: str) -> str:
    """schema 只做格式校验；校验位算法统一在 utils/id_card，由 service 层调用"""
    if not re.match(r"^\d{17}[\dXx]$", v):
        raise ValueError("身份证号必须是18位，前17位为数字，最后一位可为数字或X")
    return v.upper()


# ---------- 写入模型（Create/Update 分离；Update 物理删除不可变字段） ----------

class PersonCreate(BaseModel):
    """新增人员：必填 name + id_card，其余可选（字段与原 PersonCreate 全对齐）"""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=20)
    id_card: str = Field(min_length=18, max_length=18)
    editor: Optional[str] = Field(default=None, max_length=50)
    gender: Optional[str] = Field(default=None, max_length=2)
    birth_date: Optional[date] = None
    household_province: Optional[str] = Field(default=None, max_length=20)
    household_city: Optional[str] = Field(default=None, max_length=20)
    household_district: Optional[str] = Field(default=None, max_length=30)
    household_town: Optional[str] = Field(default=None, max_length=30)
    household_addr: Optional[str] = Field(default=None, max_length=200)
    current_addr: Optional[str] = Field(default=None, max_length=200)
    village: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=20,
                                 pattern=r"^1\d{10}$|^0\d{2,3}-?\d{7,8}$")
    original_crime: Optional[str] = Field(default=None, max_length=100)
    original_sentence: Optional[str] = Field(default=None, max_length=100)
    prison_place: Optional[str] = Field(default=None, max_length=100)
    sentence_start_date: Optional[date] = None
    release_date: Optional[date] = None
    edu_start_date: Optional[date] = None
    edu_end_date: Optional[date] = None
    responsible_person: Optional[str] = Field(default=None, max_length=20)
    status: PersonStatus = "在帮"
    is_key_target: Optional[bool] = False
    risk_level: RiskLevel = "低"
    visit_interval_days: Optional[int] = Field(default=90, ge=1, le=365)
    family_name: Optional[str] = Field(default=None, max_length=20)
    family_phone: Optional[str] = Field(default=None, max_length=20)
    family_name2: Optional[str] = Field(default=None, max_length=20)
    family_phone2: Optional[str] = Field(default=None, max_length=20)
    marital_status: Optional[str] = Field(default=None, max_length=10)
    education_level: Optional[str] = Field(default=None, max_length=20)
    employment: Optional[str] = Field(default=None, max_length=50)
    employment_unit: Optional[str] = Field(default=None, max_length=100)
    health_status: Optional[str] = Field(default=None, max_length=50)
    has_housing: Optional[bool] = True
    has_drug_history: Optional[bool] = False
    is_recidivist: Optional[bool] = False
    has_subsidy: Optional[bool] = False
    is_minor: Optional[bool] = False
    is_xj: Optional[bool] = False
    is_mental: Optional[bool] = False
    economic_status: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=2000)
    category: Optional[str] = Field(default=None, max_length=50)
    responsible_org: Optional[str] = Field(default=None, max_length=100)

    @field_validator("*", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v):
        """2026-07-28 修复：前端未填字段以 '' 提交，phone:'' 撞 pattern、日期 '' 撞 date 解析，
        导致「小猪」类最小填写被 10001 拒。空串/纯空白一律归一为 None（可选字段回落默认值）。"""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("id_card")
    @classmethod
    def _validate_id_card(cls, v: str) -> str:
        return _check_id_card_format(v)


class PersonUpdate(BaseModel):
    """修改人员：全 Optional + exclude_unset；无 id/created_at（物理不可变）"""
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=20)
    id_card: Optional[str] = Field(default=None, min_length=18, max_length=18)
    editor: Optional[str] = Field(default=None, max_length=50)
    gender: Optional[str] = Field(default=None, max_length=2)
    birth_date: Optional[date] = None
    household_province: Optional[str] = Field(default=None, max_length=20)
    household_city: Optional[str] = Field(default=None, max_length=20)
    household_district: Optional[str] = Field(default=None, max_length=30)
    household_town: Optional[str] = Field(default=None, max_length=30)
    household_addr: Optional[str] = Field(default=None, max_length=200)
    current_addr: Optional[str] = Field(default=None, max_length=200)
    village: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=20)
    original_crime: Optional[str] = Field(default=None, max_length=100)
    original_sentence: Optional[str] = Field(default=None, max_length=100)
    prison_place: Optional[str] = Field(default=None, max_length=100)
    sentence_start_date: Optional[date] = None
    release_date: Optional[date] = None
    edu_start_date: Optional[date] = None
    edu_end_date: Optional[date] = None
    responsible_person: Optional[str] = Field(default=None, max_length=20)
    status: Optional[PersonStatus] = None
    is_key_target: Optional[bool] = None
    risk_level: Optional[RiskLevel] = None
    visit_interval_days: Optional[int] = Field(default=None, ge=1, le=365)
    family_name: Optional[str] = Field(default=None, max_length=20)
    family_phone: Optional[str] = Field(default=None, max_length=20)
    family_name2: Optional[str] = Field(default=None, max_length=20)
    family_phone2: Optional[str] = Field(default=None, max_length=20)
    marital_status: Optional[str] = Field(default=None, max_length=10)
    education_level: Optional[str] = Field(default=None, max_length=20)
    employment: Optional[str] = Field(default=None, max_length=50)
    employment_unit: Optional[str] = Field(default=None, max_length=100)
    health_status: Optional[str] = Field(default=None, max_length=50)
    has_housing: Optional[bool] = None
    has_drug_history: Optional[bool] = None
    is_recidivist: Optional[bool] = None
    has_subsidy: Optional[bool] = None
    is_minor: Optional[bool] = None
    is_xj: Optional[bool] = None
    is_mental: Optional[bool] = None
    economic_status: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=2000)
    category: Optional[str] = Field(default=None, max_length=50)
    responsible_org: Optional[str] = Field(default=None, max_length=100)

    @field_validator("*", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v):
        """同 PersonCreate：空串/纯空白归一为 None，避免可选字段的 '' 撞 pattern/date 校验。"""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("id_card")
    @classmethod
    def _validate_id_card(cls, v: Optional[str]) -> Optional[str]:
        return _check_id_card_format(v) if v is not None else v


# ---------- 响应模型 ----------

class PersonListResponse(BaseModel):
    """人员列表响应：不含完整身份证号，仅含脱敏版（前6+****+后4）"""
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    name: str
    id_card_masked: Optional[str] = None  # 脱敏展示（前6+****+后4），列表专用，由 to_list_response() 填充
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    household_province: Optional[str] = None
    household_city: Optional[str] = None
    household_district: Optional[str] = None
    household_town: Optional[str] = None
    household_addr: Optional[str] = None
    current_addr: Optional[str] = None
    village: Optional[str] = None
    phone: Optional[str] = None
    original_crime: Optional[str] = None
    original_sentence: Optional[str] = None
    prison_place: Optional[str] = None
    sentence_start_date: Optional[date] = None
    release_date: Optional[date] = None
    edu_start_date: Optional[date] = None
    edu_end_date: Optional[date] = None
    responsible_person: Optional[str] = None
    status: str
    risk_level: str
    risk_score: Optional[int] = 0
    is_key_target: Optional[bool] = False
    visit_interval_days: int = 90
    family_name: Optional[str] = None
    family_phone: Optional[str] = None
    family_name2: Optional[str] = None
    family_phone2: Optional[str] = None
    marital_status: Optional[str] = None
    education_level: Optional[str] = None
    employment: Optional[str] = None
    employment_unit: Optional[str] = None
    health_status: Optional[str] = None
    has_housing: Optional[bool] = None
    has_drug_history: Optional[bool] = None
    is_recidivist: Optional[bool] = None
    has_subsidy: Optional[bool] = None
    is_minor: Optional[bool] = False
    is_xj: Optional[bool] = False
    is_mental: Optional[bool] = False
    economic_status: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    responsible_org: Optional[str] = None
    last_visit_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_status(self) -> str:
        """生效状态（派生，不落库）：在帮 且 帮教截止日已过 → 到期拟解除；否则同 status。
        「已解除」仍需人工确认（2026-07-28 决议：不自动改 status），此字段仅统一展示口径。"""
        if self.status == "在帮" and self.edu_end_date and self.edu_end_date < date.today():
            return "到期拟解除"
        return self.status


class PersonResponse(BaseModel):
    """人员详情响应：含完整身份证号（仅 detail 接口返回）+ risk_score + last_visit_date"""
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    name: str
    id_card: str
    id_card_masked: Optional[str] = None  # 脱敏展示（前6+****+后4）
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    household_province: Optional[str] = None
    household_city: Optional[str] = None
    household_district: Optional[str] = None
    household_town: Optional[str] = None
    household_addr: Optional[str] = None
    current_addr: Optional[str] = None
    village: Optional[str] = None
    phone: Optional[str] = None
    original_crime: Optional[str] = None
    original_sentence: Optional[str] = None
    prison_place: Optional[str] = None
    sentence_start_date: Optional[date] = None
    release_date: Optional[date] = None
    edu_start_date: Optional[date] = None
    edu_end_date: Optional[date] = None
    responsible_person: Optional[str] = None
    status: str
    risk_level: str
    risk_score: Optional[int] = 0
    is_key_target: Optional[bool] = False
    visit_interval_days: int = 90
    family_name: Optional[str] = None
    family_phone: Optional[str] = None
    family_name2: Optional[str] = None
    family_phone2: Optional[str] = None
    marital_status: Optional[str] = None
    education_level: Optional[str] = None
    employment: Optional[str] = None
    employment_unit: Optional[str] = None
    health_status: Optional[str] = None
    has_housing: Optional[bool] = None
    has_drug_history: Optional[bool] = None
    is_recidivist: Optional[bool] = None
    has_subsidy: Optional[bool] = None
    is_minor: Optional[bool] = False
    is_xj: Optional[bool] = False
    is_mental: Optional[bool] = False
    economic_status: Optional[str] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    responsible_org: Optional[str] = None
    last_visit_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_status(self) -> str:
        """生效状态（派生，不落库）：在帮 且 帮教截止日已过 → 到期拟解除；否则同 status。
        「已解除」仍需人工确认（2026-07-28 决议：不自动改 status），此字段仅统一展示口径。"""
        if self.status == "在帮" and self.edu_end_date and self.edu_end_date < date.today():
            return "到期拟解除"
        return self.status


class EditLogResponse(BaseModel):
    """修改记录响应（字段与原 schemas/__init__.py:242-251 对齐）"""
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    table_name: str
    record_id: int
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    editor: str
    edited_at: datetime


class PersonNameMapItem(BaseModel):
    """name-map 端点专用：不分页，只出 id+name"""
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str


# ---------- 查询参数（Depends 参数类，替代 17 个 Query 平铺） ----------

class PersonQueryParams(PageParams):
    """list/export 共用同一参数对象；筛选字段与原 persons.py:57-117 全对齐"""
    search: Optional[str] = None                # 姓名/身份证/电话模糊
    status: Optional[PersonStatus] = None
    risk_level: Optional[RiskLevel] = None
    responsible_person: Optional[str] = None
    crime_contains: Optional[str] = None        # 原罪名模糊
    village: Optional[str] = None
    prison_place: Optional[str] = None
    is_key_target: Optional[bool] = None        # 布尔传 true/false 字面量
    is_minor: Optional[bool] = None
    is_xj: Optional[bool] = None
    is_mental: Optional[bool] = None
    has_drug_history: Optional[bool] = None
    is_recidivist: Optional[bool] = None
    min_age: Optional[int] = Field(default=None, ge=0, le=150)
    max_age: Optional[int] = Field(default=None, ge=0, le=150)
    expiring_within_days: Optional[int] = Field(default=None, ge=1, le=365)
    expiring_overdue: Optional[bool] = None  # 已到期未解除（在帮且帮教截止日已过）
    ids_str: Optional[str] = None  # 仪表盘快捷跳转：逗号分隔的 ID 列表，如 "1,5,23"
    sort_by: PersonSortField = "updated_at"
    sort_order: SortOrder = "desc"


# ---------- 批量接口（显式模型，废除 body:dict） ----------

BATCH_MAX_IDS = 100


class BatchIdsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: List[int] = Field(min_length=1, max_length=BATCH_MAX_IDS)
    editor: Optional[str] = Field(default=None, max_length=50)


class BatchStatusRequest(BatchIdsRequest):
    status: PersonStatus


class BatchRiskRequest(BatchIdsRequest):
    risk_level: RiskLevel


class BatchFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    code: int
    message: str


class BatchResult(BaseModel):
    """批量部分成功结构化结果：前端弹失败名单用"""
    model_config = ConfigDict(extra="forbid")

    success_count: int
    failed_count: int
    failures: List[BatchFailure] = []
