"""api/persons_stats.py — 人员统计/导入导出/监狱路由层（Agent C 垂直切片）
独立 router（prefix="/api/persons"）。原 persons.py 对应区段：
stats_summary/stats_trend/risk_score/quarterly_report/prisons/export/import。
handler ≤10 行编排：声明参数 → 调 service → 裸返回 data（文件流端点除外）。
集成注意（主 agent）：本 router 须在 persons.router 之前注册，否则固定路径
（/stats-summary 等）会被 persons.py 的 /{person_id} 抢先匹配。
"""
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.common import ok
from app.schemas.person import PersonQueryParams
from app.schemas.stats import (PeriodReport, PrisonItem, PrisonPersonItem,
                               QuarterlyReport, RiskScoreResult, StatsSummary,
                               TrendPoint)
from app.services import import_service, stats_service

router = APIRouter(prefix="/api/persons", tags=["人员统计与导入导出"])


# ---------- 统计（固定路径在前） ----------

@router.get("/stats-summary")
def get_person_stats_summary(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user)) -> StatsSummary:
    """统计汇总：英文键定稿（status_*/risk_*），口径同原 /stats/summary"""
    return stats_service.get_summary(session)


@router.get("/stats-trend")
def get_person_stats_trend(months: int = Query(6, ge=1, le=24),
                           session: Session = Depends(get_session),
                           current_user: User = Depends(get_current_user)
                           ) -> List[TrendPoint]:
    """最近 N 个月每月新增人数（原 /stats/trend）"""
    return stats_service.get_trend(months, session)


@router.get("/reports-quarterly")
def get_person_quarterly_report(year: Optional[int] = Query(None, ge=2000, le=2100),
                                quarter: Optional[int] = Query(None, ge=1, le=4),
                                session: Session = Depends(get_session),
                                current_user: User = Depends(get_current_user)
                                ) -> QuarterlyReport:
    """季度报表：year/quarter ge/le 拦截越界（修复原 quarter=0/5 必现 500）"""
    return stats_service.get_quarterly_report(year, quarter, session)


@router.get("/reports-period")
def get_person_period_report(year: Optional[int] = Query(None, ge=2000, le=2100),
                             quarter: Optional[int] = Query(None, ge=1, le=4),
                             month: Optional[int] = Query(None, ge=1, le=12),
                             session: Session = Depends(get_session),
                             current_user: User = Depends(get_current_user)
                             ) -> PeriodReport:
    """周期报表：年 / 年+季度 / 年+月份 整页数据单一来源（统计报表页统一取数）"""
    return stats_service.get_period_report(year, quarter, month, session)


# ---------- 监狱 ----------

@router.get("/prisons")
def list_prisons(session: Session = Depends(get_session),
                 current_user: User = Depends(get_current_user)) -> List[PrisonItem]:
    """去重服刑场所及人数"""
    return stats_service.list_prisons(session)


@router.get("/prisons/{prison_name}/persons")
def list_prison_persons(prison_name: str,
                        session: Session = Depends(get_session),
                        current_user: User = Depends(get_current_user)
                        ) -> List[PrisonPersonItem]:
    """指定监狱的人员列表"""
    return stats_service.list_prison_persons(prison_name, session)


# ---------- 导入 / 导出 ----------

@router.post("/import")
async def import_persons_excel(file: UploadFile = File(...),
                               session: Session = Depends(get_session),
                               current_user: User = Depends(get_current_user)):
    """Excel 批量导入：解析 → 校验 → 单事务落库（原 /import/excel）"""
    content = await import_service.read_upload(file)
    rows = import_service.parse_excel_rows(content)
    result = import_service.import_persons(import_service.validate_rows(rows), session)
    failed = result.total_rows - result.imported
    return ok(result.model_dump(), f"导入完成：成功 {result.imported} 条，失败 {failed} 条")


@router.get("/import/template")
def download_import_template() -> StreamingResponse:
    """导入模板下载（文件流，middleware 白名单）"""
    return import_service.build_template_response()


@router.get("/export")
def export_persons(params: PersonQueryParams = Depends(),
                   format: Literal["excel"] = "excel",
                   session: Session = Depends(get_session),
                   current_user: User = Depends(get_current_user)) -> StreamingResponse:
    """按 PersonQueryParams 筛选导出 xlsx（原 /export/excel 改 /export?format=excel）"""
    return import_service.build_export_response(params, session)


# ---------- 路径参数路由最后 ----------

@router.get("/{person_id}/risk-score")
def get_person_risk_score(person_id: int,
                          session: Session = Depends(get_session),
                          current_user: User = Depends(get_current_user)) -> RiskScoreResult:
    """风险评分 0-100（两级路径，与 persons.py 的 /{person_id} 不冲突）"""
    return stats_service.get_risk_score(person_id, session)
