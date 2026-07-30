"""提醒系统 API"""
import logging
from app.core.logging_config import log_call
logger = logging.getLogger("judicial.api.reminders")

from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from datetime import date, timedelta
from typing import List, Optional

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.models.person import Person
from app.models.visit import Visit
from app.schemas import (
    DismissPerson, OverdueVisitPerson, VisitDueSoonPerson, RemindersSummary,
)

router = APIRouter(prefix="/api/reminders", tags=["提醒系统"])

# 临期未走访阈值：距下次应访日 ≤ 该天数且未超期
VISIT_DUE_SOON_DAYS = 15
# 2026-07-28 用户决议（方案1）：从未走访者须在帮教开始后 30 天内完成首访，
# 且应访日永远不晚于帮教截止日（封顶）；已有走访记录者维持原间隔逻辑。
FIRST_VISIT_DAYS = 30


def get_quarter_deadline(today: date = None) -> date:
    """计算本季度归档截止日期（每季度最后一个月的15日）"""
    if today is None:
        today = date.today()
    quarter = (today.month - 1) // 3 + 1
    deadline_month = quarter * 3  # 3/6/9/12月
    return date(today.year, deadline_month, 15)


def _visit_base_date(p: Person) -> date:
    """走访计时基准：有走访取最后走访日，否则取帮教起始日，再否则取创建日"""
    return p.last_visit_date or p.edu_start_date or p.created_at.date()


def _compute_visit_reminders(persons: List[Person], today: date):
    """统一基于 Person.last_visit_date 计算临期/超期未走访"""
    due_soon: List[VisitDueSoonPerson] = []
    overdue: List[OverdueVisitPerson] = []
    for p in persons:
        base_date = _visit_base_date(p)
        interval = p.visit_interval_days or 90
        if p.last_visit_date is None:
            # 首访规则：从未走访 → 帮教开始(或创建)后 FIRST_VISIT_DAYS 天内须首访
            due_date = base_date + timedelta(days=FIRST_VISIT_DAYS)
            # 封顶：应访日不得晚于帮教截止日（保证解除前至少被提醒一次走访）
            if p.edu_end_date and p.edu_end_date < due_date:
                due_date = p.edu_end_date
        else:
            due_date = base_date + timedelta(days=interval)
        delta = (due_date - today).days  # <0 超期；≥0 距应访日天数
        last = p.last_visit_date
        days_since = (today - (last or base_date)).days
        if delta < 0:
            overdue.append(OverdueVisitPerson(
                id=p.id, name=p.name, risk_level=p.risk_level,
                last_visit_date=last, days_since_visit=days_since,
                visit_interval_days=interval, overdue_days=-delta,
            ))
        elif 0 <= delta <= VISIT_DUE_SOON_DAYS:
            due_soon.append(VisitDueSoonPerson(
                id=p.id, name=p.name, risk_level=p.risk_level,
                last_visit_date=last, days_since_visit=days_since,
                visit_interval_days=interval, due_in_days=delta,
                due_date=due_date.isoformat(),
            ))
    due_soon.sort(key=lambda x: x.due_in_days)
    overdue.sort(key=lambda x: x.overdue_days, reverse=True)
    return due_soon, overdue


@router.get("", response_model=RemindersSummary)
@log_call
def get_reminders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """获取所有提醒汇总"""
    today = date.today()
    base = select(Person).where(Person.is_deleted == False, Person.status == "在帮")

    # === 即将解除（原"即将到期"）：帮教截止日期 edu_end_date 临近 ===
    deadline_30 = today + timedelta(days=30)
    deadline_7 = today + timedelta(days=7)

    dismiss_30_count = session.exec(
        select(func.count()).select_from(
            base.where(Person.edu_end_date != None,
                       Person.edu_end_date >= today,
                       Person.edu_end_date <= deadline_30).subquery())
    ).one()
    dismiss_7_count = session.exec(
        select(func.count()).select_from(
            base.where(Person.edu_end_date != None,
                       Person.edu_end_date >= today,
                       Person.edu_end_date <= deadline_7).subquery())
    ).one()

    # 已到期未解除（待办）：edu_end_date 已过但仍为在帮
    overdue_q = base.where(Person.edu_end_date != None, Person.edu_end_date < today)
    overdue_count = session.exec(
        select(func.count()).select_from(overdue_q.subquery())
    ).one()

    # 即将解除 + 已到期未解除 详情（未来30天内 + 已过期，按日期升序，过期在前）
    dismiss_all_q = base.where(Person.edu_end_date != None, Person.edu_end_date <= deadline_30)
    dismiss_persons = session.exec(dismiss_all_q.order_by(Person.edu_end_date.asc())).all()
    dismiss_list = []
    for p in dismiss_persons:
        days_remaining = (p.edu_end_date - today).days
        if days_remaining < 0:
            level = "到期拟解除"
        elif days_remaining <= 7:
            level = "7天"
        elif days_remaining <= 30:
            level = "30天"
        else:
            level = "正常"
        dismiss_list.append(DismissPerson(
            id=p.id, name=p.name, risk_level=p.risk_level,
            edu_end_date=p.edu_end_date, days_remaining=days_remaining,
            level=level,
        ))

    # === 走访频率提醒（临期 + 超期，统一基于 last_visit_date） ===
    all_active = session.exec(base).all()
    visit_due_soon_list, visit_overdue_list = _compute_visit_reminders(all_active, today)

    # === 季度归档提醒 ===
    quarter_deadline = get_quarter_deadline(today)
    quarter_deadline_days = (quarter_deadline - today).days

    return RemindersSummary(
        dismiss_30d=dismiss_30_count,
        dismiss_7d=dismiss_7_count,
        overdue_expired=overdue_count,
        visit_overdue=len(visit_overdue_list),
        visit_due_soon=len(visit_due_soon_list),
        quarter_deadline_days=max(quarter_deadline_days, 0),
        quarter_deadline_date=quarter_deadline.isoformat(),
        dismiss_list=dismiss_list,
        visit_overdue_list=visit_overdue_list,
        visit_due_soon_list=visit_due_soon_list,
    )
