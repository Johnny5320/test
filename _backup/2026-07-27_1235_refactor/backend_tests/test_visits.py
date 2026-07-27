"""走访记录 API 测试"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.database import get_session
from app.models import User, Person
from app.core.security import hash_password


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="testadmin", hashed_password=hash_password("test123"), real_name="测试", role="director")
        session.add(user)
        person = Person(name="张三", id_card="320102199001011234", status="在帮")
        session.add(person)
        session.commit()

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as c:
        login = c.post("/api/auth/login", json={"username": "testadmin", "password": "test123"})
        c.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield c
    app.dependency_overrides.clear()


def test_create_visit(client):
    """新增走访记录"""
    resp = client.post("/api/visits", json={
        "person_id": 1,
        "visit_date": "2025-07-15",
        "visitor": "张科员",
        "visit_method": "上门",
        "content": "走访正常，生活稳定",
        "has_abnormal": False,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["quarter"] == "2025-Q3"
    assert data["visitor"] == "张科员"


def test_create_visit_abnormal(client):
    """新增异常走访记录"""
    resp = client.post("/api/visits", json={
        "person_id": 1,
        "visit_date": "2025-07-20",
        "visitor": "李科员",
        "visit_method": "电话",
        "content": "联系不上",
        "has_abnormal": True,
        "abnormal_detail": "电话无人接听，邻居说已搬走",
    })
    assert resp.status_code == 201
    assert resp.json()["has_abnormal"] is True


def test_list_visits_by_person(client):
    """按人员筛选走访记录"""
    client.post("/api/visits", json={"person_id": 1, "visit_date": "2025-07-15", "visitor": "A", "visit_method": "上门"})
    client.post("/api/visits", json={"person_id": 1, "visit_date": "2025-07-20", "visitor": "B", "visit_method": "电话"})

    resp = client.get("/api/visits?person_id=1")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_list_visits_by_quarter(client):
    """按季度筛选"""
    client.post("/api/visits", json={"person_id": 1, "visit_date": "2025-03-10", "visitor": "A", "visit_method": "上门"})
    client.post("/api/visits", json={"person_id": 1, "visit_date": "2025-07-15", "visitor": "B", "visit_method": "电话"})

    resp = client.get("/api/visits?quarter=2025-Q3")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_update_visit(client):
    """修改走访记录"""
    create = client.post("/api/visits", json={"person_id": 1, "visit_date": "2025-07-15", "visitor": "A", "visit_method": "上门"})
    visit_id = create.json()["id"]

    resp = client.put(f"/api/visits/{visit_id}", json={
        "person_id": 1, "visit_date": "2025-07-16", "visitor": "B", "visit_method": "电话",
        "content": "已更新",
    })
    assert resp.status_code == 200
    assert resp.json()["visitor"] == "B"


def test_delete_visit(client):
    """删除走访记录"""
    create = client.post("/api/visits", json={"person_id": 1, "visit_date": "2025-07-15", "visitor": "A", "visit_method": "上门"})
    visit_id = create.json()["id"]

    resp = client.delete(f"/api/visits/{visit_id}")
    assert resp.status_code == 200

    resp = client.get(f"/api/visits/{visit_id}")
    assert resp.status_code == 404


def test_quarterly_stats(client):
    """季度统计"""
    client.post("/api/visits", json={"person_id": 1, "visit_date": "2026-07-15", "visitor": "A", "visit_method": "上门"})
    client.post("/api/visits", json={"person_id": 1, "visit_date": "2026-07-20", "visitor": "B", "visit_method": "电话"})
    client.post("/api/visits", json={"person_id": 1, "visit_date": "2026-07-25", "visitor": "C", "visit_method": "上门", "has_abnormal": True})

    resp = client.get("/api/visits/stats/quarterly")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["上门"] == 2
    assert data["电话"] == 1
    assert data["有异常"] == 1


def test_create_visit_nonexistent_person(client):
    """走访不存在的人员"""
    resp = client.post("/api/visits", json={"person_id": 999, "visit_date": "2025-07-15", "visitor": "A", "visit_method": "上门"})
    assert resp.status_code == 404
