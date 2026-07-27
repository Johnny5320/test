"""走访业务层：CRUD + quarter 计算 + person.last_visit_date 同步 + EditLog 留痕
事务边界：commit 只在本层（03-design.md §4.4）。
自含 _get_person_or_404，避免跨 agent 依赖 person_service。
"""
import math
from datetime import date
from typing import List, Optional, Tuple

from sqlmodel import Session, func, select

from app.models.edit_log import EditLog
from app.models.person import Person
from app.models.visit import Visit
from app.schemas.common import BizError, ErrorCode, Page
from app.schemas.visit import VisitCreate, VisitQueryParams, VisitResponse, VisitUpdate

DEFAULT_EDITOR = "司法所"

# 创建走访时纳入留痕的字段（photo_paths 暂无入口，不纳入）
_LOG_FIELDS = (
    "visit_date", "visitor", "visit_method", "visit_location",
    "companions", "content", "has_abnormal", "abnormal_detail",
)


def get_quarter(d: date) -> str:
    """计算季度标记，如 2025-Q3"""
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def _get_person_or_404(session: Session, person_id: int) -> Person:
    person = session.get(Person, person_id)
    if not person or person.is_deleted:
        raise BizError(ErrorCode.PERSON_NOT_FOUND, "人员不存在")
    return person


def _get_visit_or_404(session: Session, visit_id: int) -> Visit:
    visit = session.get(Visit, visit_id)
    if not visit:
        raise BizError(ErrorCode.VISIT_NOT_FOUND, "走访记录不存在")
    return visit


def _sync_last_visit_date(session: Session, person_id: int) -> None:
    """重算 person.last_visit_date = max(visit_date)（消除列表 N+1 的前提）"""
    person = session.get(Person, person_id)
    if not person:
        return
    person.last_visit_date = session.exec(
        select(func.max(Visit.visit_date)).where(Visit.person_id == person_id)
    ).one()
    session.add(person)


def _write_logs(session: Session, visit_id: int,
                diffs: List[Tuple[str, object, object]], editor: str) -> None:
    for field_name, old_value, new_value in diffs:
        session.add(EditLog(
            table_name="visits", record_id=visit_id, field_name=field_name,
            old_value=None if old_value is None else str(old_value),
            new_value=None if new_value is None else str(new_value),
            editor=editor,
        ))


def create_visit(session: Session, data: VisitCreate) -> Visit:
    """新增走访：校验人员 → 落库 → 留痕 → 同步 last_visit_date，同事务"""
    _get_person_or_404(session, data.person_id)
    payload = data.model_dump(exclude={"editor"})
    visit = Visit(**payload, quarter=get_quarter(data.visit_date))
    session.add(visit)
    session.flush()  # 取 visit.id
    diffs = [(f, None, payload[f]) for f in _LOG_FIELDS if payload.get(f) is not None]
    _write_logs(session, visit.id, diffs, data.editor or DEFAULT_EDITOR)
    _sync_last_visit_date(session, data.person_id)
    session.commit()
    session.refresh(visit)
    return visit


def list_visits(session: Session, params: VisitQueryParams) -> Page[VisitResponse]:
    """分页列表：person_id / quarter / 日期区间筛选，visit_date 倒序"""
    query = select(Visit)
    if params.person_id is not None:
        query = query.where(Visit.person_id == params.person_id)
    if params.quarter:
        query = query.where(Visit.quarter == params.quarter)
    if params.visit_date_start:
        query = query.where(Visit.visit_date >= params.visit_date_start)
    if params.visit_date_end:
        query = query.where(Visit.visit_date <= params.visit_date_end)

    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    rows = session.exec(
        query.order_by(Visit.visit_date.desc())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    ).all()
    return Page[VisitResponse](
        items=[VisitResponse.model_validate(v) for v in rows],
        total=total, page=params.page, page_size=params.page_size,
        pages=math.ceil(total / params.page_size) if total > 0 else 0,
    )


def get_visit(session: Session, visit_id: int) -> Visit:
    return _get_visit_or_404(session, visit_id)


def update_visit(session: Session, visit_id: int, data: VisitUpdate) -> Visit:
    """PATCH 语义：exclude_unset；visit_date 变更时重算 quarter；逐字段留痕"""
    visit = _get_visit_or_404(session, visit_id)
    changes = data.model_dump(exclude_unset=True)
    editor = changes.pop("editor", None) or DEFAULT_EDITOR

    diffs = []
    for field_name, new_value in changes.items():
        old_value = getattr(visit, field_name)
        if old_value != new_value:
            diffs.append((field_name, old_value, new_value))
            setattr(visit, field_name, new_value)
    if "visit_date" in changes:
        visit.quarter = get_quarter(visit.visit_date)

    session.add(visit)
    _write_logs(session, visit.id, diffs, editor)
    session.flush()
    _sync_last_visit_date(session, visit.person_id)
    session.commit()
    session.refresh(visit)
    return visit


def delete_visit(session: Session, visit_id: int) -> None:
    visit = _get_visit_or_404(session, visit_id)
    person_id = visit.person_id
    session.delete(visit)
    session.flush()  # 先剔除再重算 max
    _sync_last_visit_date(session, person_id)
    session.commit()


def get_quarterly_stats(session: Session, person_id: Optional[int] = None) -> dict:
    """走访季度统计（本季度各方式数量，键名与原实现一致）"""
    current_quarter = get_quarter(date.today())
    query = select(Visit).where(Visit.quarter == current_quarter)
    if person_id is not None:
        query = query.where(Visit.person_id == person_id)
    visits = session.exec(query).all()
    return {
        "quarter": current_quarter,
        "total": len(visits),
        "上门": sum(1 for v in visits if v.visit_method == "上门"),
        "电话": sum(1 for v in visits if v.visit_method == "电话"),
        "视频": sum(1 for v in visits if v.visit_method == "视频"),
        "有异常": sum(1 for v in visits if v.has_abnormal),
    }
