"""数据库迁移：补齐缺失列（保留现有数据）

用法：
    python tools/migrate_db.py

原理：导入所有 SQLModel 模型以填充 metadata，
逐表对比模型定义的列与 SQLite 实际列，
对缺失列执行 `ALTER TABLE <t> ADD COLUMN <col> <type>`。
新增列一律不加 NOT NULL，确保已存在数据不被破坏。
"""
import os
import sqlite3
import sys

# 让脚本能 import 到 backend 的 app 包
BACKEND = os.path.join(os.path.dirname(__file__), "..", "judicial-system", "backend")
sys.path.insert(0, os.path.abspath(BACKEND))

from sqlmodel import SQLModel
import app.models  # 触发所有模型注册到 metadata
from app.core.database import engine

DB_PATH = os.path.join(BACKEND, "data.db")


def sqlite_type(column) -> str:
    """把 SQLAlchemy 列类型转成 SQLite 可用的类型声明。"""
    t = str(column.type).upper()
    # SQLite 对类型名很宽松，直接用原始类型字符串即可
    return t


def main():
    if not os.path.exists(DB_PATH):
        print(f"[跳过] 数据库不存在：{DB_PATH}，将由 create_db_and_tables 创建。")
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    total_added = 0
    for table_name, table in SQLModel.metadata.tables.items():
        # 当前表的已有列
        existing = {r[1] for r in cur.execute(f"PRAGMA table_info('{table_name}')")}
        for column in table.columns:
            col_name = column.name
            if col_name in existing:
                continue
            # 缺列 -> 添加（不带 NOT NULL / DEFAULT，避免破坏现有行）
            ddl_type = sqlite_type(column)
            sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {ddl_type}'
            try:
                cur.execute(sql)
                print(f"[+] {table_name}.{col_name} ({ddl_type})")
                total_added += 1
            except Exception as e:
                print(f"[!] 添加 {table_name}.{col_name} 失败: {e}")

    con.commit()
    con.close()
    print(f"\n完成：共补齐 {total_added} 个缺失列。")


if __name__ == "__main__":
    main()
