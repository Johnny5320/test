@echo off
chcp 65001 >nul 2>&1
title 台账系统数据备份
cd /d "%~dp0"
echo 正在备份台账数据（data.db + 附件）...
py -3 backup_db.py
if errorlevel 1 (
    echo [重试] 尝试 python ...
    python backup_db.py
)
echo.
echo 备份完成，产物位于 backups\ 目录，可拷贝到 U 盘异地保存。
pause
