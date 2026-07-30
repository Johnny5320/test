"""api/persons.py — 人员路由层（瘦身重写，对照原 1088 行上帝文件）
职责仅限：声明参数 → 调 service → 返回 data（裸返回，信封由 core.middleware 包装）。
统计/导入导出/监狱/risk-score 端点已移至 persons_stats 域（Agent C 范围），不在本文件。
"""
from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.common import MAX_PAGE_SIZE, Page, ok

MAX_EDIT_LOG_ROWS = 5000  # 全局修改留痕查询行数上限
from app.schemas.person import (BatchIdsRequest, BatchResult, BatchRiskRequest,
                                BatchStatusRequest, EditLogResponse,
                                PersonCreate, PersonListResponse, PersonNameMapItem,
                                PersonQueryParams, PersonResponse, PersonUpdate)
from app.services import person_service

router = APIRouter(prefix="/api/persons", tags=["人员管理"])


# ---------- 固定段路由在前，/{person_id} 在后（防匹配歧义） ----------

@router.get("")
def list_persons(params: PersonQueryParams = Depends(),
                 session: Session = Depends(get_session),
                 current_user: User = Depends(get_current_user)) -> Page[PersonListResponse]:
    """人员列表：分页 + 筛选 + 排序"""
    return person_service.list_persons(params, session)


@router.get("/name-map")
def get_person_name_map(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user)) -> List[PersonNameMapItem]:
    """前端 nameCache 专用：不分页一次全量"""
    return person_service.get_person_name_map(session)


@router.post("")
def create_person(data: PersonCreate, session: Session = Depends(get_session),
                  current_user: User = Depends(get_current_user)):
    person = person_service.create_person(data, session, editor=current_user.real_name)
    return ok(person_service.to_response(person).model_dump(), "新增成功")


@router.post("/batch-delete")
def batch_delete_persons(body: BatchIdsRequest,
                         session: Session = Depends(get_session),
                         current_user: User = Depends(get_current_user)):
    result = person_service.batch_delete_persons(body.ids, session, editor=current_user.real_name)
    return ok(result.model_dump(), f"成功删除 {result.success_count} 条记录")


@router.post("/batch-update-status")
def batch_update_person_status(body: BatchStatusRequest,
                               session: Session = Depends(get_session),
                               current_user: User = Depends(get_current_user)):
    result = person_service.batch_update_status(body.ids, body.status, session, editor=current_user.real_name)
    return ok(result.model_dump(), f"已更新 {result.success_count} 条状态")


@router.post("/batch-update-risk")
def batch_update_person_risk(body: BatchRiskRequest,
                             session: Session = Depends(get_session),
                             current_user: User = Depends(get_current_user)):
    result = person_service.batch_update_risk(body.ids, body.risk_level, session, editor=current_user.real_name)
    return ok(result.model_dump(), f"已更新 {result.success_count} 条风险等级")


@router.get("/edit-log-editors")
def get_edit_log_editors(session: Session = Depends(get_session),
                         current_user: User = Depends(get_current_user)) -> List[str]:
    """获取所有操作人列表（用于修改历史筛选下拉）"""
    from app.models.edit_log import EditLog
    from sqlalchemy import distinct
    editors = session.exec(
        select(distinct(EditLog.editor)).where(EditLog.table_name == "persons")
    ).all()
    return [e for e in editors if e]


@router.get("/edit-log-stats")
def get_edit_log_stats(session: Session = Depends(get_session),
                       current_user: User = Depends(get_current_user)):
    """编辑日志统计：按操作人分组计数 + 最近30天日活动量"""
    from app.models.edit_log import EditLog
    from sqlalchemy import func
    from datetime import datetime, timedelta

    # 按操作人分组计数
    rows = session.exec(
        select(EditLog.editor, func.count(EditLog.id))
        .where(EditLog.table_name == "persons")
        .group_by(EditLog.editor)
        .order_by(func.count(EditLog.id).desc())
    ).all()
    operator_stats = [{"name": r[0] or "系统", "count": r[1]} for r in rows]

    # 最近30天日活动量
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_rows = session.exec(
        select(func.date(EditLog.edited_at), func.count(EditLog.id))
        .where(EditLog.table_name == "persons",
               EditLog.edited_at >= thirty_days_ago)
        .group_by(func.date(EditLog.edited_at))
        .order_by(func.date(EditLog.edited_at))
    ).all()
    daily_activity = [{"date": str(r[0]), "count": r[1]} for r in daily_rows]

    return {"operator_stats": operator_stats, "daily_activity": daily_activity}


@router.get("/all-edit-logs")
def list_all_edit_logs(editor: str = None, year_month: str = None,
                       session: Session = Depends(get_session),
                       current_user: User = Depends(get_current_user)) -> List[EditLogResponse]:
    """全局修改留痕：跨人员查询，支持按操作人和年月筛选"""
    from app.models.edit_log import EditLog
    stmt = select(EditLog).where(EditLog.table_name == "persons")
    if editor:
        stmt = stmt.where(EditLog.editor == editor)
    if year_month:
        stmt = stmt.where(EditLog.edited_at >= f"{year_month}-01")
        parts = year_month.split("-")
        y, m = int(parts[0]), int(parts[1])
        if m == 12:
            next_month = f"{y+1}-01-01"
        else:
            next_month = f"{y}-{m+1:02d}-01"
        stmt = stmt.where(EditLog.edited_at < next_month)
    logs = session.exec(stmt.order_by(EditLog.edited_at.desc()).limit(MAX_EDIT_LOG_ROWS)).all()
    return [EditLogResponse.model_validate(log) for log in logs]


# ---------- 路径参数路由最后 ----------

@router.get("/{person_id}")
def get_person(person_id: int,
               session: Session = Depends(get_session),
               current_user: User = Depends(get_current_user)) -> PersonResponse:
    return person_service.to_response(
        person_service.get_person_or_404(person_id, session))


@router.patch("/{person_id}")
def update_person(person_id: int, data: PersonUpdate,
                  session: Session = Depends(get_session),
                  current_user: User = Depends(get_current_user)):
    """修改人员：PATCH exclude_unset，自动留痕"""
    person = person_service.update_person(person_id, data, session)
    return ok(person_service.to_response(person).model_dump(), "保存成功")


@router.delete("/{person_id}")
def delete_person(person_id: int, session: Session = Depends(get_session),
                  current_user: User = Depends(get_current_user)):
    person_service.delete_person(person_id, session)
    return ok(None, "删除成功")


@router.get("/{person_id}/edit-logs")
def list_person_edit_logs(person_id: int,
                          editor: str = None,
                          year_month: str = None,
                          session: Session = Depends(get_session),
                          current_user: User = Depends(get_current_user)
                          ) -> List[EditLogResponse]:
    """人员修改历史：按时间倒序，支持按操作人和年月筛选"""
    return person_service.list_edit_logs(person_id, session, editor=editor, year_month=year_month)
