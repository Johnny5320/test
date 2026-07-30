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
        login = c.post("/api/auth/login", json={"real_name": "测试", "password": "test123"})
        c.headers["Authorization"] = f"Bearer {login.json()['data']['access_token']}"
        yield c
    app.dependency_overrides.clear()


def test_reminders_empty(client):
    """空数据时提醒汇总"""
    resp = client.get("/api/reminders")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["dismiss_30d"] == 0
    assert data["dismiss_7d"] == 0
    assert data["overdue_expired"] == 0
    assert data["visit_overdue"] == 0
    assert data["visit_due_soon"] == 0
    assert data["quarter_deadline_days"] >= 0


def test_expiring_30d(client):
    """30天内即将解除"""
    future = date.today() + timedelta(days=20)
    client.post("/api/persons", json={
        "name": "张三", "id_card": "320102197203030029",
        "status": "在帮", "edu_end_date": future.isoformat(),
    })
    resp = client.get("/api/reminders")
    assert resp.json()["data"]["dismiss_30d"] == 1
    assert len(resp.json()["data"]["dismiss_list"]) == 1
    assert resp.json()["data"]["dismiss_list"][0]["level"] == "30天"


def test_expiring_7d(client):
    """7天内即将解除"""
    future = date.today() + timedelta(days=5)
    client.post("/api/persons", json={
        "name": "李四", "id_card": "320102197304040031",
        "status": "在帮", "edu_end_date": future.isoformat(),
    })
    resp = client.get("/api/reminders")
    assert resp.json()["data"]["dismiss_7d"] == 1
    assert resp.json()["data"]["dismiss_list"][0]["level"] == "7天"


def test_overdue_expired(client):
    """已超期"""
    past = date.today() - timedelta(days=10)
    client.post("/api/persons", json={
        "name": "王五", "id_card": "320102197405050044",
        "status": "在帮", "edu_end_date": past.isoformat(),
    })
    resp = client.get("/api/reminders")
    assert resp.json()["data"]["overdue_expired"] == 1


def test_visit_overdue(client):
    """超期未走访（走访间隔人为填写，不再按风险自动赋值）"""
    create_resp = client.post("/api/persons", json={
        "name": "赵六", "id_card": "320102197506060057",
        "status": "在帮", "risk_level": "高", "visit_interval_days": 90,
    })
    person_id = create_resp.json()["data"]["id"]

    # 添加一条100天前的走访记录（超过默认90天间隔 → 超期）
    old_date = (date.today() - timedelta(days=100)).isoformat()
    client.post("/api/visits", json={
        "person_id": person_id, "visit_date": old_date,
        "visitor": "张科员", "visit_method": "上门",
    })

    resp = client.get("/api/reminders")
    assert resp.json()["data"]["visit_overdue"] == 1
    assert resp.json()["data"]["visit_overdue_list"][0]["name"] == "赵六"
    assert resp.json()["data"]["visit_overdue_list"][0]["overdue_days"] > 0


def test_visit_overdue_no_visit(client):
    """从未走访过（帮教起始已超过间隔）"""
    client.post("/api/persons", json={
        "name": "钱七", "id_card": "32010219760707006X",
        "status": "在帮", "risk_level": "高", "visit_interval_days": 30,
        "edu_start_date": (date.today() - timedelta(days=100)).isoformat(),
    })
    resp = client.get("/api/reminders")
    assert resp.json()["data"]["visit_overdue"] == 1


def test_visit_due_soon(client):
    """临期未走访：距下次应访日 ≤15 天且未超期（显式间隔 90 天）"""
    create_resp = client.post("/api/persons", json={
        "name": "孙八", "id_card": "320102197809090085",
        "status": "在帮", "risk_level": "中", "visit_interval_days": 90,
    })
    person_id = create_resp.json()["data"]["id"]
    # 上次走访 80 天前，间隔 90 → 距应访日 10 天（临期）
    old_date = (date.today() - timedelta(days=80)).isoformat()
    client.post("/api/visits", json={
        "person_id": person_id, "visit_date": old_date,
        "visitor": "张科员", "visit_method": "上门",
    })
    resp = client.get("/api/reminders")
    data = resp.json()["data"]
    assert data["visit_due_soon"] == 1
    assert data["visit_due_soon_list"][0]["due_in_days"] == 10
    assert data["visit_overdue"] == 0


def test_visit_interval_custom(client):
    """自定义走访间隔"""
    create_resp = client.post("/api/persons", json={
        "name": "测试", "id_card": "320102197708080072",
        "status": "在帮", "risk_level": "低",
        "visit_interval_days": 180,
    })
    assert create_resp.json()["data"]["visit_interval_days"] == 180


def test_interval_not_overridden_by_risk(client):
    """走访间隔不再按风险等级自动赋值：高风险不传间隔 → 默认 90（而非旧逻辑的 30）"""
    create_resp = client.post("/api/persons", json={
        "name": "周九", "id_card": "320102197203030029",
        "status": "在帮", "risk_level": "高",
    })
    assert create_resp.json()["data"]["visit_interval_days"] == 90


def test_first_visit_rule_30_days(client):
    """首访规则：从未走访 → 帮教开始后30天内须首访（超30天即超期，不再等90天间隔）"""
    client.post("/api/persons", json={
        "name": "首访超期", "id_card": "320102197304040031",
        "status": "在帮", "risk_level": "低", "visit_interval_days": 90,
        "edu_start_date": (date.today() - timedelta(days=40)).isoformat(),
    })
    resp = client.get("/api/reminders")
    data = resp.json()["data"]
    # 旧逻辑：40 < 90 不提醒；新逻辑：首访应在30天内 → 已超期10天
    assert data["visit_overdue"] == 1
    assert data["visit_overdue_list"][0]["overdue_days"] == 10


def test_first_visit_capped_by_edu_end(client):
    """封顶规则：从未走访且帮教截止日早于首访30天线 → 应访日封顶到帮教截止日（人才场景）"""
    client.post("/api/persons", json={
        "name": "人才场景", "id_card": "320102197506060057",
        "status": "在帮", "risk_level": "低", "visit_interval_days": 90,
        "edu_start_date": (date.today() - timedelta(days=26)).isoformat(),
        "edu_end_date": (date.today() + timedelta(days=3)).isoformat(),
    })
    resp = client.get("/api/reminders")
    data = resp.json()["data"]
    # 首访线 = 开始+30 = 4天后，但帮教截止 3 天后更早 → 应访日=截止日，剩3天 → 临期
    assert data["visit_due_soon"] == 1
    assert data["visit_due_soon_list"][0]["due_in_days"] == 3
    assert data["visit_overdue"] == 0


def test_quarter_deadline(client):
    """季度归档截止日期"""
    resp = client.get("/api/reminders")
    data = resp.json()["data"]
    assert "quarter_deadline_days" in data
    assert "quarter_deadline_date" in data
    assert data["quarter_deadline_days"] >= 0
