"""启动入口"""
import sys
import os
from pathlib import Path

if getattr(sys, "frozen", False):
    os.chdir(Path(sys.executable).parent)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="info")
