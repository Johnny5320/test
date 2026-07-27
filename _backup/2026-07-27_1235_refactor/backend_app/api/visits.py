"""走访记录 CRUD API"""
import logging
from app.core.logging_config import log_call
logger = logging.getLogger("judicial.api.visits")

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from datetime import datetime, timezone, date
from typing import Optional
import math

from app.core.database import get_session
from app.models.visit import Visit
from app.models.person import Person
from app.models.edit_log import EditLog
from app.schemas import VisitCreate, VisitResponse, PaginatedResponse, ApiResponse

router = APIRouter(prefix="/api/visits", tags=["走访记录"])


def get_quarter(d: date) -> str:
    """计算季度标记，如 2025-Q3"""
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


@router.post("", response_model=VisitResponse, status_code=201)
@log_call
def create_visit(
    data: VisitCreate,
    session: Session = Depends(get_session),
):
    """新增走访记录"""
    # 校验人员存在
    person = session.get(Person, data.person_id)
    if not person or person.is_deleted:
        raise HTTPException(status_code=404, detail="人员不存在")

    visit = Visit(
        **data.model_dump(),
        quarter=get_quarter(data.visit_date),
    )
    session.add(visit)
    session.commit()
    session.refresh(visit)
    return visit


@router.get("", response_model=PaginatedResponse)
@log_call
def list_visits(
    person_id: Optional[int] = None,
    quarter: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=2000),
    session: Session = Depends(get_session),
):
    """走访记录列表 — 支持按人员和季度筛选"""
    query = select(Visit)

    if person_id:
        query = query.where(Visit.person_id == person_id)
    if quarter:
        query = query.where(Visit.quarter == quarter)

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total = session.exec(count_query).one()

    # 分页+排序
    query = query.order_by(Visit.visit_date.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    visits = session.exec(query).all()

    return PaginatedResponse(
        items=[v.model_dump() for v in visits],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{visit_id}", response_model=VisitResponse)
@log_call
def get_visit(
    visit_id: int,
    session: Session = Depends(get_session),
):
    """获取单条走访记录"""
    visit = session.get(Visit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="走访记录不存在")
    return visit


@router.put("/{visit_id}", response_model=VisitResponse)
@log_call
def update_visit(
    visit_id: int,
    data: VisitCreate,
    session: Session = Depends(get_session),
):
    """修改走访记录"""
    visit = session.get(Visit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="走访记录不存在")

    for field, value in data.model_dump().items():
        setattr(visit, field, value)
    visit.quarter = get_quarter(data.visit_date)

    session.add(visit)
    session.commit()
    session.refresh(visit)
    return visit


@router.delete("/{visit_id}", response_model=ApiResponse)
@log_call
def delete_visit(
    visit_id: int,
    session: Session = Depends(get_session),
):
    """删除走访记录"""
    visit = session.get(Visit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="走访记录不存在")

    session.delete(visit)
    session.commit()
    return ApiResponse(message="删除成功")


@router.get("/stats/quarterly")
@log_call
def quarterly_stats(
    person_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    """走访季度统计"""
    current_quarter = get_quarter(date.today())

    query = select(Visit).where(Visit.quarter == current_quarter)
    if person_id:
        query = query.where(Visit.person_id == person_id)

    visits = session.exec(query).all()

    # 统计各方式走访数量
    stats = {
        "quarter": current_quarter,
        "total": len(visits),
        "上门": sum(1 for v in visits if v.visit_method == "上门"),
        "电话": sum(1 for v in visits if v.visit_method == "电话"),
        "视频": sum(1 for v in visits if v.visit_method == "视频"),
        "有异常": sum(1 for v in visits if v.has_abnormal),
    }
    return stats
