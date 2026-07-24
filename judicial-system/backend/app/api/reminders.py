"""提醒系统 API"""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from datetime import date, timedelta
from typing import List

from app.core.database import get_session
from app.models.person import Person
from app.models.visit import Visit
from app.schemas import (
    ExpiringPerson, OverdueVisitPerson, RemindersSummary,
)
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/reminders", tags=["提醒系统"])


def get_quarter_deadline(today: date = None) -> date:
    """计算本季度归档截止日期（每季度最后一个月的15日）"""
    if today is None:
        today = date.today()
    quarter = (today.month - 1) // 3 + 1
    deadline_month = quarter * 3  # 3/6/9/12月
    return date(today.year, deadline_month, 15)


@router.get("", response_model=RemindersSummary)
def get_reminders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """获取所有提醒汇总"""
    today = date.today()
    base = select(Person).where(Person.is_deleted == False, Person.status == "在帮")

    # === 到期提醒 ===
    # 30天内到期
    deadline_30 = today + timedelta(days=30)
    expiring_30q = base.where(
        Person.edu_end_date != None,
        Person.edu_end_date >= today,
        Person.edu_end_date <= deadline_30,
    )
    expiring_30_count = session.exec(
        select(func.count()).select_from(expiring_30q.subquery())
    ).one()

    # 7天内到期
    deadline_7 = today + timedelta(days=7)
    expiring_7q = base.where(
        Person.edu_end_date != None,
        Person.edu_end_date >= today,
        Person.edu_end_date <= deadline_7,
    )
    expiring_7_count = session.exec(
        select(func.count()).select_from(expiring_7q.subquery())
    ).one()

    # 已超期（截止日期已过但仍为"在帮"）
    overdue_q = base.where(
        Person.edu_end_date != None,
        Person.edu_end_date < today,
    )
    overdue_count = session.exec(
        select(func.count()).select_from(overdue_q.subquery())
    ).one()

    # 即将到期人员详情（30天内，按日期排序）
    expiring_persons = session.exec(
        expiring_30q.order_by(Person.edu_end_date.asc())
    ).all()
    expiring_list = []
    for p in expiring_persons:
        days_remaining = (p.edu_end_date - today).days
        if days_remaining <= 7:
            level = "7天"
        elif days_remaining <= 30:
            level = "30天"
        else:
            level = "正常"
        expiring_list.append(ExpiringPerson(
            id=p.id, name=p.name, risk_level=p.risk_level,
            edu_end_date=p.edu_end_date, days_remaining=days_remaining,
            level=level,
        ))

    # === 走访频率提醒 ===
    all_active = session.exec(base).all()
    visit_overdue_list = []
    for p in all_active:
        # 查找最近一次走访
        last_visit = session.exec(
            select(Visit).where(Visit.person_id == p.id)
            .order_by(Visit.visit_date.desc())
            .limit(1)
        ).first()

        if last_visit:
            days_since = (today - last_visit.visit_date).days
        else:
            # 从未走访过，从帮教起始日期算
            if p.edu_start_date:
                days_since = (today - p.edu_start_date).days
            else:
                days_since = (today - p.created_at.date()).days

        interval = p.visit_interval_days or 90
        if days_since > interval:
            overdue_days = days_since - interval
            visit_overdue_list.append(OverdueVisitPerson(
                id=p.id, name=p.name, risk_level=p.risk_level,
                last_visit_date=last_visit.visit_date if last_visit else None,
                days_since_visit=days_since,
                visit_interval_days=interval,
                overdue_days=overdue_days,
            ))

    # 按超期天数排序
    visit_overdue_list.sort(key=lambda x: x.overdue_days, reverse=True)

    # === 季度归档提醒 ===
    quarter_deadline = get_quarter_deadline(today)
    quarter_deadline_days = (quarter_deadline - today).days

    return RemindersSummary(
        expiring_30d=expiring_30_count,
        expiring_7d=expiring_7_count,
        overdue_expired=overdue_count,
        visit_overdue=len(visit_overdue_list),
        quarter_deadline_days=max(quarter_deadline_days, 0),
        quarter_deadline_date=quarter_deadline.isoformat(),
        expiring_list=expiring_list,
        visit_overdue_list=visit_overdue_list,
    )
