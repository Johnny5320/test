"""安置帮教智能台账系统 — 主应用"""
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import create_db_and_tables, get_session
from app.core.security import hash_password, verify_password
from app.models import User, Person, Visit, EditLog, File
from app.api import auth, persons, visits, files, reminders
from sqlmodel import Session, select


def get_base_dir() -> Path:
    """获取应用根目录（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent


def init_default_user():
    """创建默认管理员账号（首次启动时）；若从未改过密码则确保默认密码可用"""
    from app.core.database import engine
    with Session(engine) as session:
        admin = session.exec(select(User).where(User.username == "admin")).first()
        if not admin:
            admin = User(
                username="admin",
                hashed_password=hash_password("admin123"),
                real_name="系统管理员",
                role="director",
                force_change_password=True,  # 首次登录强制改密码
            )
            session.add(admin)
            session.commit()
            print("[OK] 默认管理员已创建: admin / admin123  （首次登录请修改密码）")
        else:
            # 默认管理员若从未改过密码（force_change_password 仍为 True），
            # 但库中哈希与默认密码不一致时，重置回 admin123，避免无法登录。
            if admin.force_change_password and not verify_password("admin123", admin.hashed_password):
                admin.hashed_password = hash_password("admin123")
                session.add(admin)
                session.commit()
                print("[OK] 默认管理员密码已重置为 admin123（force_change_password 仍为 True）")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    create_db_and_tables()
    init_default_user()
    print(f"[START] {settings.APP_NAME} 启动完成")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.3.0",
    lifespan=lifespan,
)

# CORS — 本地部署，限制为 localhost / 0.0.0.0
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://0.0.0.0:8000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(persons.router)
app.include_router(visits.router)
app.include_router(files.router)
app.include_router(reminders.router)


# 前端 HTML 路径（兼容 PyInstaller 打包，优先查找多个候选目录）
def get_frontend_dir() -> Path:
    base = get_base_dir()
    candidates = [base / "frontend", base.parent / "frontend"]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "frontend")
    for c in candidates:
        if (c / "index_v2.html").exists() or (c / "index.html").exists():
            return c
    return candidates[0]


FRONTEND_DIR = get_frontend_dir()


@app.get("/")
def root():
    """返回前端页面"""
    index_html = FRONTEND_DIR / "index_v2.html"
    if not index_html.exists():
        index_html = FRONTEND_DIR / "index.html"
    if index_html.exists():
        return FileResponse(index_html, media_type="text/html")
    return {"message": settings.APP_NAME, "version": "0.3.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理 — 生产环境不暴露堆栈"""
    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )
