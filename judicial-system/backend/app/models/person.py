"""安置帮教人员模型"""
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, timezone, date


class Person(SQLModel, table=True):
    __tablename__ = "persons"

    id: Optional[int] = Field(default=None, primary_key=True)

    # === 基本信息 ===
    name: str = Field(max_length=20, index=True)                    # 姓名
    id_card: str = Field(max_length=18, unique=True, index=True)    # 身份证号
    gender: Optional[str] = Field(default=None, max_length=2)       # 性别
    birth_date: Optional[date] = Field(default=None)                # 出生日期
    household_province: Optional[str] = Field(default=None, max_length=20)  # 户籍省
    household_city: Optional[str] = Field(default=None, max_length=20)      # 户籍市
    household_district: Optional[str] = Field(default=None, max_length=30)  # 户籍县/区
    household_town: Optional[str] = Field(default=None, max_length=30)      # 户籍乡镇/街道
    household_addr: Optional[str] = Field(default=None, max_length=200)     # 户籍详细地址
    current_addr: Optional[str] = Field(default=None, max_length=200)       # 居住地址
    village: Optional[str] = Field(default=None, max_length=50, index=True) # 所属村委
    phone: Optional[str] = Field(default=None, max_length=20)       # 联系电话

    # === 帮教信息 ===
    original_crime: Optional[str] = Field(default=None, max_length=100)     # 原罪名
    original_sentence: Optional[str] = Field(default=None, max_length=100)  # 原判刑期
    prison_place: Optional[str] = Field(default=None, max_length=100, index=True)  # 服刑场所
    sentence_start_date: Optional[date] = Field(default=None)        # 服刑始日
    release_date: Optional[date] = Field(default=None)               # 释放日期
    edu_start_date: Optional[date] = Field(default=None)             # 帮教起始日期
    edu_end_date: Optional[date] = Field(default=None)               # 帮教截止日期
    responsible_person: Optional[str] = Field(default=None, max_length=20)  # 帮教责任人
    status: str = Field(default="在帮", max_length=20, index=True)   # 状态
    is_key_target: Optional[bool] = Field(default=False)             # 是否重点帮教对象
    category: Optional[str] = Field(default=None, max_length=50)     # 类别
    risk_level: str = Field(default="低", max_length=4, index=True)  # 风险等级

    # === 家庭/社会信息 ===
    family_name: Optional[str] = Field(default=None, max_length=20)
    family_phone: Optional[str] = Field(default=None, max_length=20)
    family_name2: Optional[str] = Field(default=None, max_length=20)
    family_phone2: Optional[str] = Field(default=None, max_length=20)
    marital_status: Optional[str] = Field(default=None, max_length=10)
    education_level: Optional[str] = Field(default=None, max_length=20)
    employment: Optional[str] = Field(default=None, max_length=50)
    employment_unit: Optional[str] = Field(default=None, max_length=100)
    health_status: Optional[str] = Field(default=None, max_length=50)
    economic_status: Optional[str] = Field(default=None, max_length=20)
    has_housing: Optional[bool] = Field(default=True)
    has_drug_history: Optional[bool] = Field(default=False)
    is_recidivist: Optional[bool] = Field(default=False)
    has_subsidy: Optional[bool] = Field(default=False)
    is_minor: Optional[bool] = Field(default=False)        # 是否未成年
    is_xj: Optional[bool] = Field(default=False)           # 是否xj
    is_mental: Optional[bool] = Field(default=False)       # 是否精神疾病
    visit_interval_days: int = Field(default=90)
    responsible_org: Optional[str] = Field(default=None, max_length=100)
    photo_path: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)

    # === 系统字段 ===
    is_deleted: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
