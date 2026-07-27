"""数据库连接"""
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import event
from app.core.config import settings

import logging
from app.core.logging_config import log_call
logger = logging.getLogger("judicial.core.database")

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False},  # SQLite 需要
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """SQLite 健壮性设置（每次建立连接时执行）：
    - journal_mode=WAL：写操作不再阻塞读，并发更稳，崩溃恢复更好
    - busy_timeout=5000：写锁等待 5s，避免 'database is locked'
    - foreign_keys=ON：启用外键约束
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        logger.info("SQLite PRAGMA 已设置: journal_mode=WAL, busy_timeout=5000, foreign_keys=ON")
    finally:
        cursor.close()


@log_call
def create_db_and_tables():
    """创建数据库表"""
    SQLModel.metadata.create_all(engine)
    logger.info("数据库表创建/校验完成")


def get_session():
    """获取数据库会话（FastAPI 依赖注入用）"""
    logger.debug("打开数据库会话")
    with Session(engine) as session:
        yield session
    logger.debug("关闭数据库会话")
