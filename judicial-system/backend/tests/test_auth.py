"""认证 API 测试"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.database import get_session
from app.models import User
from app.core.security import hash_password


@pytest.fixture
def client():
    """测试客户端 — 使用内存数据库"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # 创建测试用户
        user = User(
            username="testadmin",
            hashed_password=hash_password("test123"),
            real_name="测试管理员",
            role="director",
        )
        session.add(user)
        session.commit()

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_login_success(client):
    """登录成功"""
    resp = client.post("/api/auth/login", json={
        "real_name": "测试管理员",
        "password": "test123",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    """密码错误"""
    resp = client.post("/api/auth/login", json={
        "real_name": "测试管理员",
        "password": "wrong",
    })
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    """用户不存在"""
    resp = client.post("/api/auth/login", json={
        "real_name": "nobody",
        "password": "test123",
    })
    assert resp.status_code == 401


def test_get_me(client):
    """获取当前用户信息"""
    # 先登录
    login_resp = client.post("/api/auth/login", json={
        "real_name": "测试管理员",
        "password": "test123",
    })
    token = login_resp.json()["data"]["access_token"]

    resp = client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {token}",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "testadmin"
    assert resp.json()["data"]["role"] == "director"


def test_get_me_no_token(client):
    """未登录访问"""
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


def test_refresh_token(client):
    """刷新Token"""
    login_resp = client.post("/api/auth/login", json={
        "real_name": "测试管理员",
        "password": "test123",
    })
    refresh = login_resp.json()["data"]["refresh_token"]

    resp = client.post("/api/auth/refresh", json={
        "refresh_token": refresh,
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()["data"]
