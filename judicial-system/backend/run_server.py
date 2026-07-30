"""启动入口（无控制台版本）"""
import sys
import os
import logging
from pathlib import Path

# 确保工作目录为 exe 所在目录
if getattr(sys, "frozen", False):
    base_dir = Path(sys.executable).parent
    os.chdir(base_dir)

    # 配置日志到文件（无控制台模式）
    log_file = base_dir / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),  # 仍然写入stdout，但不会显示
        ],
    )

from app.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
