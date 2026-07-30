"""信封自动包装 + 全局异常接管
依据 03-design.md §3.1：handler 裸返回 data，本模块统一包信封；
业务错误按 ErrorCode 映射真实 HTTP 状态码（400/401/403/404/409/500）。
在 main.py 中注册一次：register_envelope(app)
"""
import json
import logging
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from app.core.config import settings
from app.schemas.common import BizError, Envelope, ErrorCode, FieldError

logger = logging.getLogger("judicial.core.middleware")

# 文件流/静态资源白名单（前缀匹配）：不参与信封，直接透传
_ENVELOPE_SKIP_PREFIXES = (
    "/api/persons/export",
    "/api/persons/import/template",
    "/api/files/download",
    "/static",
)

# 精确匹配白名单（HTML 页面/文档/探活）
_ENVELOPE_SKIP_EXACT = ("/", "/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico")


def _is_skipped_path(path: str) -> bool:
    if path in _ENVELOPE_SKIP_EXACT:
        return True
    return any(path.startswith(p) for p in _ENVELOPE_SKIP_PREFIXES)


def _http_status_of(envelope: dict) -> int:
    """ErrorCode -> HTTP 状态码显式映射，便于监控区分错误类型"""
    code = envelope.get("code", 0)
    return _HTTP_STATUS_BY_CODE.get(code, 200)


# ErrorCode -> HTTP status 显式映射
_HTTP_STATUS_BY_CODE = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.INVALID_SORT_PARAM: 400,
    ErrorCode.BAD_REQUEST_BODY: 400,
    ErrorCode.BATCH_LIMIT_EXCEEDED: 400,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.WRONG_PASSWORD: 401,
    ErrorCode.ACCOUNT_DISABLED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.PERSON_NOT_FOUND: 404,
    ErrorCode.VISIT_NOT_FOUND: 404,
    ErrorCode.FILE_NOT_FOUND: 404,
    ErrorCode.ID_CARD_CONFLICT: 409,
    ErrorCode.FILE_TYPE_UNSUPPORTED: 400,
    ErrorCode.FILE_SIZE_EXCEEDED: 400,
    ErrorCode.BIZ_RULE_CONFLICT: 409,
    ErrorCode.INTERNAL_ERROR: 500,
}


def register_envelope(app: FastAPI) -> None:
    """注册信封中间件与全部异常处理器（main.py 启动时调用一次）"""

    @app.middleware("http")
    async def envelope_middleware(request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        if _is_skipped_path(request.url.path):
            return response
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return response
        body = b""
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            body += chunk if isinstance(chunk, bytes) else chunk.encode()
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return Response(content=body, status_code=response.status_code,
                            headers=dict(response.headers), media_type=content_type)
        if isinstance(payload, dict) and "code" in payload and "message" in payload:
            wrapped = payload                      # 已是信封（ok() 或异常处理器产出）
        elif isinstance(payload, dict) and "detail" in payload:
            # 兼容残留 HTTPException 输出（过渡期兜底，逐步清零）
            wrapped = {"code": _map_status_to_code(response.status_code),
                       "message": str(payload["detail"]), "data": None}
        else:
            wrapped = Envelope(data=payload).model_dump()
        return JSONResponse(content=wrapped, status_code=_http_status_of(wrapped))

    @app.exception_handler(BizError)
    async def biz_error_handler(request: Request, exc: BizError) -> JSONResponse:
        data = {"errors": [e.model_dump() for e in exc.errors]} if exc.errors else None
        return JSONResponse(
            status_code=_HTTP_STATUS_BY_CODE.get(exc.code, 200),
            content={"code": exc.code, "message": exc.message, "data": data},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request,
                                       exc: RequestValidationError) -> JSONResponse:
        errors = [
            FieldError(field=str(err["loc"][-1]), message=err["msg"])
            for err in exc.errors()
        ]
        first = errors[0] if errors else FieldError(field="-", message="参数错误")
        return JSONResponse(
            status_code=400,
            content={
                "code": ErrorCode.VALIDATION_ERROR,
                "message": f"参数校验失败: {first.field} {first.message}",
                "data": {"errors": [e.model_dump() for e in errors]},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        if settings.DEBUG:
            return JSONResponse(status_code=500, content={
                "code": ErrorCode.INTERNAL_ERROR,
                "message": f"服务器内部错误: {exc}", "data": None})
        return JSONResponse(status_code=500, content={
            "code": ErrorCode.INTERNAL_ERROR,
            "message": "服务器开小差了，请稍后再试", "data": None})


def _map_status_to_code(status_code: int) -> int:
    """过渡期：残留 HTTPException 的 detail 输出按状态码映射到错误码"""
    return {
        400: ErrorCode.BAD_REQUEST_BODY,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.PERSON_NOT_FOUND,
        422: ErrorCode.VALIDATION_ERROR,
    }.get(status_code, ErrorCode.INTERNAL_ERROR)
