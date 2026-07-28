"""走访记录测试 — v3.2 信封格式"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from app.main import app
from app.core.database import get_session
from app.models import User, Person
from app.core.security import hash_password


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(User(username="admin", hashed_password=hash_password("admin123"), real_name="管理员", role="director"))
        s.add(Person(name="张三", id_card="320102199001010010", status="在帮"))
        s.commit()
    app.dependency_overrides[get_session] = lambda: Session(engine)
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        c.headers["Authorization"] = f"Bearer {r.json()['data']['access_token']}"
        yield c
    app.dependency_overrides.clear()


def test_create_visit(client):
    """新增走访"""
    r = client.post("/api/visits", json={
        "person_id": 1, "visit_date": "2026-01-15", "visitor": "王科员", "visit_method": "上门",
        "content": "走访正常"
    })
    assert r.json().get("code") == 0
    assert r.json()["data"]["visitor"] == "王科员"


def test_create_abnormal_visit(client):
    """异常走访"""
    r = client.post("/api/visits", json={
        "person_id": 1, "visit_date": "2026-01-15", "visitor": "李科员", "visit_method": "电话",
        "has_abnormal": True, "abnormal_detail": "情绪波动"
    })
    assert r.json().get("code") == 0
    assert r.json()["data"]["has_abnormal"] is True


def test_list_visits(client):
    """走访列表"""
    client.post("/api/visits", json={"person_id": 1, "visit_date": "2026-01-01", "visitor": "A", "visit_method": "上门"})
    client.post("/api/visits", json={"person_id": 1, "visit_date": "2026-02-01", "visitor": "B", "visit_method": "电话"})
    r = client.get("/api/visits?person_id=1")
    assert r.json().get("code") == 0
    assert len(r.json()["data"]["items"]) >= 2


def test_update_visit(client):
    """修改走访"""
    r = client.post("/api/visits", json={"person_id": 1, "visit_date": "2026-01-15", "visitor": "原走访人", "visit_method": "上门"})
    vid = r.json()["data"]["id"]
    r = client.patch(f"/api/visits/{vid}", json={"visitor": "新走访人", "content": "已更新"})
    assert r.json().get("code") == 0
    assert r.json()["data"]["visitor"] == "新走访人"


def test_delete_visit(client):
    """删除走访"""
    r = client.post("/api/visits", json={"person_id": 1, "visit_date": "2026-01-15", "visitor": "删", "visit_method": "上门"})
    vid = r.json()["data"]["id"]
    r = client.delete(f"/api/visits/{vid}")
    assert r.json().get("code") == 0


def test_quarterly_stats(client):
    """季度走访统计"""
    from datetime import date
    today = date.today()
    client.post("/api/visits", json={"person_id": 1, "visit_date": str(today), "visitor": "Q", "visit_method": "上门"})
    r = client.get("/api/visits/stats-quarterly")
    d = r.json()["data"]
    assert "total" in d
    assert d["total"] >= 1


def test_create_visit_nonexistent_person(client):
    """不存在的人员"""
    r = client.post("/api/visits", json={"person_id": 9999, "visit_date": "2026-01-15", "visitor": "X", "visit_method": "上门"})
    assert r.json().get("code") != 0
