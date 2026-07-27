"""services/person_service.py — 人员业务层
职责：业务规则（查重/身份证推断/留痕）+ 事务边界（commit 唯一地点）。
对应 03-design.md §2/§4：handler 不碰 session.commit()；留痕与主更新同事务。
"""
import math
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.edit_log import EditLog
from app.models.person import Person
from app.schemas.common import (BizError, ErrorCode, Page)
from app.schemas.person import (BatchFailure, BatchResult, EditLogResponse,
                                PersonCreate, PersonNameMapItem,
                                PersonQueryParams, PersonResponse, PersonUpdate)
from app.utils.id_card import infer_from_id_card, validate_id_card

DEFAULT_EDITOR = "司法所"  # 决议 F5：editor 缺省值
# 原 persons.py:1020-1023：未显式设置走访间隔时按风险等级给默认值
RISK_INTERVAL_MAP = {"高": 30, "中": 90, "低": 180}


# ---------- 查询 ----------

def list_persons(params: PersonQueryParams, session: Session) -> Page[PersonResponse]:
    """分页列表：一个参数对象收敛全部筛选；无 N+1（last_visit_date 走冗余字段）"""
    stmt = select(Person).where(Person.is_deleted == False)  # noqa: E712
    stmt = _apply_filters(stmt, params)
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    sort_col = getattr(Person, params.sort_by)  # sort_by 已被 Literal 白名单约束
    stmt = stmt.order_by(sort_col.asc() if params.sort_order == "asc" else sort_col.desc())
    stmt = stmt.offset((params.page - 1) * params.page_size).limit(params.page_size)
    items = session.exec(stmt).all()
    return Page[PersonResponse](
        items=[PersonResponse.model_validate(p) for p in items],
        total=total, page=params.page, page_size=params.page_size,
        pages=math.ceil(total / params.page_size) if total else 0,
    )


def _apply_filters(stmt, params: PersonQueryParams):
    """筛选构建唯一地点（与原 persons.py:80-124 全对齐）"""
    if params.search:
        like = f"%{params.search}%"
        stmt = stmt.where((Person.name.like(like)) | (Person.id_card.like(like))
                          | (Person.phone.like(like)))
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
    if params.is_key_target is not None:
        stmt = stmt.where(Person.is_key_target == params.is_key_target)
    if params.is_minor is not None:
        stmt = stmt.where(Person.is_minor == params.is_minor)
    if params.is_xj is not None:
        stmt = stmt.where(Person.is_xj == params.is_xj)
    if params.is_mental is not None:
        stmt = stmt.where(Person.is_mental == params.is_mental)
    if params.has_drug_history is not None:
        stmt = stmt.where(Person.has_drug_history == params.has_drug_history)
    if params.is_recidivist is not None:
        stmt = stmt.where(Person.is_recidivist == params.is_recidivist)
    if params.expiring_within_days is not None:
        # 原语义：仅"在帮"且帮教截止日在 [today, today+N] 闭区间
        deadline = date.today() + timedelta(days=params.expiring_within_days)
        stmt = stmt.where(Person.status == "在帮")
        stmt = stmt.where(Person.edu_end_date != None,  # noqa: E711
                          Person.edu_end_date >= date.today(),
                          Person.edu_end_date <= deadline)
    if params.min_age is not None or params.max_age is not None:
        stmt = _apply_age_filter(stmt, params.min_age, params.max_age)
    return stmt


def _apply_age_filter(stmt, min_age: Optional[int], max_age: Optional[int]):
    """闰日安全（修复原 persons.py:100-105 在 2/29 必现 500）"""
    today = date.today()
    if min_age is not None:
        stmt = stmt.where(Person.birth_date != None,  # noqa: E711
                          Person.birth_date <= _shift_years(today, -min_age))
    if max_age is not None:
        # 原语义：birth_date >= (today-(max_age+1)年)+1天 ≡ birth_date > today-(max_age+1)年
        stmt = stmt.where(Person.birth_date != None,  # noqa: E711
                          Person.birth_date > _shift_years(today, -max_age - 1))
    return stmt


def _shift_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 2/29 → 2/28
        return d.replace(year=d.year + years, day=28)


def get_person_or_404(person_id: int, session: Session) -> Person:
    person = session.get(Person, person_id)
    if not person or person.is_deleted:
        raise BizError(ErrorCode.PERSON_NOT_FOUND, "人员不存在或已删除")
    return person


def get_person_name_map(session: Session) -> List[PersonNameMapItem]:
    """name-map 专用：无 join 无分页，一次全量"""
    rows = session.exec(
        select(Person.id, Person.name).where(Person.is_deleted == False)  # noqa: E712
    ).all()
    return [PersonNameMapItem(id=r[0], name=r[1]) for r in rows]


def list_edit_logs(person_id: int, session: Session) -> List[EditLogResponse]:
    """人员修改历史：按时间倒序（原 persons.py:972-989）"""
    get_person_or_404(person_id, session)
    logs = session.exec(
        select(EditLog)
        .where(EditLog.table_name == "persons", EditLog.record_id == person_id)
        .order_by(EditLog.edited_at.desc())
    ).all()
    return [EditLogResponse.model_validate(log) for log in logs]


# ---------- 写入（事务与留痕在此层） ----------

def create_person(data: PersonCreate, session: Session) -> Person:
    """校验位复用 utils；查重 40901；身份证推断性别/生日；风险默认走访间隔"""
    if not validate_id_card(data.id_card):
        raise BizError(ErrorCode.VALIDATION_ERROR, "身份证号校验位错误")
    _raise_if_id_card_exists(data.id_card, session)
    payload = data.model_dump(exclude={"editor"})
    for k, v in infer_from_id_card(data.id_card).items():  # 未提供时从身份证推算
        if not payload.get(k):
            payload[k] = v
    if payload.get("visit_interval_days") in (None, 90):  # 90 为 schema 默认值
        payload["visit_interval_days"] = RISK_INTERVAL_MAP.get(
            payload.get("risk_level") or "低", 90)
    person = Person(**payload)
    session.add(person)
    session.flush()                       # 先拿 id 再留痕，同事务
    _write_edit_log(person.id, "persons", "新增人员", data.editor, session)
    session.commit()
    session.refresh(person)
    return person


def update_person(person_id: int, data: PersonUpdate, session: Session) -> Person:
    """PATCH 语义：exclude_unset 只改传了的字段；逐字段 EditLog 与主更新同事务"""
    person = get_person_or_404(person_id, session)
    changes = data.model_dump(exclude_unset=True, exclude={"editor"})
    if "id_card" in changes and changes["id_card"] != person.id_card:
        if not validate_id_card(changes["id_card"]):
            raise BizError(ErrorCode.VALIDATION_ERROR, "身份证号校验位错误")
        _raise_if_id_card_exists(changes["id_card"], session, exclude_id=person_id)
    for field, new_value in changes.items():
        old_value = getattr(person, field)
        if str(old_value) != str(new_value):  # 留痕格式同原 persons.py:1048-1059
            session.add(EditLog(
                table_name="persons", record_id=person_id, field_name=field,
                old_value=str(old_value)[:2000] if old_value is not None else None,
                new_value=str(new_value)[:2000] if new_value is not None else None,
                editor=data.editor or DEFAULT_EDITOR))
        setattr(person, field, new_value)
    person.updated_at = datetime.now(timezone.utc)
    session.add(person)
    session.commit()
    session.refresh(person)
    return person


def delete_person(person_id: int, session: Session) -> None:
    """软删除"""
    person = get_person_or_404(person_id, session)
    person.is_deleted = True
    person.updated_at = datetime.now(timezone.utc)
    session.add(person)
    session.commit()


def batch_delete_persons(ids: List[int], session: Session) -> BatchResult:
    return _batch_apply(ids, session, lambda p: setattr(p, "is_deleted", True))


def batch_update_status(ids: List[int], status: str, session: Session) -> BatchResult:
    return _batch_apply(ids, session, lambda p: setattr(p, "status", status))


def batch_update_risk(ids: List[int], risk_level: str, session: Session) -> BatchResult:
    return _batch_apply(ids, session, lambda p: setattr(p, "risk_level", risk_level))


def _batch_apply(ids: List[int], session: Session, apply) -> BatchResult:
    """批量部分成功（决议 #8）：失败项仅标记不拖崩整批，单事务 commit"""
    failures: List[BatchFailure] = []
    success = 0
    for pid in ids:
        person = session.get(Person, pid)
        if not person or person.is_deleted:
            failures.append(BatchFailure(id=pid, code=ErrorCode.PERSON_NOT_FOUND,
                                         message="人员不存在或已删除"))
            continue
        apply(person)
        person.updated_at = datetime.now(timezone.utc)
        session.add(person)
        success += 1
    session.commit()
    return BatchResult(success_count=success, failed_count=len(failures),
                       failures=failures)


# ---------- 留痕 ----------

def _raise_if_id_card_exists(id_card: str, session: Session,
                             exclude_id: Optional[int] = None) -> None:
    stmt = select(Person.id).where(Person.id_card == id_card)
    if exclude_id is not None:
        stmt = stmt.where(Person.id != exclude_id)
    if session.exec(stmt).first():
        raise BizError(ErrorCode.ID_CARD_CONFLICT, "该身份证号已存在")


def _write_edit_log(record_id: int, table: str, summary: str,
                    editor: Optional[str], session: Session) -> None:
    """新增类留痕：field_name 用 "(新增)" 占位（EditLog.field_name 必填）"""
    session.add(EditLog(table_name=table, record_id=record_id,
                        field_name="(新增)", new_value=summary[:2000],
                        editor=editor or DEFAULT_EDITOR))
