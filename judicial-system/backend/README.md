# 安置帮教智能台账系统 — 后端

## 快速开始

```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 复制配置
cp .env.example .env

# 3. 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. 访问 API 文档
# http://localhost:8000/docs
```

## 默认账号

- 用户名: `admin`
- 密码: `admin123`

## 运行测试

```bash
pip install pytest httpx
pytest tests/ -v
```

## 技术栈

- FastAPI + SQLModel + SQLite
- JWT 认证（python-jose）
- RapidOCR（扫描识别）
- openpyxl（Excel导出）
