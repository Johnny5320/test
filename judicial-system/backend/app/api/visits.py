"""走访记录 API — 路由层：收参 → service → 裸返回 data（信封由 middleware 包装）"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.core.logging_config import log_call
from app.schemas.common import Page, ok
from app.schemas.visit import VisitCreate, VisitQueryParams, VisitResponse, VisitUpdate
from app.services import visit_service

logger = logging.getLogger("judicial.api.visits")

router = APIRouter(prefix="/api/visits", tags=["走访记录"])


@router.post("", response_model=VisitResponse)
@log_call
def create_visit(data: VisitCreate, session: Session = Depends(get_session),
                 current_user: User = Depends(get_current_user)):
    """新增走访记录"""
    return visit_service.create_visit(session, data, editor=current_user.real_name)


@router.get("", response_model=Page[VisitResponse])
@log_call
def list_visits(params: VisitQueryParams = Depends(),
                session: Session = Depends(get_session),
                current_user: User = Depends(get_current_user)):
    """走访记录列表 — 按人员/季度/日期区间筛选"""
    return visit_service.list_visits(session, params)


# 定稿 §3.4：kebab 命名，且必须注册在 /{visit_id} 之前，否则被路径参数捕获
@router.get("/stats-quarterly")
@log_call
def get_visit_quarterly_stats(person_id: Optional[int] = None,
                              session: Session = Depends(get_session),
                              current_user: User = Depends(get_current_user)):
    """走访季度统计"""
    return visit_service.get_quarterly_stats(session, person_id)


@router.get("/calendar-stats")
@log_call
def get_visit_calendar_stats(year: Optional[int] = None, month: Optional[int] = None,
                             session: Session = Depends(get_session),
                             current_user: User = Depends(get_current_user)):
    """走访日历统计：指定月份的每日走访数、覆盖人数、逾期标记"""
    from datetime import date, timedelta
    from app.models.person import Person
    from app.models.visit import Visit
    from sqlalchemy import func
    from sqlmodel import select

    today = date.today()
    year = year or today.year
    month = month or today.month

    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    # 每日走访数
    daily_rows = session.exec(
        select(Visit.visit_date, func.count(Visit.id))
        .where(Visit.visit_date >= month_start, Visit.visit_date <= month_end)
        .group_by(Visit.visit_date)
    ).all()
    daily_map = {str(r[0]): r[1] for r in daily_rows}

    # 本月走访的不重复人数
    visited_count = session.exec(
        select(func.count()).select_from(
            select(Visit.person_id)
            .where(Visit.visit_date >= month_start, Visit.visit_date <= month_end)
            .distinct().subquery()
        )
    ).one()

    # 在帮总人数
    active_count = session.exec(
        select(func.count(Person.id)).where(
            Person.is_deleted == False, Person.status == "在帮")  # noqa: E712
    ).one()

    # 逾期人员（在帮且超过走访间隔）
    overdue_persons = []
    active_persons = session.exec(
        select(Person).where(Person.is_deleted == False, Person.status == "在帮")  # noqa: E712
    ).all()
    for p in active_persons:
        interval = p.visit_interval_days or 90
        if p.last_visit_date is None:
            ref_date = p.edu_start_date or (p.created_at.date() if p.created_at else today)
            days_since = (today - ref_date).days
        else:
            days_since = (today - p.last_visit_date).days
        if days_since > interval:
            overdue_persons.append({
                "person_id": p.id, "name": p.name,
                "days_overdue": days_since - interval,
                "last_visit": str(p.last_visit_date) if p.last_visit_date else None,
            })

    coverage_rate = round(visited_count / active_count * 100, 1) if active_count > 0 else 0

    return {
        "year": year, "month": month,
        "daily_visits": daily_map,
        "visited_person_count": visited_count,
        "active_person_count": active_count,
        "coverage_rate": coverage_rate,
        "overdue_persons": sorted(overdue_persons, key=lambda x: -x["days_overdue"]),
    }


@router.get("/{visit_id}", response_model=VisitResponse)
@log_call
def get_visit(visit_id: int, session: Session = Depends(get_session),
              current_user: User = Depends(get_current_user)):
    """获取单条走访记录"""
    return visit_service.get_visit(session, visit_id)


@router.patch("/{visit_id}", response_model=VisitResponse)
@log_call
def update_visit(visit_id: int, data: VisitUpdate,
                 session: Session = Depends(get_session),
                 current_user: User = Depends(get_current_user)):
    """修改走访记录（PATCH exclude_unset，person_id 等不可变字段已物理删除）"""
    return visit_service.update_visit(session, visit_id, data, editor=current_user.real_name)


@router.delete("/{visit_id}")
@log_call
def delete_visit(visit_id: int, session: Session = Depends(get_session),
                 current_user: User = Depends(get_current_user)):
    """删除走访记录"""
    visit_service.delete_visit(session, visit_id)
    return ok(message="删除成功")
