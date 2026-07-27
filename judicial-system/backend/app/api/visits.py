"""走访记录 API — 路由层：收参 → service → 裸返回 data（信封由 middleware 包装）"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.core.logging_config import log_call
from app.schemas.common import Page, ok
from app.schemas.visit import VisitCreate, VisitQueryParams, VisitResponse, VisitUpdate
from app.services import visit_service

logger = logging.getLogger("judicial.api.visits")

router = APIRouter(prefix="/api/visits", tags=["走访记录"])


@router.post("", response_model=VisitResponse)
@log_call
def create_visit(data: VisitCreate, session: Session = Depends(get_session)):
    """新增走访记录"""
    return visit_service.create_visit(session, data)


@router.get("", response_model=Page[VisitResponse])
@log_call
def list_visits(params: VisitQueryParams = Depends(),
                session: Session = Depends(get_session)):
    """走访记录列表 — 按人员/季度/日期区间筛选"""
    return visit_service.list_visits(session, params)


# 定稿 §3.4：kebab 命名，且必须注册在 /{visit_id} 之前，否则被路径参数捕获
@router.get("/stats-quarterly")
@log_call
def get_visit_quarterly_stats(person_id: Optional[int] = None,
                              session: Session = Depends(get_session)):
    """走访季度统计"""
    return visit_service.get_quarterly_stats(session, person_id)


@router.get("/{visit_id}", response_model=VisitResponse)
@log_call
def get_visit(visit_id: int, session: Session = Depends(get_session)):
    """获取单条走访记录"""
    return visit_service.get_visit(session, visit_id)


@router.patch("/{visit_id}", response_model=VisitResponse)
@log_call
def update_visit(visit_id: int, data: VisitUpdate,
                 session: Session = Depends(get_session)):
    """修改走访记录（PATCH exclude_unset，person_id 等不可变字段已物理删除）"""
    return visit_service.update_visit(session, visit_id, data)


@router.delete("/{visit_id}")
@log_call
def delete_visit(visit_id: int, session: Session = Depends(get_session)):
    """删除走访记录"""
    visit_service.delete_visit(session, visit_id)
    return ok(message="删除成功")
