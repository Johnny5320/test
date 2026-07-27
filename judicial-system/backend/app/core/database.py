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
        cursor.execute("PRAGMA synchronous=NORMAL")  # WAL 下安全且写性能更好
        logger.info("SQLite PRAGMA 已设置: WAL, busy_timeout=5000, foreign_keys=ON, synchronous=NORMAL")
    finally:
        cursor.close()


@log_call
def create_db_and_tables():
    """创建数据库表"""
    SQLModel.metadata.create_all(engine)
    logger.info("数据库表创建/校验完成")


@log_call
def migrate_missing_columns():
    """启动时自动补齐缺失列（幂等，带默认值，保留现有数据）。
    替代 tools/migrate_db.py 的手动执行：create_all 只建新表不补列，
    老用户升级后新列缺失会在运行时才爆 OperationalError，迁移到启动期消除。"""
    from sqlalchemy import text
    import app.models  # noqa: F401  确保 metadata 已填充全部表

    with engine.begin() as conn:
        for table_name, table in SQLModel.metadata.tables.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(
                    f"PRAGMA table_info('{table_name}')")
            }
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {col.type}'
                default = _column_default_sql(col)
                if default is not None:
                    ddl += f" DEFAULT {default}"
                conn.exec_driver_sql(text(ddl))
                logger.info("迁移: 补列 %s.%s DEFAULT %s", table_name, col.name, default)


def _column_default_sql(col):
    """提取列的标量默认值并转为 SQL 字面量；无默认值返回 None"""
    if col.default is None or not getattr(col.default, "is_scalar", False):
        return None
    value = col.default.arg
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, (int, float)):
        return str(value)
    return None


def get_session():
    """获取数据库会话（FastAPI 依赖注入用）"""
    logger.debug("打开数据库会话")
    with Session(engine) as session:
        yield session
    logger.debug("关闭数据库会话")
