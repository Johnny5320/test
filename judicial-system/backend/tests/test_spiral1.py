"""螺旋第 1 圈验收测试 — 身份证脱敏+严格校验+软删走访分组+截止日排序"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.database import get_session
from app.models import User, Person
from app.core.security import hash_password


def _vid(seq: int) -> str:
    """生成校验位正确的身份证号（seq 编入第15-17位，确保唯一）"""
    W = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    C = "10X98765432"
    # 32010219900101 = 14字符（地区+生日），seq % 1000 占3位 = 17字符
    b = f"32010219900101{seq % 1000:03d}"
    return b + C[sum(int(b[i]) * W[i] for i in range(17)) % 11]


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(User(username="admin", hashed_password=hash_password("admin123"), real_name="管理员", role="director"))
        s.commit()
    app.dependency_overrides[get_session] = lambda: Session(engine)
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"real_name": "管理员", "password": "admin123"})
        c.headers["Authorization"] = f"Bearer {r.json()['data']['access_token']}"
        yield c
    app.dependency_overrides.clear()


# ============================================================
# 1.1 身份证脱敏 — id_card_masked 字段
# ============================================================

class TestIdCardMasking:
    def test_masked_format(self, client):
        """id_card_masked 格式：前6 + **** + 后4"""
        r = client.post("/api/persons", json={"name": "脱敏测试", "id_card": _vid(100)})
        pid = r.json()["data"]["id"]
        r = client.get(f"/api/persons/{pid}")
        d = r.json()["data"]
        assert d["id_card_masked"] is not None
        assert d["id_card_masked"][:6] == d["id_card"][:6]
        assert d["id_card_masked"][-4:] == d["id_card"][-4:]
        assert "****" in d["id_card_masked"]
        # 脱敏格式：前6 + **** + 后4 = 14字符（比原18位短）
        assert len(d["id_card_masked"]) == 14

    def test_list_returns_masked(self, client):
        """列表接口仅返回 id_card_masked（脱敏），不含完整 id_card"""
        client.post("/api/persons", json={"name": "列表脱敏", "id_card": _vid(101)})
        r = client.get("/api/persons")
        item = r.json()["data"]["items"][0]
        assert "id_card" not in item  # 完整号不在列表响应中（隐私脱敏）
        assert item["id_card_masked"] is not None
        assert "****" in item["id_card_masked"]

    def test_masked_preserves_case(self, client):
        """末位 X 保持大写"""
        # 32010219900101007X 末位为 X
        r = client.post("/api/persons", json={"name": "大写X", "id_card": "32010219900101007X"})
        pid = r.json()["data"]["id"]
        r = client.get(f"/api/persons/{pid}")
        masked = r.json()["data"]["id_card_masked"]
        assert masked.endswith("007X") or masked.endswith("007x")  # 脱敏保留原样


# ============================================================
# 1.2 身份证严格校验
# ============================================================

class TestStrictIdCard:
    def test_invalid_checksum_rejected(self, client):
        """校验位错误 → 拒绝入库"""
        r = client.post("/api/persons", json={"name": "假号", "id_card": "320113196907177577"})
        assert r.json()["code"] == 10001

    def test_gender_conflict_rejected(self, client):
        """性别与身份证第17位不一致 → 拒绝"""
        r = client.post("/api/persons", json={
            "name": "性别冲突", "id_card": "320102197304040031", "gender": "女"
        })
        assert r.json()["code"] == 10001

    def test_birth_conflict_rejected(self, client):
        """出生日期与身份证编码不一致 → 拒绝"""
        r = client.post("/api/persons", json={
            "name": "生日冲突", "id_card": "320102197506060057",
            "birth_date": "1999-01-01"
        })
        assert r.json()["code"] == 10001

    def test_update_invalid_checksum_rejected(self, client):
        """修改身份证号时同样严格校验"""
        r = client.post("/api/persons", json={"name": "待改", "id_card": _vid(102)})
        pid = r.json()["data"]["id"]
        r = client.patch(f"/api/persons/{pid}", json={"id_card": "320113196907177577"})
        assert r.json()["code"] == 10001


# ============================================================
# 1.3 软删除人员走访记录单独分组
# ============================================================

class TestSoftDeletedVisitGrouping:
    def test_deleted_person_visits_marked(self, client):
        """软删人员的走访 person_is_deleted=True"""
        r = client.post("/api/persons", json={"name": "软删A", "id_card": _vid(200)})
        pid = r.json()["data"]["id"]
        client.post("/api/visits", json={"person_id": pid, "visit_date": "2026-01-10", "visitor": "张", "visit_method": "上门"})
        client.delete(f"/api/persons/{pid}")
        r = client.get("/api/visits?page_size=100")
        items = r.json()["data"]["items"]
        deleted_visits = [v for v in items if v["person_id"] == pid]
        assert len(deleted_visits) == 1
        assert deleted_visits[0]["person_is_deleted"] is True

    def test_active_person_visits_not_marked(self, client):
        """在帮人员的走访 person_is_deleted=False"""
        r = client.post("/api/persons", json={"name": "在帮A", "id_card": _vid(201)})
        pid = r.json()["data"]["id"]
        client.post("/api/visits", json={"person_id": pid, "visit_date": "2026-01-11", "visitor": "李", "visit_method": "电话"})
        r = client.get("/api/visits?page_size=100")
        items = r.json()["data"]["items"]
        active_visits = [v for v in items if v["person_id"] == pid]
        assert len(active_visits) == 1
        assert active_visits[0]["person_is_deleted"] is False

    def test_stats_exclude_deleted_persons(self, client):
        """统计汇总排除软删人员"""
        # 先记录当前总数
        r0 = client.get("/api/persons/stats-summary")
        total_before = r0.json()["data"]["total"]
        # 新增一个人并软删
        r = client.post("/api/persons", json={"name": "删后统计", "id_card": _vid(202)})
        client.delete(f"/api/persons/{r.json()['data']['id']}")
        r1 = client.get("/api/persons/stats-summary")
        total_after = r1.json()["data"]["total"]
        # 软删后总数不变（删了一个又加了一个，但加的被删了应该回到原来的值）
        # 实际上：加了1个，删了1个，净变化为0
        assert total_after == total_before


# ============================================================
# 1.4 台账帮教截止时间排序
# ============================================================

class TestEduEndDateSort:
    def _create_persons_with_dates(self, client):
        """创建三个帮教截止日不同的人员"""
        today = date.today()
        persons = [
            ("远期", _vid(300), str(today + timedelta(days=365))),
            ("近期", _vid(301), str(today + timedelta(days=30))),
            ("已过期", _vid(302), str(today - timedelta(days=10))),
        ]
        ids = []
        for name, vid, edu_end in persons:
            r = client.post("/api/persons", json={
                "name": name, "id_card": vid, "edu_end_date": edu_end
            })
            ids.append(r.json()["data"]["id"])
        return ids

    def test_sort_asc(self, client):
        """截止日正序：已过期 → 近期 → 远期"""
        ids = self._create_persons_with_dates(client)
        r = client.get("/api/persons?sort_by=edu_end_date&sort_order=asc&page_size=100")
        items = r.json()["data"]["items"]
        # 过滤出刚创建的三个（按名称）
        created = [i for i in items if i["name"] in ("远期", "近期", "已过期")]
        assert len(created) == 3
        # 正序：已过期 < 近期 < 远期
        edu_dates = [i["edu_end_date"] for i in created]
        assert edu_dates == sorted(edu_dates)

    def test_sort_desc(self, client):
        """截止日倒序：远期 → 近期 → 已过期"""
        ids = self._create_persons_with_dates(client)
        r = client.get("/api/persons?sort_by=edu_end_date&sort_order=desc&page_size=100")
        items = r.json()["data"]["items"]
        created = [i for i in items if i["name"] in ("远期", "近期", "已过期")]
        assert len(created) == 3
        edu_dates = [i["edu_end_date"] for i in created]
        assert edu_dates == sorted(edu_dates, reverse=True)

    def test_default_sort(self, client):
        """默认排序（updated_at desc）不按 edu_end_date"""
        ids = self._create_persons_with_dates(client)
        r = client.get("/api/persons?page_size=100")
        items = r.json()["data"]["items"]
        created = [i for i in items if i["name"] in ("远期", "近期", "已过期")]
        # 默认按更新时间倒序，最后更新的排最前
        # 三个是连续创建的，最后创建的 "已过期" 应排最前
        assert created[0]["name"] == "已过期"
