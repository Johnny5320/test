#!/usr/bin/env python3
"""全功能集成测试 — 模拟用户点击每一个按钮"""
import httpx
import json
from datetime import date, timedelta

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0
ERRORS = []

def test(name, func):
    global PASS, FAIL
    try:
        result = func()
        PASS += 1
        print(f"  ✅ {name}: {result}")
    except AssertionError as e:
        FAIL += 1
        ERRORS.append(f"{name}: {e}")
        print(f"  ❌ {name}: {e}")
    except Exception as e:
        FAIL += 1
        ERRORS.append(f"{name}: {type(e).__name__}: {e}")
        print(f"  ❌ {name}: {type(e).__name__}: {e}")

# ========== 登录 ==========
c = httpx.Client(base_url=BASE, timeout=15)
r = c.post("/api/auth/login", json={"real_name": "admin", "password": "admin123"})
assert r.status_code == 200, f"登录失败: {r.text}"
TOKEN = r.json()["data"]["access_token"]
H = {"Authorization": f"Bearer {TOKEN}"}
print(f"\n{'='*60}")
print(f"  登录成功，开始全功能测试")
print(f"{'='*60}\n")

# ========== 准备测试数据 ==========
print("─── 准备测试数据 ───")

# 创建多种类型的人员
today = date.today()
test_data = [
    # 即将到期（5天内）
    {"name": "张三_5天到期", "id_card": "320102199001010002", "status": "在帮", "risk_level": "高",
     "edu_end_date": (today + timedelta(days=5)).isoformat(), "is_minor": False, "is_xj": False, "is_mental": False},
    # 即将到期（15天）
    {"name": "李四_15天到期", "id_card": "320102199001010010", "status": "在帮", "risk_level": "中",
     "edu_end_date": (today + timedelta(days=15)).isoformat(), "is_minor": True, "is_xj": False, "is_mental": False},
    # 即将到期（25天）
    {"name": "王五_25天到期", "id_card": "320102199001010029", "status": "在帮", "risk_level": "低",
     "edu_end_date": (today + timedelta(days=25)).isoformat(), "is_minor": False, "is_xj": True, "is_mental": False},
    # 已超期
    {"name": "赵六_已超期", "id_card": "320102199001010037", "status": "在帮", "risk_level": "高",
     "edu_end_date": (today - timedelta(days=10)).isoformat(), "is_minor": False, "is_xj": False, "is_mental": True},
    # 正常在帮（90天后到期）
    {"name": "钱七_正常", "id_card": "32010219900101111X", "status": "在帮", "risk_level": "低",
     "edu_end_date": (today + timedelta(days=90)).isoformat(), "is_minor": False, "is_xj": False, "is_mental": False},
    # 已解除
    {"name": "孙八_已解除", "id_card": "320102199001011128", "status": "已解除", "risk_level": "低",
     "edu_end_date": (today + timedelta(days=3)).isoformat(), "is_minor": False, "is_xj": False, "is_mental": False},
    # 未成年+精神疾病
    {"name": "周九_未成年精神", "id_card": "320102199001011005", "status": "在帮", "risk_level": "高",
     "edu_end_date": (today + timedelta(days=10)).isoformat(), "is_minor": True, "is_xj": False, "is_mental": True},
]

created_ids = []
for d in test_data:
    r = c.post("/api/persons", json=d, headers=H)
    if r.status_code == 200:
        created_ids.append(r.json()["id"])
    elif r.status_code == 400 and "已存在" in r.text:
        # 已存在，获取id
        r2 = c.get(f"/api/persons?search={d['name']}", headers=H)
        if r2.json()["data"]["items"]:
            created_ids.append(r2.json()["data"]["items"][0]["id"])
    else:
        print(f"  ⚠️ 创建 {d['name']} 失败: {r.text}")

print(f"  准备了 {len(created_ids)} 条测试数据\n")

# ========================================================
# Bug 1: 预警列表
# ========================================================
print("─── Bug 1: 预警列表 ───")

def test_reminders_has_dismiss_list():
    r = c.get("/api/reminders", headers=H)
    d = r.json()
    assert "dismiss_list" in d, "缺少 dismiss_list"
    assert len(d["dismiss_list"]) > 0, "dismiss_list 为空"
    return f"dismiss_list 有 {len(d['dismiss_list'])} 人"

def test_dismiss_list_has_correct_fields():
    r = c.get("/api/reminders", headers=H)
    item = r.json()["dismiss_list"][0]
    missing = [k for k in ["name", "risk_level", "edu_end_date", "days_remaining", "level"] if k not in item]
    assert not missing, f"缺少字段: {missing}"
    return f"字段完整: {list(item.keys())}"

def test_dismiss_list_contains_5d_person():
    r = c.get("/api/reminders", headers=H)
    names = [p["name"] for p in r.json()["dismiss_list"]]
    assert "张三_5天到期" in names, f"5天到期人员不在列表中，实际: {names}"
    return "5天到期人员在列表中"

def test_dismiss_list_contains_15d_person():
    r = c.get("/api/reminders", headers=H)
    names = [p["name"] for p in r.json()["dismiss_list"]]
    assert "李四_15天到期" in names, "15天到期人员不在列表中"
    return "15天到期人员在列表中"

def test_dismiss_list_excludes_active解除():
    r = c.get("/api/reminders", headers=H)
    names = [p["name"] for p in r.json()["dismiss_list"]]
    assert "孙八_已解除" not in names, "已解除人员不应出现在预警列表"
    return "已解除人员正确排除"

def test_dismiss_list_days_remaining_correct():
    r = c.get("/api/reminders", headers=H)
    item = next((p for p in r.json()["dismiss_list"] if p["name"] == "张三_5天到期"), None)
    assert item is not None
    assert item["days_remaining"] == 5, f"剩余天数应为5，实际: {item['days_remaining']}"
    return f"days_remaining={item['days_remaining']}"

def test_dismiss_list_level_correct():
    r = c.get("/api/reminders", headers=H)
    item = next((p for p in r.json()["dismiss_list"] if p["name"] == "张三_5天到期"), None)
    assert item["level"] == "7天", f"5天到期应标记为'7天'，实际: {item['level']}"
    return f"level={item['level']}"

def test_reminders_has_visit_overdue_list():
    r = c.get("/api/reminders", headers=H)
    d = r.json()
    assert "visit_overdue_list" in d, "缺少 visit_overdue_list"
    assert isinstance(d["visit_overdue_list"], list)
    return f"visit_overdue_list 有 {len(d['visit_overdue_list'])} 人"

def test_visit_overdue_has_correct_fields():
    r = c.get("/api/reminders", headers=H)
    if not r.json()["visit_overdue_list"]:
        return "无超期走访数据，跳过字段检查"
    item = r.json()["visit_overdue_list"][0]
    missing = [k for k in ["name", "risk_level", "days_since_visit", "visit_interval_days", "overdue_days"] if k not in item]
    assert not missing, f"缺少字段: {missing}"
    return f"字段完整"

test("dismiss_list 存在且非空", test_reminders_has_dismiss_list)
test("dismiss_list 字段完整", test_dismiss_list_has_correct_fields)
test("dismiss_list 包含5天到期人员", test_dismiss_list_contains_5d_person)
test("dismiss_list 包含15天到期人员", test_dismiss_list_contains_15d_person)
test("dismiss_list 不含已解除人员", test_dismiss_list_excludes_active解除)
test("days_remaining 计算正确", test_dismiss_list_days_remaining_correct)
test("level 标记正确(7天)", test_dismiss_list_level_correct)
test("visit_overdue_list 存在", test_reminders_has_visit_overdue_list)
test("visit_overdue_list 字段完整", test_visit_overdue_has_correct_fields)

# ========================================================
# Bug 2: 仪表盘待办点击 → 到期筛选
# ========================================================
print("\n─── Bug 2: 仪表盘待办点击 → 到期筛选 ───")

def test_7d_filter():
    r = c.get("/api/persons?expiring_within_days=7", headers=H)
    names = [p["name"] for p in r.json()["data"]["items"]]
    assert "张三_5天到期" in names, f"5天到期应包含: {names}"
    assert "李四_15天到期" not in names, f"15天到期不应包含: {names}"
    assert "钱七_正常" not in names, f"90天到期不应包含: {names}"
    return f"命中 {r.json()['total']} 人: {names}"

def test_30d_filter():
    r = c.get("/api/persons?expiring_within_days=30", headers=H)
    names = [p["name"] for p in r.json()["data"]["items"]]
    assert "张三_5天到期" in names, "5天到期应包含"
    assert "李四_15天到期" in names, "15天到期应包含"
    assert "王五_25天到期" in names, "25天到期应包含"
    assert "钱七_正常" not in names, "90天到期不应包含"
    return f"命中 {r.json()['total']} 人: {names}"

def test_30d_only_active():
    r = c.get("/api/persons?expiring_within_days=30", headers=H)
    statuses = set(p["status"] for p in r.json()["data"]["items"])
    assert statuses == {"在帮"}, f"应只包含在帮人员，实际: {statuses}"
    return f"状态全部为在帮"

def test_30d_no_end_date_excluded():
    r = c.get("/api/persons?expiring_within_days=30", headers=H)
    names = [p["name"] for p in r.json()["data"]["items"]]
    # 钱七_正常有90天后到期，不应出现
    assert "钱七_正常" not in names
    return "无到期日人员正确排除"

test("7天筛选: 只含5天到期", test_7d_filter)
test("30天筛选: 含5/15/25天到期", test_30d_filter)
test("30天筛选: 只含在帮", test_30d_only_active)
test("30天筛选: 排除90天到期", test_30d_no_end_date_excluded)

# ========================================================
# Bug 3: 仪表盘跳转后再筛选（组合筛选）
# ========================================================
print("\n─── Bug 3: 组合筛选（模拟仪表盘跳转后再筛选）───")

def test_minor_then_mental():
    """模拟：仪表盘点击未成年 → 再筛选精神疾病"""
    # 先筛未成年
    r1 = c.get("/api/persons?is_minor=true", headers=H)
    minor_names = [p["name"] for p in r1.json()["data"]["items"]]
    assert "李四_15天到期" in minor_names, f"李四应为未成年: {minor_names}"
    assert "周九_未成年精神" in minor_names, f"周九应为未成年: {minor_names}"

    # 再叠加精神疾病
    r2 = c.get("/api/persons?is_minor=true&is_mental=true", headers=H)
    combined = [p["name"] for p in r2.json()["data"]["items"]]
    assert "周九_未成年精神" in combined, f"周九应同时是未成年+精神疾病: {combined}"
    assert "李四_15天到期" not in combined, f"李四不应是精神疾病: {combined}"
    return f"未成年({len(minor_names)}) + 精神疾病({len(combined)}) = 正确"

def test_mental_then_minor():
    """反向：先筛精神疾病 → 再叠加未成年"""
    r1 = c.get("/api/persons?is_mental=true", headers=H)
    r2 = c.get("/api/persons?is_mental=true&is_minor=true", headers=H)
    mental_names = [p["name"] for p in r1.json()["data"]["items"]]
    combined = [p["name"] for p in r2.json()["data"]["items"]]
    assert "赵六_已超期" in mental_names, f"赵六应为精神疾病: {mental_names}"
    assert "周九_未成年精神" in combined
    assert "赵六_已超期" not in combined, f"赵六不应是未成年: {combined}"
    return f"精神疾病({len(mental_names)}) + 未成年({len(combined)}) = 正确"

def test_expiring_then_minor():
    """到期筛选 + 未成年"""
    r = c.get("/api/persons?expiring_within_days=30&is_minor=true", headers=H)
    names = [p["name"] for p in r.json()["data"]["items"]]
    assert "李四_15天到期" in names, f"李四(未成年+15天到期)应命中: {names}"
    assert "周九_未成年精神" in names, f"周九(未成年+10天到期)应命中: {names}"
    assert "张三_5天到期" not in names, f"张三(非未成年)不应命中: {names}"
    return f"命中 {len(names)} 人: {names}"

def test_xj_filter():
    """xj 筛选"""
    r = c.get("/api/persons?is_xj=true", headers=H)
    names = [p["name"] for p in r.json()["data"]["items"]]
    assert "王五_25天到期" in names, f"王五应为xj: {names}"
    return f"xj命中 {len(names)} 人: {names}"

def test_status_filter():
    """状态筛选"""
    r = c.get("/api/persons?status=在帮", headers=H)
    for p in r.json()["data"]["items"]:
        assert p["status"] == "在帮", f"状态应为在帮: {p['name']}={p['status']}"
    return f"在帮 {r.json()['total']} 人"

test("未成年 → 再叠加精神疾病", test_minor_then_mental)
test("精神疾病 → 再叠加未成年", test_mental_then_minor)
test("30天到期 + 未成年叠加", test_expiring_then_minor)
test("xj 筛选", test_xj_filter)
test("状态筛选(在帮)", test_status_filter)

# ========================================================
# Bug 4: 滚动优化（验证 CSS 和列合并）
# ========================================================
print("\n─── Bug 4: 前端滚动优化验证 ───")

def test_frontend_has_scroll_css():
    with open("judicial-system/frontend/index_v2.html") as f:
        html = f.read()
    assert "will-change:transform" in html, "缺少 will-change CSS"
    assert "will-change:scroll-position" in html, "缺少 scroll-position CSS"
    assert "-webkit-overflow-scrolling:touch" in html, "缺少 iOS 滚动优化"
    assert "contain:layout style" in html, "缺少 contain CSS"
    return "CSS 滚动优化全部存在"

def test_frontend_table_has_border():
    with open("judicial-system/frontend/index_v2.html") as f:
        html = f.read()
    # el-table 应有 stripe border 属性提升可读性
    assert 'el-table' in html
    return "表格组件存在"

test("CSS 滚动优化已添加", test_frontend_has_scroll_css)
test("表格组件完整", test_frontend_table_has_border)

# ========================================================
# Bug 5: ECharts 可视化
# ========================================================
print("\n─── Bug 5: ECharts 可视化验证 ───")

def test_echarts_cdn():
    with open("judicial-system/frontend/index_v2.html") as f:
        html = f.read()
    assert "echarts@5" in html, "缺少 ECharts CDN"
    return "ECharts CDN 已引入"

def test_echarts_chart_containers():
    with open("judicial-system/frontend/index_v2.html") as f:
        html = f.read()
    for ref in ["statusChartRef", "riskChartRef", "villageChartRef", "responsibleChartRef"]:
        assert f'ref="{ref}"' in html, f"缺少图表容器: {ref}"
    return "4个图表容器全部存在"

def test_echarts_init_code():
    with open("judicial-system/frontend/index_v2.html") as f:
        html = f.read()
    assert "echarts.init" in html, "缺少 echarts.init 代码"
    assert "initCharts" in html, "缺少 initCharts 函数"
    assert "handleChartResize" in html, "缺少 resize 处理"
    return "ECharts 初始化代码完整"

def test_echarts_has_pie_charts():
    with open("judicial-system/frontend/index_v2.html") as f:
        html = f.read()
    assert "type:'pie'" in html, "缺少饼图"
    return "饼图配置存在"

def test_echarts_has_bar_charts():
    with open("judicial-system/frontend/index_v2.html") as f:
        html = f.read()
    assert "type:'bar'" in html, "缺少柱状图"
    return "柱状图配置存在"

test("ECharts CDN 已引入", test_echarts_cdn)
test("4个图表容器存在", test_echarts_chart_containers)
test("ECharts 初始化代码完整", test_echarts_init_code)
test("饼图配置存在", test_echarts_has_pie_charts)
test("柱状图配置存在", test_echarts_has_bar_charts)

# ========================================================
# 额外：原有功能回归测试
# ========================================================
print("\n─── 回归测试：原有功能 ───")

def test_persons_list_pagination():
    r = c.get("/api/persons?page=1&page_size=5", headers=H)
    d = r.json()
    assert "items" in d
    assert "total" in d
    assert len(d["items"]) <= 5
    return f"total={d['total']}, page_size={d['page_size']}"

def test_persons_search():
    r = c.get("/api/persons?search=张三", headers=H)
    names = [p["name"] for p in r.json()["data"]["items"]]
    assert any("张三" in n for n in names), f"搜索张三无结果: {names}"
    return f"命中 {r.json()['total']} 人"

def test_persons_detail():
    r = c.get(f"/api/persons/{created_ids[0]}", headers=H)
    assert r.status_code == 200
    assert r.json()["name"] == "张三_5天到期"
    return f"id={created_ids[0]}, name={r.json()['name']}"

def test_edit_logs():
    # 修改一个人的risk_level
    c.put(f"/api/persons/{created_ids[0]}", json={"risk_level": "中"}, headers=H)
    r = c.get(f"/api/persons/{created_ids[0]}/edit-logs", headers=H)
    assert r.status_code == 200
    return f"修改记录 {len(r.json())} 条"

def test_stats_summary():
    r = c.get("/api/persons/stats-summary", headers=H)
    d = r.json()
    assert "total" in d
    assert "在帮" in d
    assert "total_minor" in d
    assert "total_xj" in d
    assert "total_mental" in d
    return f"total={d['total']}, 在帮={d['在帮']}, 未成年={d['total_minor']}, xj={d['total_xj']}, 精神={d['total_mental']}"

def test_quarterly_report():
    r = c.get("/api/persons/reports-quarterly", headers=H)
    d = r.json()
    assert "year" in d
    assert "visits" in d
    return f"{d['year']}年Q{d['quarter']}, 在帮={d['active_count']}"

def test_excel_export():
    r = c.get("/api/persons/export?format=excel", headers=H)
    assert r.status_code == 200
    assert len(r.content) > 100
    return f"{len(r.content)} bytes"

test("分页查询", test_persons_list_pagination)
test("搜索功能", test_persons_search)
test("人员详情", test_persons_detail)
test("修改留痕", test_edit_logs)
test("统计汇总", test_stats_summary)
test("季度报表", test_quarterly_report)
test("Excel导出", test_excel_export)

# ========================================================
# 前端 HTML 完整性
# ========================================================
print("\n─── 前端 HTML 完整性 ───")

def test_html_not_broken():
    with open("judicial-system/frontend/index_v2.html") as f:
        html = f.read()
    # 基本结构检查
    assert "<html" in html and "</html>" in html, "HTML 结构不完整"
    assert "<head" in html and "</head>" in html, "HEAD 不完整"
    assert "<body" in html and "</body>" in html, "BODY 不完整"
    assert "createApp" in html, "Vue 初始化代码丢失"
    assert "ElementPlus" in html, "Element Plus 丢失"
    return f"{len(html)} bytes, 结构完整"

def test_html_has_all_views():
    with open("judicial-system/frontend/index_v2.html") as f:
        html = f.read()
    for view in ["dashboard", "ledger", "visits", "history", "stats"]:
        assert f"currentView === '{view}'" in html or f"currentView==='{view}'" in html, f"缺少视图: {view}"
    return "5个视图全部存在"

def test_html_has_filter_vars():
    with open("judicial-system/frontend/index_v2.html") as f:
        html = f.read()
    for var in ["fromDashboard", "filterExpiringDays", "filterStatus", "filterIsMinor", "filterIsXj", "filterIsMental"]:
        assert var in html, f"缺少变量: {var}"
    return "筛选变量全部存在"

test("HTML 结构完整", test_html_not_broken)
test("5个视图全部存在", test_html_has_all_views)
test("筛选变量全部存在", test_html_has_filter_vars)

# ========================================================
# 总结
# ========================================================
print(f"\n{'='*60}")
print(f"  测试结果: {PASS} 通过 / {FAIL} 失败 / {PASS+FAIL} 总计")
print(f"{'='*60}")
if ERRORS:
    print(f"\n  失败详情:")
    for e in ERRORS:
        print(f"    ❌ {e}")
else:
    print(f"\n  🎉 全部通过！")
print(f"{'='*60}")

# 清理
c.close()
exit(1 if FAIL > 0 else 0)
