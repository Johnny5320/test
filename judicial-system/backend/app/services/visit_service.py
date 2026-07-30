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


def _validate_visit_date(person: Person, visit_date: date) -> None:
    """走访日期校验：不能早于帮教起始日，不能晚于今天"""
    if person.edu_start_date and visit_date < person.edu_start_date:
        raise BizError(ErrorCode.VALIDATION_ERROR,
                       f"走访日期不能早于帮教起始日期（{person.edu_start_date}）")
    if visit_date > date.today():
        raise BizError(ErrorCode.VALIDATION_ERROR, "走访日期不能晚于今天")


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


def create_visit(session: Session, data: VisitCreate,
                  editor: Optional[str] = None) -> Visit:
    """新增走访：校验人员 → 校验日期 → 落库 → 留痕 → 同步 last_visit_date，同事务"""
    person = _get_person_or_404(session, data.person_id)
    _validate_visit_date(person, data.visit_date)
    # 标记有异常时必须填写异常详情
    if data.has_abnormal and not data.abnormal_detail:
        raise BizError(ErrorCode.VALIDATION_ERROR, "标记有异常时必须填写异常详情")
    payload = data.model_dump(exclude={"editor"})
    visit = Visit(**payload, quarter=get_quarter(data.visit_date))
    session.add(visit)
    session.flush()  # 取 visit.id
    diffs = [(f, None, payload[f]) for f in _LOG_FIELDS if payload.get(f) is not None]
    _write_logs(session, visit.id, diffs, editor or DEFAULT_EDITOR)
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
    # 1.3 标注走访所属人员是否已软删：一次 IN 查询拿软删 id 集合（避免 N+1），
    # 供前端将「已删除人员走访」独立分组，主口径排除以免重复计数。
    person_ids = {v.person_id for v in rows}
    deleted_ids: set = set()
    if person_ids:
        deleted_ids = set(session.exec(
            select(Person.id).where(
                Person.id.in_(person_ids), Person.is_deleted == True)  # noqa: E712
        ).all())
    items = []
    for v in rows:
        r = VisitResponse.model_validate(v)
        r.person_is_deleted = v.person_id in deleted_ids
        items.append(r)
    return Page[VisitResponse](
        items=items,
        total=total, page=params.page, page_size=params.page_size,
        pages=math.ceil(total / params.page_size) if total > 0 else 0,
    )


def get_visit(session: Session, visit_id: int) -> Visit:
    return _get_visit_or_404(session, visit_id)


def update_visit(session: Session, visit_id: int, data: VisitUpdate,
                  editor: Optional[str] = None) -> Visit:
    """PATCH 语义：exclude_unset；visit_date 变更时重算 quarter；逐字段留痕"""
    visit = _get_visit_or_404(session, visit_id)
    changes = data.model_dump(exclude_unset=True, exclude={"editor"})
    editor = editor or DEFAULT_EDITOR

    diffs = []
    for field_name, new_value in changes.items():
        old_value = getattr(visit, field_name)
        if old_value != new_value:
            diffs.append((field_name, old_value, new_value))
            setattr(visit, field_name, new_value)
    if "visit_date" in changes:
        person = _get_person_or_404(session, visit.person_id)
        _validate_visit_date(person, visit.visit_date)
        visit.quarter = get_quarter(visit.visit_date)

    # 标记有异常时必须填写异常详情
    final_has_abnormal = changes.get("has_abnormal", visit.has_abnormal)
    final_abnormal_detail = changes.get("abnormal_detail", visit.abnormal_detail)
    if final_has_abnormal and not final_abnormal_detail:
        raise BizError(ErrorCode.VALIDATION_ERROR, "标记有异常时必须填写异常详情")

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
