# ============================================================
#  安置帮教智能台账系统 — Dockerfile
#  多阶段构建，优化镜像体积
# ============================================================

# ── 阶段 1: 构建依赖 ──────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# 系统依赖（编译时）
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY judicial-system/backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── 阶段 2: 运行镜像 ──────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="judicial-system"
LABEL description="安置帮教智能台账系统 后端服务"

WORKDIR /app

# 从 builder 阶段复制已安装的 Python 包
COPY --from=builder /install /usr/local

# 复制后端代码
COPY judicial-system/backend/ .

# 创建数据目录（挂载点）
RUN mkdir -p /app/uploads /app/data

# 非 root 用户运行
RUN useradd -r -s /bin/false appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
