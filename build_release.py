"""
安置帮教智能台账系统 — 发布打包脚本
用法: py -3 build_release.py
输出: dist/安置帮教智能台账系统_安装程序.exe
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
    print("[1/6] 清理旧构建...")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)
    for d in [BACKEND_DIR / "build", BACKEND_DIR / "dist"]:
        if d.is_dir():
            shutil.rmtree(d)
    print("  清理完成")


def build_exe():
    """使用 PyInstaller 构建 exe（无控制台窗口）"""
    print("[2/6] 构建 exe（无控制台模式）...")

    # PyInstaller 参数
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", "安置帮教系统",
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
        # 关键：隐藏控制台窗口
        "--noconsole",
        # 排除不需要的模块（减小体积）
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy.random._examples",
        # 入口文件
        str(BACKEND_DIR / "run_server.py"),
    ]

    run(" ".join(cmd), cwd=str(BACKEND_DIR))
    print("  构建完成")


def copy_frontend():
    """复制前端文件"""
    print("[3/6] 复制前端文件...")
    target = DIST_APP_DIR / "frontend"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(FRONTEND_DIR, target)
    print("  复制完成")


def create_launcher():
    """创建 README"""
    print("[4/6] 创建 README...")
    readme_content = f'''# {APP_NAME}

## 使用说明

1. 运行安装程序，按向导完成安装
2. 安装完成后，桌面会出现"安置帮教系统"图标
3. 双击图标启动系统
4. 打开浏览器访问 http://localhost:8000
5. 使用默认账号登录：
   - 用户名：admin
   - 密码：admin123
6. 首次登录后请修改默认密码

## 注意事项

- 数据库文件位于安装目录的 `data.db`，请定期备份
- 上传的文件保存在安装目录的 `uploads/` 目录
- 如需修改端口，请联系管理员

## 系统要求

- Windows 10/11
- 无需安装 Python 或其他依赖

## 卸载

- 打开"控制面板" -> "程序和功能"
- 找到"安置帮教智能台账系统"，点击卸载
'''
    readme_path = DIST_APP_DIR / "README.md"
    readme_path.write_text(readme_content, encoding="utf-8")
    print("  创建完成")


def build_installer():
    """使用 NSIS 编译安装程序（先复制到临时ASCII路径避免NSIS中文路径问题）"""
    print("[5/6] 编译安装程序...")

    # 查找 makensis
    makensis_paths = [
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
    ]
    makensis = None
    for p in makensis_paths:
        if Path(p).exists():
            makensis = p
            break

    if not makensis:
        print("  [ERROR] 未找到 NSIS，请先安装 NSIS")
        print("  下载地址: https://nsis.sourceforge.io/Download")
        sys.exit(1)

    # NSIS 不支持中文源路径，复制到临时ASCII目录
    import tempfile, shutil
    tmp_dir = Path(tempfile.mkdtemp(prefix="nsis_build_"))
    tmp_app = tmp_dir / "app"
    shutil.copytree(DIST_APP_DIR, tmp_app)

    # 重命名中文子目录为ASCII
    for item in tmp_app.iterdir():
        if item.is_dir() and not item.name.isascii():
            new_name = "app_bin" if "安置" in item.name or "系统" in item.name else item.name
            item.rename(tmp_app / new_name)

    # 生成临时NSIS脚本（纯ASCII路径）
    nsis_template = (PROJECT_ROOT / "installer.nsi").read_text(encoding="utf-8")
    # 替换源路径占位符为临时路径
    nsis_content = nsis_template.replace(
        '__NSIS_SRC__',
        str(tmp_app)
    )
    tmp_nsi = tmp_dir / "installer.nsi"
    tmp_nsi.write_text(nsis_content, encoding="utf-8")

    # 编译
    cmd = f'"{makensis}" "{tmp_nsi}"'
    run(cmd, cwd=str(tmp_dir))

    # 清理临时目录
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("  安装程序编译完成")


def cleanup_temp_files():
    """清理临时文件"""
    print("[6/6] 清理临时文件...")
    # 删除临时的 spec 文件
    spec_file = BACKEND_DIR / "安置帮教系统.spec"
    if spec_file.exists():
        spec_file.unlink()
    # 删除 build 目录
    build_dir = BACKEND_DIR / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    print("  清理完成")


def main():
    print(f"===== {APP_NAME} 发布打包 =====")
    print()
    print("打包流程：")
    print("  1. PyInstaller 构建 exe（无控制台窗口）")
    print("  2. NSIS 编译标准安装程序")
    print("  3. 输出：安置帮教智能台账系统_安装程序.exe")
    print()

    clean()
    build_exe()
    copy_frontend()
    create_launcher()
    build_installer()
    cleanup_temp_files()

    installer_path = PROJECT_ROOT.parent / f"{APP_NAME}_安装程序.exe"
    if installer_path.exists():
        size_mb = installer_path.stat().st_size / 1024 / 1024
        print()
        print("===== 打包完成 =====")
        print(f"  安装程序: {installer_path}")
        print(f"  文件大小: {size_mb:.1f} MB")
        print()
        print("功能特性：")
        print("  - 标准 Windows 安装向导")
        print("  - 自动创建桌面快捷方式")
        print("  - 自动创建开始菜单")
        print("  - 启动无 CMD 窗口")
        print("  - 支持控制面板卸载")
        print()
    else:
        print()
        print("[ERROR] 安装程序生成失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
