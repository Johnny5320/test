"""安置帮教人员模型 — 33个字段"""
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, timezone, date


class Person(SQLModel, table=True):
    __tablename__ = "persons"

    id: Optional[int] = Field(default=None, primary_key=True)

    # === 必填字段（14个）===
    name: str = Field(max_length=20, index=True)                    # 姓名
    id_card: str = Field(max_length=18, unique=True, index=True)    # 身份证号
    gender: Optional[str] = Field(default=None, max_length=2)       # 性别（从身份证推算）
    birth_date: Optional[date] = Field(default=None)                # 出生日期（从身份证推算）
    household_addr: Optional[str] = Field(default=None, max_length=200)  # 户籍地址
    current_addr: Optional[str] = Field(default=None, max_length=200)    # 现住址
    phone: Optional[str] = Field(default=None, max_length=20)       # 联系电话
    original_crime: Optional[str] = Field(default=None, max_length=100)  # 原罪名
    original_sentence: Optional[str] = Field(default=None, max_length=100)  # 原判刑期
    release_date: Optional[date] = Field(default=None)              # 释放日期
    edu_start_date: Optional[date] = Field(default=None)            # 帮教起始日期
    edu_end_date: Optional[date] = Field(default=None)              # 帮教截止日期
    responsible_person: Optional[str] = Field(default=None, max_length=20)  # 帮教责任人
    status: str = Field(default="在帮", max_length=20, index=True)   # 状态：在帮/已解除/脱管/重点关注

    # === 选填字段（19个）===
    family_name: Optional[str] = Field(default=None, max_length=20)     # 家属姓名
    family_phone: Optional[str] = Field(default=None, max_length=20)    # 家属电话
    marital_status: Optional[str] = Field(default=None, max_length=10)  # 婚姻状况
    education_level: Optional[str] = Field(default=None, max_length=20) # 文化程度
    employment: Optional[str] = Field(default=None, max_length=50)      # 就业情况
    employment_unit: Optional[str] = Field(default=None, max_length=100) # 就业单位
    health_status: Optional[str] = Field(default=None, max_length=50)   # 身体状况
    has_housing: Optional[bool] = Field(default=True)                    # 有无固定住所
    has_drug_history: Optional[bool] = Field(default=False)              # 有无吸毒史
    is_recidivist: Optional[bool] = Field(default=False)                 # 是否累犯
    risk_level: str = Field(default="低", max_length=4, index=True)     # 风险等级：高/中/低
    visit_interval_days: int = Field(default=90)  # 走访间隔天数（默认每季度）
    family_name2: Optional[str] = Field(default=None, max_length=20)    # 家属姓名2
    family_phone2: Optional[str] = Field(default=None, max_length=20)   # 家属电话2
    has_subsidy: Optional[bool] = Field(default=False)                   # 有无低保/救助
    economic_status: Optional[str] = Field(default=None, max_length=20)  # 家庭经济状况
    photo_path: Optional[str] = Field(default=None, max_length=500)     # 照片路径
    notes: Optional[str] = Field(default=None, max_length=2000)         # 备注
    category: Optional[str] = Field(default=None, max_length=50)        # 类别（安置帮教/社区矫正等）
    responsible_org: Optional[str] = Field(default=None, max_length=100) # 责任单位/司法所

    # === 系统字段 ===
    is_deleted: bool = Field(default=False, index=True)  # 软删除
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
