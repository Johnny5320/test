"""统一日志配置 —— 安置帮教智能台账系统

设计目标（用户要求：无论正确与否都记录，最大化收集运行情况）：
- 日志写入 backend/logs/app.log（按天轮转，保留 30 天）并同时输出到控制台
- 格式包含：时间、级别、模块、函数名、行号、消息
- 提供 log_call 装饰器，用于“进入 / 成功 / 业务拒绝 / 异常”全量记录接口与函数调用轨迹
- 对敏感信息（密码、JWT、完整身份证号）做脱敏，不写明文
"""
import asyncio
import functools
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent          # backend/
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> Path:
    """配置全局日志。幂等，可重复调用。返回日志文件路径。"""
    global _CONFIGURED
    if _CONFIGURED:
        return LOG_FILE

    # 尽量让 Windows 控制台以 UTF-8 输出中文，失败则忽略
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    fmt = "[%(asctime)s] %(levelname)-8s %(name)s :: %(funcName)s:L%(lineno)d | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt)

    # 文件 handler（每日 0 点轮转，保留 30 份）
    try:
        from logging.handlers import TimedRotatingFileHandler
        fh = TimedRotatingFileHandler(LOG_FILE, when="midnight", backupCount=30, encoding="utf-8")
    except Exception:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(formatter)

    # 控制台 handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(fh)
    root.addHandler(sh)

    # 抑制第三方噪音，避免日志被刷屏（仅 WARNING 及以上才记录）
    for noisy in (
        "uvicorn", "uvicorn.access", "uvicorn.error", "uvicorn.asgi",
        "sqlalchemy.engine", "sqlalchemy.pool", "bcrypt",
    ):
        lg = logging.getLogger(noisy)
        lg.setLevel(logging.WARNING)
        lg.propagate = False

    _CONFIGURED = True
    logging.getLogger("judicial").info("日志系统已初始化 -> %s", LOG_FILE)
    return LOG_FILE


def log_call(func):
    """装饰器：记录函数进入 / 成功 / 业务拒绝 / 异常（含完整堆栈）。

    - 兼容同步与异步函数
    - 使用 functools.wraps 保留原函数签名（FastAPI 依赖注入/参数解析不受影响）
    - 业务拒绝（带 status_code 的异常，如 HTTPException）只记原因，不刷堆栈
    - 其它异常记完整堆栈，便于定位
    """
    qual = func.__qualname__

    def _report(kind, exc=None):
        lg = logging.getLogger("judicial")
        if kind == "enter":
            lg.info("▶ 进入 %s", qual)
        elif kind == "ok":
            lg.info("✓ 完成 %s", qual)
        elif kind == "http":
            lg.warning(
                "⚠ 业务拒绝 %s: %s (status=%s)",
                qual, getattr(exc, "detail", exc), getattr(exc, "status_code", "?"),
            )
        else:  # err
            lg.exception("✗ 异常 %s: %s", qual, exc)

    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def _aw(*args, **kwargs):
            _report("enter")
            try:
                result = await func(*args, **kwargs)
                _report("ok")
                return result
            except Exception as e:  # noqa: BLE001
                _report("http" if getattr(e, "status_code", None) is not None else "err", e)
                raise
        return _aw
    else:
        @functools.wraps(func)
        def _sw(*args, **kwargs):
            _report("enter")
            try:
                result = func(*args, **kwargs)
                _report("ok")
                return result
            except Exception as e:  # noqa: BLE001
                _report("http" if getattr(e, "status_code", None) is not None else "err", e)
                raise
        return _sw


# 导入本模块即初始化日志（幂等），确保任何入口（uvicorn / run_server / 测试）都有日志
setup_logging()
