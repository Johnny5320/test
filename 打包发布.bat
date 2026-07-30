@echo off
chcp 65001 >nul 2>&1
title 发布打包

echo ============================================
echo   安置帮教智能台账系统 — 发布打包
echo ============================================
echo.

cd /d "%~dp0"

REM 查找 Python
set "PYTHON_CMD="
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3"
    goto :found
)
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python3"
    goto :found
)
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto :found
)
echo [ERROR] 未找到 Python
pause
exit /b 1

:found
echo 使用 Python: %PYTHON_CMD%
echo.

REM 检查 PyInstaller
%PYTHON_CMD% -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 正在安装 PyInstaller...
    %PYTHON_CMD% -m pip install pyinstaller -q
)

REM 运行打包脚本
%PYTHON_CMD% build_release.py

echo.
pause
