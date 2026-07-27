"""
安置帮教智能台账系统 — 发布打包脚本
用法: py -3 build_release.py
输出: dist/安置帮教智能台账系统/
"""
import subprocess
import sys
import shutil
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / "judicial-system" / "backend"
FRONTEND_DIR = PROJECT_ROOT / "judicial-system" / "frontend"
DIST_DIR = PROJECT_ROOT / "dist"
APP_NAME = "安置帮教智能台账系统"
DIST_APP_DIR = DIST_DIR / APP_NAME


def run(cmd, cwd=None):
    print(f"  > {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"  [ERROR] 命令失败: {cmd}")
        sys.exit(1)


def clean():
    """清理旧的构建产物"""
    print("[1/5] 清理旧构建...")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)
    for d in [BACKEND_DIR / "build", BACKEND_DIR / "dist", BACKEND_DIR / "*.spec"]:
        if d.is_dir():
            shutil.rmtree(d)
    print("  清理完成")


def build_exe():
    """使用 PyInstaller 构建 exe"""
    print("[2/5] 构建 exe...")

    # PyInstaller 参数
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", "server",
        "--onedir",
        "--workpath", str(BACKEND_DIR / "build"),
        "--distpath", str(DIST_APP_DIR),
        "--specpath", str(BACKEND_DIR),
        # 添加数据文件
        "--add-data", f"{FRONTEND_DIR};frontend",
        # 隐藏导入
        "--hidden-import", "app",
        "--hidden-import", "app.core",
        "--hidden-import", "app.api",
        "--hidden-import", "app.models",
        "--hidden-import", "app.schemas",
        "--hidden-import", "sqlmodel",
        "--hidden-import", "pydantic",
        "--hidden-import", "pydantic_settings",
        "--hidden-import", "jose",
        "--hidden-import", "bcrypt",
        "--hidden-import", "multipart",
        "--hidden-import", "uvicorn",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "rapidocr_onnxruntime",
        "--hidden-import", "onnxruntime",
        "--hidden-import", "openpyxl",
        "--hidden-import", "aiofiles",
        # 排除不需要的模块（减小体积）
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy.random._examples",
        # 入口文件
        str(BACKEND_DIR / "run_server.py"),
    ]

    run(" ".join(cmd), cwd=str(BACKEND_DIR))
    print("  构建完成")


def create_runner():
    """创建启动入口 run_server.py"""
    print("[3/5] 创建启动入口...")
    runner_code = '''"""启动入口"""
import sys
import os

# 确保工作目录为 exe 所在目录
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

from app.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
    runner_path = BACKEND_DIR / "run_server.py"
    runner_path.write_text(runner_code, encoding="utf-8")
    print("  创建完成")


def copy_frontend():
    """复制前端文件"""
    print("[4/5] 复制前端文件...")
    target = DIST_APP_DIR / "frontend"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(FRONTEND_DIR, target)
    print("  复制完成")


def create_launcher():
    """创建用户启动脚本"""
    print("[5/5] 创建启动脚本...")

    # Windows 启动脚本
    bat_content = f'''@echo off
chcp 65001 >nul 2>&1
title {APP_NAME}

echo ============================================
echo   {APP_NAME}
echo ============================================
echo.
echo   正在启动服务，请稍候...
echo.
echo   访问地址: http://localhost:8000
echo   默认账号: admin / admin123
echo   首次登录请修改密码
echo.
echo   按 Ctrl+C 可停止服务
echo ============================================
echo.

cd /d "%~dp0"
server\\server.exe

pause
'''
    bat_path = DIST_APP_DIR / "启动.bat"
    bat_path.write_text(bat_content, encoding="utf-8")

    # README
    readme_content = f'''# {APP_NAME}

## 使用说明

1. 双击 `启动.bat` 启动系统
2. 打开浏览器访问 http://localhost:8000
3. 使用默认账号登录：
   - 用户名：admin
   - 密码：admin123
4. 首次登录后请修改默认密码

## 注意事项

- 数据库文件位于 `data.db`，请定期备份
- 上传的文件保存在 `uploads/` 目录
- 如需修改端口，请编辑 `启动.bat` 中的参数

## 系统要求

- Windows 10/11
- 无需安装 Python 或其他依赖
'''
    readme_path = DIST_APP_DIR / "README.md"
    readme_path.write_text(readme_content, encoding="utf-8")

    print("  创建完成")


def main():
    print(f"===== {APP_NAME} 发布打包 =====")
    print()

    create_runner()
    clean()
    build_exe()
    copy_frontend()
    create_launcher()

    # 清理临时文件
    spec_file = BACKEND_DIR / "server.spec"
    if spec_file.exists():
        spec_file.unlink()

    print()
    print("===== 打包完成 =====")
    print(f"  输出目录: {DIST_APP_DIR}")
    print(f"  将整个目录压缩为 zip 即可发布到 GitHub")
    print()

    # 计算总大小
    total_size = sum(f.stat().st_size for f in DIST_APP_DIR.rglob("*") if f.is_file())
    print(f"  总大小: {total_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
