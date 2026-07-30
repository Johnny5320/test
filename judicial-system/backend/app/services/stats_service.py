"""services/stats_service.py — 人员统计业务层
原 persons.py 区段下沉：stats_summary(169-300) / stats_trend(303-334) /
risk_score(337-400) / quarterly_report(484-589) / prisons(28-51)。
数值口径与原 SQL 完全一致（仅键名英文化）；修复点：
- quarterly_report 的 year/quarter 越界由 schema 层 ge/le 拦截（原 quarter=0/5 必现 500）
- 原 stats_summary:226-230 的 total_village 独立查询为死代码（返回值被
  len(village_distribution) 覆盖），直接以分布长度为准，行为不变。
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlmodel import Session, func, select

from app.models.person import Person
from app.models.visit import Visit
from app.schemas.common import BizError, ErrorCode
from app.schemas.person import PersonQueryParams
from app.schemas.stats import (NameCount, PeriodDistributions, PeriodReport,
                               PrisonItem, PrisonPersonItem, QuarterlyReport,
                               QuarterlyVisitStats, RiskFactor, RiskScoreResult,
                               StatsSummary, TrendPoint)

NOT_DELETED = Person.is_deleted == False  # noqa: E712

STATUS_KEY_MAP = {"在帮": "status_active", "已解除": "status_released",
                  "脱管": "status_missing", "重点关注": "status_focused"}  # 决议 F4 冻结
RISK_KEY_MAP = {"高": "risk_high", "中": "risk_medium", "低": "risk_low"}


# ---------- 汇总 / 趋势 ----------

def get_summary(session: Session) -> StatsSummary:
    """统计汇总：分组聚合取值与原逐值 count 数学等价"""
    today = date.today()
    month_start = today.replace(day=1)
    quarter_start = today.replace(month=(today.month - 1) // 3 * 3 + 1, day=1)
    status_counts = _group_counts(session, Person.status)
    risk_counts = _group_counts(session, Person.risk_level)
    village_distribution = _distribution(session, Person.village)
    return StatsSummary(
        total=_count(session, NOT_DELETED),
        total_prison=_count(session, NOT_DELETED, Person.prison_place != None,  # noqa: E711
                            Person.prison_place != ""),
        total_key_target=_count(session, NOT_DELETED, Person.is_key_target == True),  # noqa: E712
        total_minor=_count(session, NOT_DELETED, Person.is_minor == True),  # noqa: E712
        total_xj=_count(session, NOT_DELETED, Person.is_xj == True),  # noqa: E712
        total_mental=_count(session, NOT_DELETED, Person.is_mental == True),  # noqa: E712
        total_village=len(village_distribution),
        status_active=status_counts.get("在帮", 0),
        status_released=status_counts.get("已解除", 0),
        status_missing=status_counts.get("脱管", 0),
        status_focused=status_counts.get("重点关注", 0),
        risk_high=risk_counts.get("高", 0),
        risk_medium=risk_counts.get("中", 0),
        risk_low=risk_counts.get("低", 0),
        expiring_soon=_count(session, NOT_DELETED, Person.status == "在帮",
                             Person.edu_end_date != None,  # noqa: E711
                             Person.edu_end_date >= today,
                             Person.edu_end_date <= today + timedelta(days=90)),
        monthly_new=_count(session, NOT_DELETED, Person.created_at >=
                           datetime(month_start.year, month_start.month, 1)),
        quarterly_new=_count(session, NOT_DELETED, Person.created_at >=
                             datetime(quarter_start.year, quarter_start.month, 1)),
        responsible_distribution=_distribution(session, Person.responsible_person),
        prison_distribution=_distribution(session, Person.prison_place),
        village_distribution=village_distribution,
    )


def get_trend(months: int, session: Session) -> List[TrendPoint]:
    """最近 N 个月每月新增人数（算法与原 persons.py:310-334 一致）"""
    today = date.today()
    result: List[TrendPoint] = []
    for i in range(months - 1, -1, -1):
        year, month = today.year, today.month - i
        while month <= 0:
            month += 12
            year -= 1
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        cnt = _count(session, NOT_DELETED,
                     Person.created_at >= start, Person.created_at < end)
        result.append(TrendPoint(month=f"{year}-{month:02d}", count=cnt))
    return result


# ---------- 季度报表 ----------

def get_quarterly_report(year: Optional[int], quarter: Optional[int],
                         session: Session) -> QuarterlyReport:
    """季度报表（原 persons.py:484-589）；year/quarter 越界已由 schema 拦截"""
    today = date.today()
    year = year or today.year
    quarter = quarter or (today.month - 1) // 3 + 1
    q_start_month = (quarter - 1) * 3 + 1
    q_start = date(year, q_start_month, 1)
    q_end = (date(year, q_start_month + 3, 1) - timedelta(days=1)
             if quarter < 4 else date(year, 12, 31))
    start_dt = datetime(q_start.year, q_start.month, 1)
    end_dt = datetime(q_end.year, q_end.month, q_end.day, 23, 59, 59)
    existing = _count(session, NOT_DELETED, Person.created_at < start_dt)
    new_count = _count(session, NOT_DELETED, Person.created_at >= start_dt,
                       Person.created_at <= end_dt)
    current = _count(session, NOT_DELETED)
    active = _count(session, NOT_DELETED, Person.status == "在帮")
    in_quarter = (Visit.visit_date >= q_start) & (Visit.visit_date <= q_end)
    total_visits = _count_visits(session, in_quarter)
    visit_by_method = {m: _count_visits(session, in_quarter, Visit.visit_method == m)
                       for m in ("上门", "电话", "视频")}
    abnormal = _count_visits(session, in_quarter, Visit.has_abnormal == True)  # noqa: E712
    visited_persons = session.exec(
        select(func.count()).select_from(
            select(Visit.person_id).where(in_quarter).distinct().subquery())
    ).one()
    visit_rate = round(visited_persons / active * 100, 1) if active > 0 else 0
    return QuarterlyReport(
        year=year, quarter=quarter,
        period=f"{q_start.isoformat()} ~ {q_end.isoformat()}",
        existing_at_start=existing, new_this_quarter=new_count,
        current_total=current, active_count=active,
        visits=QuarterlyVisitStats(
            total=total_visits, onsite=visit_by_method["上门"],
            phone=visit_by_method["电话"], video=visit_by_method["视频"],
            abnormal=abnormal, completion_rate=visit_rate),
    )


def get_period_report(year: Optional[int], quarter: Optional[int],
                      month: Optional[int], session: Session) -> PeriodReport:
    """周期报表（按 年 / 年+季度 / 年+月份）：整页数据单一来源。
    人员分布口径 = 窗口内被走访(distinct person_id)的人员；趋势 = 所选年份 12 个月走访次数。
    """
    today = date.today()
    year = year or today.year
    # 计算窗口起止
    if month and 1 <= month <= 12:
        mode = "month"
        q_start = date(year, month, 1)
        q_end = date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        period = f"{year}年{month}月"
    elif quarter and 1 <= quarter <= 4:
        mode = "quarter"
        q_start_month = (quarter - 1) * 3 + 1
        q_start = date(year, q_start_month, 1)
        # 2026-07-29 修复：原条件写反——Q1~Q3 全算成 12-31（统计虚高），Q4 触发 date(year,13,1) 崩溃。
        # 正确边界：Q1=3/31, Q2=6/30, Q3=9/30, Q4=12/31。
        quarter_end_month = quarter * 3
        end_day = 30 if quarter_end_month in (6, 9) else 31
        q_end = date(year, quarter_end_month, end_day)
        period = f"{year}年第{quarter}季度"
    else:
        mode = "year"
        q_start = date(year, 1, 1)
        q_end = date(year, 12, 31)
        period = f"{year}年"
    start_dt = datetime(q_start.year, q_start.month, 1)
    end_dt = datetime(q_end.year, q_end.month, q_end.day, 23, 59, 59)

    # 人员计数
    existing = _count(session, NOT_DELETED, Person.created_at < start_dt)
    new_count = _count(session, NOT_DELETED, Person.created_at >= start_dt,
                       Person.created_at <= end_dt)
    active = _count(session, NOT_DELETED, Person.status == "在帮")
    current = _count(session, NOT_DELETED)

    # 窗口内走访
    in_window = (Visit.visit_date >= q_start) & (Visit.visit_date <= q_end)
    total_visits = _count_visits(session, in_window)
    visit_by_method = {m: _count_visits(session, in_window, Visit.visit_method == m)
                       for m in ("上门", "电话", "视频")}
    abnormal = _count_visits(session, in_window, Visit.has_abnormal == True)  # noqa: E712
    visited_persons = session.exec(
        select(func.count()).select_from(
            select(Visit.person_id).where(in_window).distinct().subquery())
    ).one()
    visit_rate = round(visited_persons / active * 100, 1) if active > 0 else 0

    # 窗口内被走访人员的分布
    visited_subq = select(Visit.person_id).where(in_window).distinct().subquery()
    status_counts = dict(session.exec(
        select(Person.status, func.count()).where(
            Person.id.in_(visited_subq), NOT_DELETED).group_by(Person.status)).all())
    risk_counts = dict(session.exec(
        select(Person.risk_level, func.count()).where(
            Person.id.in_(visited_subq), NOT_DELETED).group_by(Person.risk_level)).all())
    village_dist = [NameCount(name=r[0], count=r[1]) for r in session.exec(
        select(Person.village, func.count()).where(
            Person.id.in_(visited_subq), NOT_DELETED,
            Person.village != None, Person.village != "")  # noqa: E711
        .group_by(Person.village).order_by(func.count().desc())).all()]
    responsible_dist = [NameCount(name=r[0], count=r[1]) for r in session.exec(
        select(Person.responsible_person, func.count()).where(
            Person.id.in_(visited_subq), NOT_DELETED,
            Person.responsible_person != None, Person.responsible_person != "")  # noqa: E711
        .group_by(Person.responsible_person).order_by(func.count().desc())).all()]

    # 所选年份 12 个月月度走访趋势
    year_visits = (Visit.visit_date >= date(year, 1, 1)) & (Visit.visit_date <= date(year, 12, 31))
    trend_rows = session.exec(
        select(func.strftime("%Y-%m", Visit.visit_date), func.count())
        .where(year_visits).group_by(func.strftime("%Y-%m", Visit.visit_date))
    ).all()
    trend_map = {r[0]: r[1] for r in trend_rows}
    trend = [TrendPoint(month=f"{year}-{m:02d}", count=trend_map.get(f"{year}-{m:02d}", 0))
             for m in range(1, 13)]

    return PeriodReport(
        year=year, quarter=quarter or 0, month=month or 0, mode=mode, period=period,
        existing_at_start=existing, new_in_period=new_count,
        active_count=active, current_total=current,
        visited_person_count=visited_persons,
        visits=QuarterlyVisitStats(
            total=total_visits, onsite=visit_by_method["上门"],
            phone=visit_by_method["电话"], video=visit_by_method["视频"],
            abnormal=abnormal, completion_rate=visit_rate),
        distributions=PeriodDistributions(
            status_active=status_counts.get("在帮", 0),
            status_released=status_counts.get("已解除", 0),
            status_missing=status_counts.get("脱管", 0),
            status_focused=status_counts.get("重点关注", 0),
            risk_high=risk_counts.get("高", 0),
            risk_medium=risk_counts.get("中", 0),
            risk_low=risk_counts.get("低", 0),
            village_distribution=village_dist,
            responsible_distribution=responsible_dist),
        trend=trend,
    )


# ---------- 风险评分 ----------

def get_risk_score(person_id: int, session: Session) -> RiskScoreResult:
    """风险评分 0-100（算法与原 persons.py:337-400 逐行一致）"""
    person = session.get(Person, person_id)
    if not person or person.is_deleted:
        raise BizError(ErrorCode.PERSON_NOT_FOUND, "人员不存在")
    score = 0
    factors: List[RiskFactor] = []
    rw = {"高": 40, "中": 20, "低": 10}.get(person.risk_level, 0)
    score += rw
    factors.append(RiskFactor(type="risk_level", score=rw,
                              detail=f"风险等级：{person.risk_level}"))
    last_visit = session.exec(
        select(Visit).where(Visit.person_id == person_id)
        .order_by(Visit.visit_date.desc()).limit(1)
    ).first()
    today = date.today()
    if last_visit:
        days_since = (today - last_visit.visit_date).days
    elif person.edu_start_date:
        days_since = (today - person.edu_start_date).days
    else:
        days_since = (today - person.created_at.date()).days
    interval = person.visit_interval_days or 90
    if days_since > interval:
        overdue = days_since - interval
        vscore = min(30, 20 + overdue)
        score += vscore
        factors.append(RiskFactor(type="visit_overdue", score=vscore,
                                  detail=f"走访超期{overdue}天"))
    elif last_visit is None:
        score += 40
        factors.append(RiskFactor(type="visit_overdue", score=40, detail="从未走访"))
    if person.edu_end_date:
        days_remaining = (person.edu_end_date - today).days
        if days_remaining <= 0:
            score += 50
            factors.append(RiskFactor(type="expired", score=50,
                                      detail=f"已超期{abs(days_remaining)}天"))
        elif days_remaining <= 30:
            escore = max(5, 30 - days_remaining)
            score += escore
            factors.append(RiskFactor(type="expiring", score=escore,
                                      detail=f"剩余{days_remaining}天"))
    score = min(score, 100)
    level = "高风险" if score >= 60 else ("中风险" if score >= 30 else "低风险")
    return RiskScoreResult(person_id=person_id, score=score, level=level,
                           factors=factors)


# ---------- 监狱 ----------

def list_prisons(session: Session) -> List[PrisonItem]:
    """去重服刑场所及人数（原 persons.py:28-36）"""
    rows = session.exec(
        select(Person.prison_place, func.count())
        .where(NOT_DELETED, Person.prison_place != None, Person.prison_place != "")  # noqa: E711
        .group_by(Person.prison_place).order_by(func.count().desc())
    ).all()
    return [PrisonItem(name=r[0], count=r[1]) for r in rows]


def list_prison_persons(prison_name: str, session: Session) -> List[PrisonPersonItem]:
    """指定监狱的人员列表（原 persons.py:39-51）"""
    persons = session.exec(
        select(Person).where(NOT_DELETED, Person.prison_place == prison_name)
        .order_by(Person.name)
    ).all()
    return [PrisonPersonItem(id=p.id, name=p.name, id_card=p.id_card, status=p.status)
            for p in persons]


# ---------- export 专用筛选构建 ----------

def apply_export_filters(stmt, params: PersonQueryParams):
    """export 专用筛选：复制自 person_service._apply_filters（跨 agent，私有函数不可 import）
    TODO(集成): 与 person_service._apply_filters 收敛为公共函数后删除本函数"""
    if params.search:
        like = f"%{params.search}%"
        stmt = stmt.where(Person.name.like(like) | Person.id_card.like(like)
                          | Person.phone.like(like))
    if params.status:
        stmt = stmt.where(Person.status == params.status)
    if params.risk_level:
        stmt = stmt.where(Person.risk_level == params.risk_level)
    if params.responsible_person:
        stmt = stmt.where(Person.responsible_person == params.responsible_person)
    if params.crime_contains:
        stmt = stmt.where(Person.original_crime.contains(params.crime_contains))
    if params.village:
        stmt = stmt.where(Person.village == params.village)
    if params.prison_place:
        stmt = stmt.where(Person.prison_place == params.prison_place)
    for flag in ("is_key_target", "is_minor", "is_xj", "is_mental",
                 "has_drug_history", "is_recidivist"):
        value = getattr(params, flag)
        if value is not None:
            stmt = stmt.where(getattr(Person, flag) == value)
    if params.expiring_within_days is not None:
        today = date.today()
        stmt = stmt.where(Person.status == "在帮")
        stmt = stmt.where(Person.edu_end_date != None,  # noqa: E711
                          Person.edu_end_date >= today,
                          Person.edu_end_date <= today + timedelta(days=params.expiring_within_days))
    if params.expiring_overdue:
        today = date.today()
        stmt = stmt.where(Person.status == "在帮")
        stmt = stmt.where(Person.edu_end_date != None,  # noqa: E711
                          Person.edu_end_date < today)
    if params.min_age is not None:
        stmt = stmt.where(Person.birth_date != None,  # noqa: E711
                          Person.birth_date <= _shift_years(date.today(), -params.min_age))
    if params.max_age is not None:
        # 原语义：birth_date > today-(max_age+1)年（闰日安全）
        stmt = stmt.where(Person.birth_date != None,  # noqa: E711
                          Person.birth_date > _shift_years(date.today(), -params.max_age - 1))
    if params.ids_str:
        try:
            ids = [int(x.strip()) for x in params.ids_str.split(",") if x.strip()]
            if ids:
                stmt = stmt.where(Person.id.in_(ids))
        except ValueError:
            pass
    return stmt


def _shift_years(d: date, years: int) -> date:
    """闰日安全平移（2/29 → 2/28），与 person_service 同款"""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


# ---------- 内部聚合工具 ----------

def _count(session: Session, *conditions) -> int:
    return session.exec(select(func.count(Person.id)).where(*conditions)).one()


def _count_visits(session: Session, *conditions) -> int:
    return session.exec(select(func.count(Visit.id)).where(*conditions)).one()


def _group_counts(session: Session, column) -> Dict[str, int]:
    rows = session.exec(
        select(column, func.count()).where(NOT_DELETED).group_by(column)).all()
    return {r[0]: r[1] for r in rows}


def _distribution(session: Session, column) -> List[NameCount]:
    rows = session.exec(
        select(column, func.count())
        .where(NOT_DELETED, column != None, column != "")  # noqa: E711
        .group_by(column).order_by(func.count().desc())
    ).all()
    return [NameCount(name=r[0], count=r[1]) for r in rows]
