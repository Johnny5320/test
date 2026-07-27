"""Excel 导入契约（替代 schemas/__init__.py 中的 Import 段）
依据决议 D10：删冗余 success 布尔（成败由 envelope code 推导），
新增 errors_truncated 标记错误明细是否被 100 条上限截断。
对照原声明：ImportErrorDetail / ImportResult（schemas/__init__.py:296-309）。
模块名加下划线避开关键字 import（PEP8 惯例）。
"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ImportErrorDetail(BaseModel):
    """导入错误详情；field 为 None 表示整行级错误"""
    model_config = ConfigDict(extra="forbid")

    row: int
    field: Optional[str] = None
    message: str


class ImportResult(BaseModel):
    """导入结果（无 success 字段；total_rows = imported + skipped + 校验失败行数）"""
    model_config = ConfigDict(extra="forbid")

    total_rows: int
    imported: int
    skipped: int
    errors: List[ImportErrorDetail]
    errors_truncated: bool = False
