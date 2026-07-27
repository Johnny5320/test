"""api/persons.py — 人员路由层（瘦身重写，对照原 1088 行上帝文件）
职责仅限：声明参数 → 调 service → 返回 data（裸返回，信封由 core.middleware 包装）。
统计/导入导出/监狱/risk-score 端点已移至 persons_stats 域（Agent C 范围），不在本文件。
"""
from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.schemas.common import Page, ok
from app.schemas.person import (BatchIdsRequest, BatchResult, BatchRiskRequest,
                                BatchStatusRequest, EditLogResponse,
                                PersonCreate, PersonNameMapItem,
                                PersonQueryParams, PersonResponse, PersonUpdate)
from app.services import person_service

router = APIRouter(prefix="/api/persons", tags=["人员管理"])


# ---------- 固定段路由在前，/{person_id} 在后（防匹配歧义） ----------

@router.get("")
def list_persons(params: PersonQueryParams = Depends(),
                 session: Session = Depends(get_session)) -> Page[PersonResponse]:
    """人员列表：分页 + 筛选 + 排序"""
    return person_service.list_persons(params, session)


@router.get("/name-map")
def get_person_name_map(
        session: Session = Depends(get_session)) -> List[PersonNameMapItem]:
    """前端 nameCache 专用：不分页一次全量"""
    return person_service.get_person_name_map(session)


@router.post("")
def create_person(data: PersonCreate, session: Session = Depends(get_session)):
    person = person_service.create_person(data, session)
    return ok(PersonResponse.model_validate(person).model_dump(), "新增成功")


@router.post("/batch-delete")
def batch_delete_persons(body: BatchIdsRequest,
                         session: Session = Depends(get_session)):
    result = person_service.batch_delete_persons(body.ids, session)
    return ok(result.model_dump(), f"成功删除 {result.success_count} 条记录")


@router.post("/batch-update-status")
def batch_update_person_status(body: BatchStatusRequest,
                               session: Session = Depends(get_session)):
    result = person_service.batch_update_status(body.ids, body.status, session)
    return ok(result.model_dump(), f"已更新 {result.success_count} 条状态")


@router.post("/batch-update-risk")
def batch_update_person_risk(body: BatchRiskRequest,
                             session: Session = Depends(get_session)):
    result = person_service.batch_update_risk(body.ids, body.risk_level, session)
    return ok(result.model_dump(), f"已更新 {result.success_count} 条风险等级")


# ---------- 路径参数路由最后 ----------

@router.get("/{person_id}")
def get_person(person_id: int,
               session: Session = Depends(get_session)) -> PersonResponse:
    return PersonResponse.model_validate(
        person_service.get_person_or_404(person_id, session))


@router.patch("/{person_id}")
def update_person(person_id: int, data: PersonUpdate,
                  session: Session = Depends(get_session)):
    """修改人员：PATCH exclude_unset，自动留痕"""
    person = person_service.update_person(person_id, data, session)
    return ok(PersonResponse.model_validate(person).model_dump(), "保存成功")


@router.delete("/{person_id}")
def delete_person(person_id: int, session: Session = Depends(get_session)):
    person_service.delete_person(person_id, session)
    return ok(None, "删除成功")


@router.get("/{person_id}/edit-logs")
def list_person_edit_logs(person_id: int,
                          session: Session = Depends(get_session)
                          ) -> List[EditLogResponse]:
    """人员修改历史：按时间倒序"""
    return person_service.list_edit_logs(person_id, session)
