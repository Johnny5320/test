"""共享 fixtures"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.database import get_session
from app.models import User
from app.core.security import hash_password


@pytest.fixture(name="client")
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        admin = User(username="admin", hashed_password=hash_password("admin123"), real_name="管理员", role="director", force_change_password=False)
        session.add(admin)
        session.commit()

    def override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    c = TestClient(app)
    # 登录获取token并设置到headers（信封契约：data 内取 token）
    r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = r.json()["data"]["access_token"]
    c.headers["Authorization"] = f"Bearer {token}"
    yield c
    app.dependency_overrides.clear()
