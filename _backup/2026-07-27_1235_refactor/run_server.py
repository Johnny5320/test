"""启动入口"""
import sys
import os

# 确保工作目录为 exe 所在目录
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

from app.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
