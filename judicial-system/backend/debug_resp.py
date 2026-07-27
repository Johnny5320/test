"""Debug: 看看 create person 实际返回什么"""
import json
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool
from app.main import app
from app.core.database import get_session
from app.models import User
from app.core.security import hash_password

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SQLModel.metadata.create_all(engine)
with Session(engine) as session:
    session.add(User(username="admin", hashed_password=hash_password("***"), real_name="管理员", role="director"))
    session.commit()

def get_test_session():
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_session] = get_test_session
with TestClient(app) as c:
    login = c.post("/api/auth/login", json={"username": "admin", "password": "***"})
    token = login.json()["data"]["access_token"]
    c.headers["Authorization"] = f"Bearer {token}"

    # Test 1: 正常创建
    r = c.post("/api/persons", json={"name": "张三", "id_card": "320102199001011234"})
    print("=== CREATE ===")
    print("Status:", r.status_code)
    print("Full response:", json.dumps(r.json(), ensure_ascii=False, indent=2))

    # Test 2: 小写x
    r2 = c.post("/api/persons", json={"name": "李四", "id_card": "32010219900101123x"})
    print("\n=== CREATE lowercase x ===")
    print("Status:", r2.status_code)
    print("Full response:", json.dumps(r2.json(), ensure_ascii=False, indent=2))

    # Test 3: 缺少必填
    r3 = c.post("/api/persons", json={"id_card": "320102199001011234"})
    print("\n=== CREATE missing name ===")
    print("Status:", r3.status_code)
    print("Full response:", json.dumps(r3.json(), ensure_ascii=False, indent=2))

    # Test 4: 列表
    r4 = c.get("/api/persons")
    print("\n=== LIST ===")
    print("Status:", r4.status_code)
    print("Full response:", json.dumps(r4.json(), ensure_ascii=False, indent=2))
