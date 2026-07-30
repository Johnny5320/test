"""统计域契约（替代 schemas/__init__.py 中的 StatsSummary 段）
依据 03-design.md §2 + 决议 F4：状态/风险键英文化（值仍是中文）。
键名冻结：status_active/status_released/status_missing/status_focused
         risk_high/risk_medium/risk_low —— 前端 STATS_KEYS 共享同一份，禁止错位。
对照原声明：StatsSummary(schemas/__init__.py:271-292) / NameCount(:260-262) /
PrisonItem(原 /prisons 端点返回 dict) / 季度报表(原 persons.py:573-589) /
风险评分(原 persons.py:400) —— 仅中文键改英文键，字段与语义全对齐。
"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class NameCount(BaseModel):
    """名称+计数（责任人/监狱/村居分布通用）"""
    model_config = ConfigDict(extra="forbid")

    name: str
    count: int


class StatsSummary(BaseModel):
    """统计汇总：除 4 个状态键英文化外，其余键与原 StatsSummary 完全一致"""
    model_config = ConfigDict(extra="forbid")

    total: int
    total_prison: int = 0
    total_key_target: int = 0
    total_minor: int = 0
    total_xj: int = 0
    total_mental: int = 0
    total_village: int = 0
    status_active: int      # 原"在帮"
    status_released: int    # 原"已解除"
    status_missing: int     # 原"脱管"
    status_focused: int     # 原"重点关注"
    risk_high: int
    risk_medium: int
    risk_low: int
    expiring_soon: int
    monthly_new: int = 0
    quarterly_new: int = 0
    responsible_distribution: List[NameCount] = []
    prison_distribution: List[NameCount] = []
    village_distribution: List[NameCount] = []


class TrendPoint(BaseModel):
    """月度趋势点（原 stats_trend 返回 {"month": "2025-01", "count": 3}）"""
    model_config = ConfigDict(extra="forbid")

    month: str
    count: int


class QuarterlyVisitStats(BaseModel):
    """季度走访统计：上门/电话/视频 三个中文键英文化，其余同原"""
    model_config = ConfigDict(extra="forbid")

    total: int
    onsite: int             # 原"上门"
    phone: int              # 原"电话"
    video: int              # 原"视频"
    abnormal: int
    completion_rate: float


class QuarterlyReport(BaseModel):
    """季度报表（字段与原 persons.py:573-589 返回 dict 全对齐）"""
    model_config = ConfigDict(extra="forbid")

    year: int
    quarter: int
    period: str
    existing_at_start: int
    new_this_quarter: int
    current_total: int
    active_count: int
    visits: QuarterlyVisitStats


class PeriodDistributions(BaseModel):
    """周期报表的人员分布：窗口内被走访(distinct person_id)人员的状态/风险/村居/责任人分布"""
    model_config = ConfigDict(extra="forbid")

    status_active: int      # 原"在帮"
    status_released: int    # 原"已解除"
    status_missing: int     # 原"脱管"
    status_focused: int     # 原"重点关注"
    risk_high: int
    risk_medium: int
    risk_low: int
    village_distribution: List[NameCount] = []
    responsible_distribution: List[NameCount] = []


class PeriodReport(BaseModel):
    """周期报表（按 年 / 年+季度 / 年+月份 筛选）：整页数据单一来源"""
    model_config = ConfigDict(extra="forbid")

    year: int
    quarter: int = 0           # 0 表示未按季度
    month: int = 0             # 0 表示未按月份
    mode: str                  # 'year' | 'quarter' | 'month'
    period: str                # 人类可读区间/标签
    existing_at_start: int     # 窗口开始前已在册（created_at < 窗口起点）
    new_in_period: int         # 窗口内新增（created_at 在窗口内）
    active_count: int          # 当前在帮（快照）
    current_total: int         # 当前总在册（快照）
    visited_person_count: int  # 窗口内被走访的 distinct 人数
    visits: QuarterlyVisitStats
    distributions: PeriodDistributions
    trend: List[TrendPoint]    # 所选年份 12 个月的月度走访次数


class RiskFactor(BaseModel):
    """风险因子（type 值为英文枚举，detail 为中文描述）"""
    model_config = ConfigDict(extra="forbid")

    type: str
    score: int
    detail: str


class RiskScoreResult(BaseModel):
    """风险评分结果（level 为中文值：高风险/中风险/低风险，保留不改）"""
    model_config = ConfigDict(extra="forbid")

    person_id: int
    score: int
    level: str
    factors: List[RiskFactor]


class PrisonItem(BaseModel):
    """服刑场所及人数（原 /prisons 端点返回 {"name", "count"}）"""
    model_config = ConfigDict(extra="forbid")

    name: str
    count: int


class PrisonPersonItem(BaseModel):
    """指定监狱的人员简表（原 /prisons/{name}/persons 返回字段全对齐）"""
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    id_card: str
    status: str
