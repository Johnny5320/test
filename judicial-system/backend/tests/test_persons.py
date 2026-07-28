"""人员 CRUD 测试 — v3.2 信封格式"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from app.main import app
from app.core.database import get_session
from app.models import User
from app.core.security import hash_password


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(User(username="admin", hashed_password=hash_password("admin123"), real_name="管理员", role="director"))
        s.commit()
    app.dependency_overrides[get_session] = lambda: Session(engine)
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        c.headers["Authorization"] = f"Bearer {r.json()['data']['access_token']}"
        yield c
    app.dependency_overrides.clear()


# 有效身份证号生成
def _id(seq):
    w = [7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2]
    d17 = f"32010219900101{seq:03d}"[:17]
    check = "10X98765432"[sum(int(d17[i])*w[i] for i in range(17)) % 11]
    return d17 + check


def test_create_person(client):
    """新增人员"""
    r = client.post("/api/persons", json={"name": "张三", "id_card": _id(1)})
    assert r.json().get("code") == 0
    d = r.json()["data"]
    assert d["name"] == "张三"
    assert d["id_card"] == _id(1)
    assert d["gender"] in ("男", "女")


def test_create_duplicate(client):
    """身份证重复"""
    client.post("/api/persons", json={"name": "张三", "id_card": _id(2)})
    r = client.post("/api/persons", json={"name": "李四", "id_card": _id(2)})
    assert r.json().get("code") != 0


def test_list_persons(client):
    """列表查询"""
    client.post("/api/persons", json={"name": "A", "id_card": _id(3)})
    client.post("/api/persons", json={"name": "B", "id_card": _id(4)})
    r = client.get("/api/persons")
    assert r.json()["data"]["total"] >= 2


def test_search(client):
    """搜索"""
    client.post("/api/persons", json={"name": "搜索测试", "id_card": _id(5)})
    r = client.get("/api/persons?search=搜索")
    assert any("搜索" in p["name"] for p in r.json()["data"]["items"])


def test_filter_status(client):
    """状态筛选"""
    client.post("/api/persons", json={"name": "在帮人", "id_card": _id(6), "status": "在帮"})
    client.post("/api/persons", json={"name": "解除人", "id_card": _id(7), "status": "已解除"})
    r = client.get("/api/persons?status=在帮")
    for p in r.json()["data"]["items"]:
        assert p["status"] == "在帮"


def test_filter_minor(client):
    """未成年筛选"""
    client.post("/api/persons", json={"name": "未成年", "id_card": _id(8), "is_minor": True})
    r = client.get("/api/persons?is_minor=true")
    assert any(p["is_minor"] for p in r.json()["data"]["items"])


def test_filter_mental(client):
    """精神疾病筛选"""
    client.post("/api/persons", json={"name": "精神", "id_card": _id(9), "is_mental": True})
    r = client.get("/api/persons?is_mental=true")
    assert any(p["is_mental"] for p in r.json()["data"]["items"])


def test_filter_combined(client):
    """组合筛选"""
    client.post("/api/persons", json={"name": "组合", "id_card": _id(10), "is_minor": True, "is_mental": True})
    r = client.get("/api/persons?is_minor=true&is_mental=true")
    for p in r.json()["data"]["items"]:
        assert p["is_minor"] and p["is_mental"]


def test_person_detail(client):
    """人员详情"""
    client.post("/api/persons", json={"name": "详情", "id_card": _id(11)})
    r = client.get("/api/persons")
    pid = r.json()["data"]["items"][0]["id"]
    r = client.get(f"/api/persons/{pid}")
    assert r.json()["data"]["id"] == pid


def test_update_person(client):
    """修改人员"""
    client.post("/api/persons", json={"name": "待改", "id_card": _id(12)})
    r = client.get("/api/persons")
    pid = r.json()["data"]["items"][0]["id"]
    r = client.patch(f"/api/persons/{pid}", json={"phone": "13900139000", "status": "已解除"})
    assert r.json().get("code") == 0


def test_delete_person(client):
    """软删除"""
    client.post("/api/persons", json={"name": "待删", "id_card": _id(13)})
    r = client.get("/api/persons")
    pid = r.json()["data"]["items"][0]["id"]
    r = client.delete(f"/api/persons/{pid}")
    assert r.json().get("code") == 0
    r = client.get(f"/api/persons/{pid}")
    assert r.json().get("code") != 0


def test_edit_logs(client):
    """修改历史"""
    client.post("/api/persons", json={"name": "留痕", "id_card": _id(14)})
    r = client.get("/api/persons")
    pid = r.json()["data"]["items"][0]["id"]
    client.patch(f"/api/persons/{pid}", json={"phone": "111"})
    client.patch(f"/api/persons/{pid}", json={"phone": "222"})
    r = client.get(f"/api/persons/{pid}/edit-logs")
    assert r.json().get("code") == 0
    assert len(r.json()["data"]) >= 1


def test_stats_summary(client):
    """统计汇总"""
    client.post("/api/persons", json={"name": "统计", "id_card": _id(15)})
    r = client.get("/api/persons/stats-summary")
    d = r.json()["data"]
    assert "total" in d
    assert d["total"] >= 1


def test_export_excel(client):
    """导出Excel"""
    client.post("/api/persons", json={"name": "导出", "id_card": _id(16)})
    r = client.get("/api/persons/export")
    assert r.status_code == 200
    assert len(r.content) > 100


def test_stats_trend(client):
    """月度趋势"""
    r = client.get("/api/persons/stats-trend?months=3")
    assert r.json().get("code") == 0
    assert isinstance(r.json()["data"], list)


def test_risk_score(client):
    """风险评分"""
    client.post("/api/persons", json={"name": "评分", "id_card": _id(17), "risk_level": "高"})
    r = client.get("/api/persons")
    pid = r.json()["data"]["items"][0]["id"]
    r = client.get(f"/api/persons/{pid}/risk-score")
    d = r.json()["data"]
    assert "score" in d
    assert "level" in d
    assert "factors" in d


def test_batch_delete(client):
    """批量删除"""
    client.post("/api/persons", json={"name": "批量A", "id_card": _id(18)})
    client.post("/api/persons", json={"name": "批量B", "id_card": _id(19)})
    r = client.get("/api/persons?search=批量")
    ids = [p["id"] for p in r.json()["data"]["items"]]
    r = client.post("/api/persons/batch-delete", json={"ids": ids})
    assert r.json().get("code") == 0


def test_batch_status(client):
    """批量改状态"""
    client.post("/api/persons", json={"name": "改状态", "id_card": _id(20)})
    r = client.get("/api/persons")
    pid = r.json()["data"]["items"][0]["id"]
    r = client.post("/api/persons/batch-update-status", json={"ids": [pid], "status": "脱管"})
    assert r.json().get("code") == 0


def test_batch_risk(client):
    """批量改风险"""
    client.post("/api/persons", json={"name": "改风险", "id_card": _id(21)})
    r = client.get("/api/persons")
    pid = r.json()["data"]["items"][0]["id"]
    r = client.post("/api/persons/batch-update-risk", json={"ids": [pid], "risk_level": "高"})
    assert r.json().get("code") == 0


def test_id_card_auto_infer(client):
    """身份证自动推算性别和出生日期"""
    r = client.post("/api/persons", json={"name": "推算", "id_card": _id(22)})
    d = r.json()["data"]
    assert d["gender"] in ("男", "女")
    assert d["birth_date"]
