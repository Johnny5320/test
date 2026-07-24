#!/usr/bin/env bash
# 安置帮教智能台账系统 — 一键启动脚本 (Linux/macOS)
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/judicial-system/backend"

echo "============================================"
echo "  安置帮教智能台账系统 — 一键启动"
echo "============================================"
echo ""

cd "$BACKEND_DIR"

# 检查 Python
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then PYTHON="$cmd"; break; fi
done
[[ -z "$PYTHON" ]] && fail "未找到 Python，请先安装 Python 3.10+"

PY_VER=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
ok "Python $PY_VER"

# 虚拟环境
VENV_DIR="$BACKEND_DIR/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
    info "创建虚拟环境..."
    $PYTHON -m venv "$VENV_DIR"
    ok "虚拟环境已创建"
fi
source "$VENV_DIR/bin/activate"

# 安装依赖
if [[ ! -f "$VENV_DIR/.deps_installed" ]]; then
    info "安装依赖（首次需要几分钟）..."
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt -q
    touch "$VENV_DIR/.deps_installed"
    ok "依赖安装完成"
fi

# 配置文件
if [[ ! -f ".env" ]]; then
    cp .env.example .env
    ok "已创建默认配置 .env"
fi

# 启动
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo ""
echo "============================================"
echo "  系统已启动！"
echo "  本机访问: http://localhost:${PORT}"
echo "  局域网访问: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '本机IP'):${PORT}"
echo "  默认账号: admin / admin123"
echo "  首次登录请修改默认密码"
echo "============================================"
echo ""
echo "  按 Ctrl+C 可停止服务"
echo ""

exec python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
