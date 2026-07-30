#!/usr/bin/env bash
# 安置帮教智能台账系统 — 数据备份（Linux/macOS）
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 backup_db.py "$@"
