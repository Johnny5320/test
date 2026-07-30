"""services/person_service.py — 人员业务层
职责：业务规则（查重/身份证推断/留痕）+ 事务边界（commit 唯一地点）。
对应 03-design.md §2/§4：handler 不碰 session.commit()；留痕与主更新同事务。
"""
import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

logger = logging.getLogger("judicial.persons")

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.edit_log import EditLog
from app.models.person import Person
from app.schemas.common import (BizError, ErrorCode, Page)
from app.schemas.person import (BatchFailure, BatchResult, EditLogResponse,
                                PersonCreate, PersonListResponse, PersonNameMapItem,
                                PersonQueryParams, PersonResponse, PersonUpdate)
from app.utils.id_card import infer_from_id_card, mask_id_card, validate_id_card

DEFAULT_EDITOR = "司法所"  # 决议 F5：editor 缺省值
# 2026-07-28 用户决议：走访间隔不再按风险等级自动赋值（避免与人工填写冲突），
# 由添加人员时人为填写；未填写则用 schema 默认值 90。


# ---------- 查询 ----------

def to_response(person: Person) -> PersonResponse:
    """详情序列化：含完整身份证号 + 脱敏版（仅 detail 接口使用）"""
    r = PersonResponse.model_validate(person)
    r.id_card_masked = mask_id_card(person.id_card)
    return r


def to_list_response(person: Person) -> PersonListResponse:
    """列表序列化：不含完整身份证号，仅含脱敏版"""
    r = PersonListResponse.model_validate(person)
    r.id_card_masked = mask_id_card(person.id_card)
    return r


def list_persons(params: PersonQueryParams, session: Session) -> Page[PersonListResponse]:
    """分页列表：不含完整身份证号（隐私脱敏）"""
    stmt = select(Person).where(Person.is_deleted == False)  # noqa: E712
    stmt = _apply_filters(stmt, params)
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    sort_col = getattr(Person, params.sort_by)  # sort_by 已被 Literal 白名单约束
    stmt = stmt.order_by(sort_col.asc() if params.sort_order == "asc" else sort_col.desc())
    stmt = stmt.offset((params.page - 1) * params.page_size).limit(params.page_size)
    items = session.exec(stmt).all()
    return Page[PersonListResponse](
        items=[to_list_response(p) for p in items],
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
    if params.expiring_overdue:
        # 已到期未解除：在帮且帮教截止日已过
        stmt = stmt.where(Person.status == "在帮")
        stmt = stmt.where(Person.edu_end_date != None,  # noqa: E711
                          Person.edu_end_date < date.today())
    if params.min_age is not None or params.max_age is not None:
        stmt = _apply_age_filter(stmt, params.min_age, params.max_age)
    if params.ids_str:
        try:
            ids = [int(x.strip()) for x in params.ids_str.split(",") if x.strip()]
            if ids:
                stmt = stmt.where(Person.id.in_(ids))
        except ValueError:
            pass  # 忽略无效的 ids 参数
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


def list_edit_logs(person_id: int, session: Session,
                   editor: str = None, year_month: str = None) -> List[EditLogResponse]:
    """人员修改历史：按时间倒序，支持按操作人和年月筛选"""
    get_person_or_404(person_id, session)
    stmt = select(EditLog).where(EditLog.table_name == "persons", EditLog.record_id == person_id)
    if editor:
        stmt = stmt.where(EditLog.editor == editor)
    if year_month:
        # year_month 格式：2026-07
        stmt = stmt.where(EditLog.edited_at >= f"{year_month}-01")
        # 计算月末
        parts = year_month.split("-")
        y, m = int(parts[0]), int(parts[1])
        if m == 12:
            next_month = f"{y+1}-01-01"
        else:
            next_month = f"{y}-{m+1:02d}-01"
        stmt = stmt.where(EditLog.edited_at < next_month)
    logs = session.exec(stmt.order_by(EditLog.edited_at.desc())).all()
    return [EditLogResponse.model_validate(log) for log in logs]


# ---------- 写入（事务与留痕在此层） ----------

def _assert_id_card_strict(id_card: str, gender: Optional[str] = None,
                           birth_date: Optional[date] = None) -> None:
    """1.2 严格校验（报告⑧）：校验位必须正确；若同时提供性别/出生日期，须与身份证
    编码一致（二者均可从身份证号本身推导，无需外部行政区表）。校验失败直接阻断落库。"""
    if not validate_id_card(id_card):
        raise BizError(ErrorCode.VALIDATION_ERROR,
                       "身份证号校验位错误（末位与 GB 11643 算法不符），请核对后重新录入")
    inferred = infer_from_id_card(id_card)
    if gender and inferred.get("gender") and gender != inferred["gender"]:
        raise BizError(ErrorCode.VALIDATION_ERROR, "性别与身份证号第17位编码不一致")
    if birth_date and inferred.get("birth_date") and birth_date != inferred["birth_date"]:
        raise BizError(ErrorCode.VALIDATION_ERROR, "出生日期与身份证号编码不一致")


def create_person(data: PersonCreate, session: Session,
                   editor: Optional[str] = None) -> Person:
    """1.2 严格校验：校验位错误 / 性别·出生不一致 直接阻断（VALIDATION_ERROR）。
    导入通道走 import_service（独立 _validate_one_row 仅警告），不受此影响。"""
    _assert_id_card_strict(data.id_card, data.gender, data.birth_date)
    _raise_if_id_card_exists(data.id_card, session)
    _release_soft_deleted_id_card(data.id_card, session)  # 释放软删墓碑占用的库级 UNIQUE
    payload = data.model_dump(exclude={"editor"})
    for k, v in infer_from_id_card(data.id_card).items():  # 未提供时从身份证推算
        if not payload.get(k):
            payload[k] = v
    if payload.get("visit_interval_days") is None:  # 未填写时兜底为 schema 默认 90
        payload["visit_interval_days"] = 90
    person = Person(**payload)
    session.add(person)
    try:
        session.flush()                       # 先拿 id 再留痕，同事务
    except IntegrityError:
        session.rollback()
        raise BizError(ErrorCode.ID_CARD_CONFLICT,
                       "该身份证号已被其他记录占用，请刷新后重试")
    _write_edit_log(person.id, "persons", "新增人员", editor, session)
    session.commit()
    session.refresh(person)
    return person


def update_person(person_id: int, data: PersonUpdate, session: Session) -> Person:
    """PATCH 语义：exclude_unset 只改传了的字段；逐字段 EditLog 与主更新同事务"""
    person = get_person_or_404(person_id, session)
    changes = data.model_dump(exclude_unset=True, exclude={"editor"})
    if "id_card" in changes and changes["id_card"] != person.id_card:
        _assert_id_card_strict(changes["id_card"], changes.get("gender"), changes.get("birth_date"))
        _raise_if_id_card_exists(changes["id_card"], session, exclude_id=person_id)
        _release_soft_deleted_id_card(changes["id_card"], session)  # 同创建：释放软删占坑
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
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise BizError(ErrorCode.ID_CARD_CONFLICT,
                       "该身份证号已被其他记录占用，请刷新后重试")
    session.refresh(person)
    return person


def delete_person(person_id: int, session: Session) -> None:
    """软删除"""
    person = get_person_or_404(person_id, session)
    person.is_deleted = True
    person.updated_at = datetime.now(timezone.utc)
    session.add(person)
    session.commit()


def batch_delete_persons(ids: List[int], session: Session,
                         editor: Optional[str] = None) -> BatchResult:
    return _batch_apply(ids, session, lambda p: setattr(p, "is_deleted", True),
                        field_name="is_deleted", new_value_str="True", editor=editor)


def batch_update_status(ids: List[int], status: str, session: Session,
                        editor: Optional[str] = None) -> BatchResult:
    return _batch_apply(ids, session, lambda p: setattr(p, "status", status),
                        field_name="status", new_value_str=status, editor=editor)


def batch_update_risk(ids: List[int], risk_level: str, session: Session,
                      editor: Optional[str] = None) -> BatchResult:
    return _batch_apply(ids, session, lambda p: setattr(p, "risk_level", risk_level),
                        field_name="risk_level", new_value_str=risk_level, editor=editor)


def _batch_apply(ids: List[int], session: Session, apply,
                 field_name: str = "", new_value_str: str = "",
                 editor: Optional[str] = None) -> BatchResult:
    """批量部分成功（决议 #8）：失败项仅标记不拖崩整批，单事务 commit，每条写 EditLog"""
    failures: List[BatchFailure] = []
    success = 0
    for pid in ids:
        person = session.get(Person, pid)
        if not person or person.is_deleted:
            failures.append(BatchFailure(id=pid, code=ErrorCode.PERSON_NOT_FOUND,
                                         message="人员不存在或已删除"))
            continue
        old_value = getattr(person, field_name) if field_name else None
        apply(person)
        person.updated_at = datetime.now(timezone.utc)
        session.add(person)
        # 写留痕
        if field_name:
            session.add(EditLog(
                table_name="persons", record_id=pid, field_name=field_name,
                old_value=str(old_value)[:2000] if old_value is not None else None,
                new_value=new_value_str[:2000],
                editor=editor or DEFAULT_EDITOR))
        success += 1
    session.commit()
    return BatchResult(success_count=success, failed_count=len(failures),
                       failures=failures)


# ---------- 留痕 ----------

def _raise_if_id_card_exists(id_card: str, session: Session,
                             exclude_id: Optional[int] = None) -> None:
    # 2026-07-28 修复：查重需排除软删记录，否则已删除人员的身份证号会永久占坑无法重新添加
    stmt = select(Person.id).where(Person.id_card == id_card,
                                   Person.is_deleted == False)  # noqa: E712
    if exclude_id is not None:
        stmt = stmt.where(Person.id != exclude_id)
    if session.exec(stmt).first():
        raise BizError(ErrorCode.ID_CARD_CONFLICT, "该身份证号已存在")


def _release_soft_deleted_id_card(id_card: str, session: Session) -> None:
    """2026-07-28：persons.id_card 有库级 UNIQUE，软删行会占坑导致同号重建撞
    IntegrityError(500)。入库/改号前把持有同号的软删行改成墓碑号 `原号#D{id}`，
    释放唯一约束，同时保留软删记录可追溯。（墓碑号超 18 位，与真实号不冲突）"""
    tombstones = session.exec(
        select(Person).where(Person.id_card == id_card,
                             Person.is_deleted == True)  # noqa: E712
    ).all()
    for p in tombstones:
        p.id_card = f"{id_card}#D{p.id}"
        session.add(p)
    if tombstones:
        session.flush()


def _write_edit_log(record_id: int, table: str, summary: str,
                    editor: Optional[str], session: Session) -> None:
    """新增类留痕：field_name 用 "(新增)" 占位（EditLog.field_name 必填）"""
    session.add(EditLog(table_name=table, record_id=record_id,
                        field_name="(新增)", new_value=summary[:2000],
                        editor=editor or DEFAULT_EDITOR))
