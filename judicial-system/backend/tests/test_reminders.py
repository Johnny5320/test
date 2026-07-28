"""提醒系统 API 测试"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool
from datetime import date, timedelta

from app.main import app
from app.core.database import get_session
from app.models import User, Person, Visit
from app.core.security import hash_password


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="testadmin", hashed_password=hash_password("test123"), real_name="测试", role="director")
        session.add(user)
        session.commit()

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as c:
        login = c.post("/api/auth/login", json={"username": "testadmin", "password": "test123"})
        c.headers["Authorization"] = f"Bearer {login.json()['data']['access_token']}"
        yield c
    app.dependency_overrides.clear()


def test_reminders_empty(client):
    """空数据时提醒汇总"""
    resp = client.get("/api/reminders")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["expiring_30d"] == 0
    assert data["expiring_7d"] == 0
    assert data["overdue_expired"] == 0
    assert data["visit_overdue"] == 0
    assert data["quarter_deadline_days"] >= 0


def test_expiring_30d(client):
    """30天内到期"""
    future = date.today() + timedelta(days=20)
    client.post("/api/persons", json={
        "name": "张三", "id_card": "32010219900100100X",
        "status": "在帮", "edu_end_date": future.isoformat(),
    })
    resp = client.get("/api/reminders")
    assert resp.json()["data"]["expiring_30d"] == 1
    assert len(resp.json()["data"]["expiring_list"]) == 1
    assert resp.json()["data"]["expiring_list"][0]["level"] == "30天"


def test_expiring_7d(client):
    """7天内到期"""
    future = date.today() + timedelta(days=5)
    client.post("/api/persons", json={
        "name": "李四", "id_card": "32010219900202123X",
        "status": "在帮", "edu_end_date": future.isoformat(),
    })
    resp = client.get("/api/reminders")
    assert resp.json()["data"]["expiring_7d"] == 1
    assert resp.json()["data"]["expiring_list"][0]["level"] == "7天"


def test_overdue_expired(client):
    """已超期"""
    past = date.today() - timedelta(days=10)
    client.post("/api/persons", json={
        "name": "王五", "id_card": "320102199001010010",
        "status": "在帮", "edu_end_date": past.isoformat(),
    })
    resp = client.get("/api/reminders")
    assert resp.json()["data"]["overdue_expired"] == 1


def test_visit_overdue(client):
    """超期未走访"""
    # 创建人员（高风险，默认30天间隔）
    create_resp = client.post("/api/persons", json={
        "name": "赵六", "id_card": "320102199001010029",
        "status": "在帮", "risk_level": "高",
    })
    person_id = create_resp.json()["data"]["id"]

    # 添加一条45天前的走访记录
    old_date = (date.today() - timedelta(days=45)).isoformat()
    client.post("/api/visits", json={
        "person_id": person_id, "visit_date": old_date,
        "visitor": "张科员", "visit_method": "上门",
    })

    resp = client.get("/api/reminders")
    assert resp.json()["data"]["visit_overdue"] == 1
    assert resp.json()["data"]["visit_overdue_list"][0]["name"] == "赵六"
    assert resp.json()["data"]["visit_overdue_list"][0]["overdue_days"] > 0


def test_visit_overdue_no_visit(client):
    """从未走访过"""
    client.post("/api/persons", json={
        "name": "钱七", "id_card": "320102199001010037",
        "status": "在帮", "risk_level": "高",
        "edu_start_date": (date.today() - timedelta(days=60)).isoformat(),
    })
    resp = client.get("/api/reminders")
    assert resp.json()["data"]["visit_overdue"] == 1


def test_visit_interval_custom(client):
    """自定义走访间隔"""
    create_resp = client.post("/api/persons", json={
        "name": "测试", "id_card": "320102199001010045",
        "status": "在帮", "risk_level": "低",
        "visit_interval_days": 180,
    })
    assert create_resp.json()["data"]["visit_interval_days"] == 180


def test_quarter_deadline(client):
    """季度归档截止日期"""
    resp = client.get("/api/reminders")
    data = resp.json()["data"]
    assert "quarter_deadline_days" in data
    assert "quarter_deadline_date" in data
    assert data["quarter_deadline_days"] >= 0
