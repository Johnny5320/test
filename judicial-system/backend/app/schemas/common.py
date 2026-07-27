"""公共契约：信封 / 分页 / 错误码 / 业务异常
依据 sys_v3.2-refactor-plan/03-design.md §3.1-3.2 定稿。
约定：HTTP 一律 200（仅 401 例外）；所有 schema 一律 extra="forbid"。
"""
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# ---------- 信封 ----------

class Envelope(BaseModel, Generic[T]):
    """统一响应信封：{ "code": 0, "message": "ok", "data": T }"""
    code: int = 0
    message: str = "ok"
    data: Optional[T] = None


def ok(data: Any = None, message: str = "ok") -> dict:
    """需要自定义 message 的端点显式调用（如批量"成功删除 3 条"）"""
    return {"code": 0, "message": message, "data": data}


class FieldError(BaseModel):
    """字段级错误（code=10001 时 data.errors 的元素）"""
    field: str
    message: str


# ---------- 分页 ----------

MAX_PAGE_SIZE = 500  # 决议 F2：上限 500（原 2000 废除；全量需求走 name-map）


class PageParams(BaseModel):
    """分页查询参数基类（Depends 参数类用）"""
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=MAX_PAGE_SIZE)


class Page(BaseModel, Generic[T]):
    """分页响应（泛型化）"""
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int


# ---------- 错误码（大类1+模块域2+序号2；大类冻结 6 个，序号不回收） ----------

class ErrorCode:
    """大类：1参数/2认证/3权限/4资源/5业务/9系统。
    模块域：00 通用 / 01 人员 / 02 走访 / 03 提醒 / 04 文件·导入导出 / 05 认证。"""
    SUCCESS = 0
    VALIDATION_ERROR = 10001        # 参数校验失败（data.errors 带 FieldError 明细）
    INVALID_SORT_PARAM = 10002      # 非法排序/筛选参数
    BAD_REQUEST_BODY = 10003        # 请求体格式错误
    BATCH_LIMIT_EXCEEDED = 10004    # 批量数量超限（>100）
    UNAUTHORIZED = 20001            # 未认证/Token 失效（唯一配 HTTP 401）
    WRONG_PASSWORD = 20002
    ACCOUNT_DISABLED = 20003
    FORBIDDEN = 30001               # 权限不足（预留）
    PERSON_NOT_FOUND = 40401
    VISIT_NOT_FOUND = 40402
    FILE_NOT_FOUND = 40403
    ID_CARD_CONFLICT = 40901        # 身份证号已存在
    FILE_TYPE_UNSUPPORTED = 50401
    FILE_SIZE_EXCEEDED = 50402
    BIZ_RULE_CONFLICT = 50901       # 业务规则冲突（预留）
    INTERNAL_ERROR = 90001          # 全局兜底


# ---------- 业务异常（service/api 抛出，core.middleware 统一转信封） ----------

class BizError(Exception):
    """业务异常：service/api 层 raise，异常处理器统一捕获转信封"""

    def __init__(self, code: int, message: str,
                 errors: Optional[List[FieldError]] = None):
        self.code = code
        self.message = message
        self.errors = errors
        super().__init__(message)
