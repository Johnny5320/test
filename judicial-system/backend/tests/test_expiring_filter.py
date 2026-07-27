"""测试：到期天数筛选 + 预警列表"""
from datetime import date, timedelta


def _create_person(client, headers, name, id_card, status="在帮", risk_level="低", edu_end_date=None, **kwargs):
    """辅助：创建人员"""
    body = {"name": name, "id_card": id_card, "status": status, "risk_level": risk_level}
    if edu_end_date:
        body["edu_end_date"] = edu_end_date
    body.update(kwargs)
    r = client.post("/api/persons", json=body, headers=headers)
    assert r.status_code == 200, f"创建失败: {r.text}"
    return r.json()


class TestExpiringFilter:
    """Bug2: expiring_within_days 参数测试"""

    def test_filter_30d_includes_15d(self, client):
        """15天后到期 → 30天筛选应包含"""
        _create_person(client, client.headers, "15天到期", "320102199001011005",
                       edu_end_date=(date.today() + timedelta(days=15)).isoformat())
        r = client.get("/api/persons?expiring_within_days=30")
        assert r.status_code == 200
        names = [p["name"] for p in r.json()["data"]["items"]]
        assert "15天到期" in names

    def test_filter_7d_excludes_15d(self, client):
        """15天后到期 → 7天筛选不应包含"""
        _create_person(client, client.headers, "15天到期B", "320102199001011005",
                       edu_end_date=(date.today() + timedelta(days=15)).isoformat())
        r = client.get("/api/persons?expiring_within_days=7")
        assert r.status_code == 200
        names = [p["name"] for p in r.json()["data"]["items"]]
        assert "15天到期B" not in names

    def test_filter_only_active(self, client):
        """已解除人员即使近期到期也不应出现"""
        _create_person(client, client.headers, "已解除到期", "320102199001011005",
                       status="已解除", edu_end_date=(date.today() + timedelta(days=3)).isoformat())
        r = client.get("/api/persons?expiring_within_days=7")
        names = [p["name"] for p in r.json()["data"]["items"]]
        assert "已解除到期" not in names

    def test_filter_no_end_date_excluded(self, client):
        """无截止日期的人员不应出现"""
        _create_person(client, client.headers, "无截止日期", "320102199001011005")
        r = client.get("/api/persons?expiring_within_days=30")
        names = [p["name"] for p in r.json()["data"]["items"]]
        assert "无截止日期" not in names

    def test_combined_with_is_minor(self, client):
        """到期筛选 + 未成年筛选叠加"""
        _create_person(client, client.headers, "未成年到期", "320102199001011005",
                       edu_end_date=(date.today() + timedelta(days=10)).isoformat(), is_minor=True)
        _create_person(client, client.headers, "成年到期", "320102199001011005",
                       edu_end_date=(date.today() + timedelta(days=10)).isoformat(), is_minor=False)

        r = client.get("/api/persons?expiring_within_days=30&is_minor=true")
        names = [p["name"] for p in r.json()["data"]["items"]]
        assert "未成年到期" in names
        assert "成年到期" not in names

    def test_combined_with_is_mental(self, client):
        """到期筛选 + 精神疾病筛选叠加"""
        _create_person(client, client.headers, "精神到期", "320102199001011005",
                       edu_end_date=(date.today() + timedelta(days=10)).isoformat(), is_mental=True)
        _create_person(client, client.headers, "正常到期", "320102199001011005",
                       edu_end_date=(date.today() + timedelta(days=10)).isoformat(), is_mental=False)

        r = client.get("/api/persons?expiring_within_days=30&is_mental=true")
        names = [p["name"] for p in r.json()["data"]["items"]]
        assert "精神到期" in names
        assert "正常到期" not in names


class TestRemindersList:
    """Bug1: 预警列表数据测试"""

    def test_reminders_has_expiring_list(self, client):
        """提醒接口应返回 expiring_list"""
        _create_person(client, client.headers, "提醒测试A", "320102199001011013",
                       edu_end_date=(date.today() + timedelta(days=10)).isoformat())
        r = client.get("/api/reminders")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "expiring_list" in data
        assert isinstance(data["expiring_list"], list)
        names = [p["name"] for p in data["expiring_list"]]
        assert "提醒测试A" in names

    def test_reminders_has_visit_overdue_list(self, client):
        """提醒接口应返回 visit_overdue_list"""
        r = client.get("/api/reminders")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "visit_overdue_list" in data
        assert isinstance(data["visit_overdue_list"], list)

    def test_expiring_list_has_required_fields(self, client):
        """expiring_list 每项应包含 name/risk_level/edu_end_date/days_remaining/level"""
        _create_person(client, client.headers, "字段测试", "320102199001011013",
                       edu_end_date=(date.today() + timedelta(days=5)).isoformat())
        r = client.get("/api/reminders")
        data = r.json()["data"]
        item = next((p for p in data["expiring_list"] if p["name"] == "字段测试"), None)
        assert item is not None
        for key in ["name", "risk_level", "edu_end_date", "days_remaining", "level"]:
            assert key in item, f"缺少字段: {key}"

    def test_visit_overdue_list_has_required_fields(self, client):
        """visit_overdue_list 每项应包含必要字段"""
        _create_person(client, client.headers, "走访字段测试", "320102199001011013")
        r = client.get("/api/reminders")
        data = r.json()["data"]
        # 如果有超期未走访的人员
        if data["visit_overdue_list"]:
            item = data["visit_overdue_list"][0]
            for key in ["name", "risk_level", "days_since_visit", "visit_interval_days", "overdue_days"]:
                assert key in item, f"缺少字段: {key}"
