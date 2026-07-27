#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安置帮教智能台账系统 — 数据备份脚本（离线单机版）

功能：
  1. 对 SQLite 执行 WAL 检查点，把未落盘数据写回主库；
  2. 复制 data.db（+ -wal / -shm 若在线）与 uploads/ 到带时间戳的备份目录；
  3. 仅保留最近 KEEP 份，自动清理更早的备份（防止无限占用空间）。

用法：
  python backup_db.py            # 默认保留最近 10 份
  python backup_db.py --keep 20  # 保留最近 20 份

说明：脚本与 judicial-system/backend 同工程；路径按此推算，无需手动指定。
      备份产物位于 本脚本同级的 backups/ 目录下，可整体拷贝到 U 盘异地保存。
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR / "judicial-system" / "backend"
DB_PATH = BACKEND_DIR / "data.db"
UPLOAD_DIR = BACKEND_DIR / "uploads"
BACKUP_ROOT = SCRIPT_DIR / "backups"
KEEP_DEFAULT = 10


def checkpoint_and_copy(dest_db: Path) -> str:
    """对在线 SQLite 做 WAL 检查点并复制主库文件。返回状态说明。"""
    # 复制 -wal / -shm（若存在），先复制它们以保证一致性
    for suffix in ("-wal", "-shm"):
        src = DB_PATH.with_suffix(suffix) if DB_PATH.suffix == ".db" else None
        # data.db -> data-wal / data-shm
        extra = DB_PATH.parent / (DB_PATH.name + suffix)
        if extra.exists():
            shutil.copy2(extra, dest_db.parent / (dest_db.name + suffix))
    # 连接做检查点，把 WAL 内容刷回主库
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
        conn.close()
        note = "已执行 WAL 检查点"
    except Exception as e:
        note = f"检查点跳过（库可能未在使用）: {e}"
    shutil.copy2(DB_PATH, dest_db)
    return note


def main():
    ap = argparse.ArgumentParser(description="台账系统数据备份")
    ap.add_argument("--keep", type=int, default=KEEP_DEFAULT, help="保留最近几份备份")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"[跳过] 未找到数据库：{DB_PATH}")
        sys.exit(0)

    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir = BACKUP_ROOT / f"backup_{stamp}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_db = dest_dir / "data.db"

    note = checkpoint_and_copy(dest_db)
    print(f"[OK] 数据库已备份 -> {dest_db}  ({note})")

    if UPLOAD_DIR.exists():
        shutil.copytree(UPLOAD_DIR, dest_dir / "uploads", dirs_exist_ok=True)
        print(f"[OK] 附件已备份 -> {dest_dir / 'uploads'}")
    else:
        print("[提示] 无 uploads 目录，跳过附件备份")

    # 滚动清理：仅保留最近 keep 份
    backups = sorted(
        [d for d in BACKUP_ROOT.iterdir() if d.is_dir() and d.name.startswith("backup_")],
        key=lambda d: d.name,
    )
    excess = backups[:-args.keep] if len(backups) > args.keep else []
    for old in excess:
        shutil.rmtree(old)
        print(f"[清理] 删除旧备份 {old.name}")
    print(f"[完成] 当前共保留 {min(len(backups), args.keep)} 份备份（keep={args.keep}）")


if __name__ == "__main__":
    main()
