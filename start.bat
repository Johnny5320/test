@echo off
chcp 65001 >nul 2>&1
title Judicial System

echo ============================================
echo   Judicial System - Start
echo ============================================
echo.

cd /d "%~dp0judicial-system\backend"

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
echo [ERROR] Python not found. Install Python 3.10+
echo https://www.python.org/downloads/
pause
exit /b 1

:found
%PYTHON_CMD% --version
echo Using: %PYTHON_CMD%

if not exist ".venv" (
    echo [1/3] Creating venv...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create venv
        pause
        exit /b 1
    )
    echo Done
)

call .venv\Scripts\activate.bat

if not exist ".venv\.deps_installed" (
    echo [2/3] Installing deps...
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt -q
    if %errorlevel% neq 0 (
        echo [ERROR] Install failed
        pause
        exit /b 1
    )
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple rapidocr-onnxruntime -q 2>nul
    echo. > .venv\.deps_installed
    echo Done
)

if not exist ".env" (
    copy .env.example .env >nul
)

echo [3/3] Starting...
echo.
echo ============================================
echo   http://localhost:8000
echo   admin / admin123
echo   Ctrl+C to stop
echo ============================================
echo.

%PYTHON_CMD% -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
