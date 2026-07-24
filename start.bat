@echo off
chcp 65001 >nul 2>&1
title 安置帮教智能台账系统

echo ============================================
echo   安置帮教智能台账系统 — 一键启动
echo ============================================
echo.

cd /d "%~dp0judicial-system\backend"

REM 按优先级查找可用的Python: py -3 > python3 > python
set "PYTHON_CMD="
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3"
    goto :found_python
)
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python3"
    goto :found_python
)
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto :found_python
)
echo [ERROR] 未找到 Python，请先安装 Python 3.10+
echo 下载地址: https://www.python.org/downloads/
pause
exit /b 1

:found_python
%PYTHON_CMD% --version
echo 使用Python: %PYTHON_CMD%

REM 检查虚拟环境
if not exist ".venv" (
    echo [1/3] 首次运行，正在创建虚拟环境...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo 虚拟环境创建完成
)

REM 激活虚拟环境
call .venv\Scripts\activate.bat

REM 安装依赖
if not exist ".venv\.deps_installed" (
    echo [2/3] 正在安装依赖（首次需要几分钟）...
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt -q
    if %errorlevel% neq 0 (
        echo [ERROR] 安装依赖失败，请检查网络连接
        pause
        exit /b 1
    )
    echo. > .venv\.deps_installed
    echo 依赖安装完成
)

REM 复制配置文件
if not exist ".env" (
    copy .env.example .env >nul
    echo 已创建默认配置文件 .env
)

REM 启动服务
echo [3/3] 启动服务...
echo.
echo ============================================
echo   系统已启动！
echo   本机访问: http://localhost:8000
echo   默认账号: admin / admin123
echo   首次登录请修改默认密码
echo ============================================
echo.
echo   按 Ctrl+C 可停止服务
echo   关闭此窗口也会停止服务
echo ============================================
echo.

%PYTHON_CMD% -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
