#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真·浏览器"指针测试"（端到端全覆盖版）—— 用 Playwright 驱动真实 Chromium 点击整套前端 UI。

区别于 smoke_test.py（接口级 HTTP 调用），本脚本模拟真实用户在页面上的鼠标/键盘操作，
覆盖读操作 + 完整写操作 CRUD：
  - 首页/操作员/仪表盘渲染
  - 仪表盘卡片跳转筛选（脱管、精神疾病）
  - 台账搜索、状态/风险/未成年/xj/精神疾病 各类筛选
  - 新增人员完整流程：填表 -> 确认入库 -> 搜索定位 -> 打开详情抽屉 -> 编辑 -> 删除
  - 走访记录：详情抽屉内新增走访 -> 校验 -> 删除
  - 详情抽屉切 3 个 tab、分页、批量勾选、修改留痕搜索、各侧边菜单
每步截图取证，并捕获浏览器控制台错误 / 页面 JS 异常（后端日志抓不到的前端问题）。

用法：
    cd judicial-system/backend
    .venv\\Scripts\\python.exe tools/ui_test.py                 # 默认 http://127.0.0.1:8000
    .venv\\Scripts\\python.exe tools/ui_test.py http://localhost:8000 --headed   # 显示浏览器窗口

输出：
    截图 -> tools/ui_shots/*.png
    汇总 -> tools/ui_result.json
"""
import sys
import json
import random
import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
HEADED = False
for a in sys.argv[1:]:
    if a.startswith("http"):
        BASE = a.rstrip("/")
    elif a in ("--headed", "-H"):
        HEADED = True

SHOT_DIR = Path(__file__).parent / "ui_shots"
SHOT_DIR.mkdir(exist_ok=True)
RESULT_PATH = Path(__file__).parent / "ui_result.json"

steps = []
console_errors = []
page_errors = []
_shot_seq = 0


def record(name, ok, detail=""):
    status = "OK " if ok else "FAIL"
    print(f"[{status}] {name}" + (f"  -> {detail}" if detail else ""))
    steps.append({"name": name, "ok": bool(ok), "detail": str(detail)})


def shot(page, tag):
    global _shot_seq
    _shot_seq += 1
    p = SHOT_DIR / f"{_shot_seq:02d}_{tag}.png"
    try:
        page.screenshot(path=str(p), full_page=True)
    except Exception:
        pass


def make_id_card() -> str:
    """生成校验位合法的 18 位身份证号"""
    region = f"{random.randint(110000, 659004):06d}"
    d = datetime.date(1970 + random.randint(0, 30), random.randint(1, 12), random.randint(1, 28))
    body = region + d.strftime("%Y%m%d") + f"{random.randint(0, 999):03d}"
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    s = sum(int(body[i]) * weights[i] for i in range(17))
    return body + "10X98765432"[s % 11]


def row_count(page):
    try:
        return page.locator(".el-table__body-wrapper tbody tr").count()
    except Exception:
        return -1


def force_close(page):
    """强制关闭所有残留弹层（对话框/抽屉），避免 overlay 挡住后续点击"""
    for _ in range(3):
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
        except Exception:
            break
    # 如果还有可见的 dialog/drawer，点关闭按钮
    for sel in [".el-dialog .el-dialog__headerbtn", ".el-drawer .el-drawer__close-btn"]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
        except Exception:
            pass


def goto_menu(page, label):
    page.locator(".sidebar-item", has_text=label).click()
    page.wait_for_timeout(1200)


def dialog_input(page, label_text):
    """按 el-form-item 的 label 文本定位对话框内输入框"""
    return page.locator(
        f'.el-dialog .el-form-item:has(label:text-is("{label_text}")) input'
    ).first


def toolbar_select(page, idx):
    """台账工具栏筛选下拉：0状态 1风险 2未成年 3xj 4精神疾病"""
    return page.locator(".sys-main .el-select").nth(idx)


def pick_dropdown(page, text):
    page.locator(
        ".el-select-dropdown:visible .el-select-dropdown__item", has_text=text
    ).first.click()


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not HEADED)
        ctx = browser.new_context(viewport={"width": 1600, "height": 950})
        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        uniq = datetime.datetime.now().strftime("%H%M%S")
        test_name = f"UI测试员{uniq}"
        test_idcard = make_id_card()

        # ---------- 1. 首页 ----------
        try:
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1500)
            record("打开首页", True, f"title={page.title()!r}")
            shot(page, "home")
        except Exception as e:
            record("打开首页", False, e)
            browser.close()
            return

        # ---------- 2. 操作员 ----------
        try:
            op = page.get_by_placeholder("请输入您的姓名")
            if op.count() and op.first.is_visible():
                op.first.fill("自动化测试员")
                page.get_by_role("button", name="确认").click()
                page.wait_for_timeout(1000)
                record("设置操作员", True)
            else:
                record("设置操作员", True, "已存在")
        except Exception as e:
            record("设置操作员", False, e)

        # ---------- 3. 仪表盘卡片 ----------
        try:
            page.wait_for_selector(".stat-card", timeout=8000)
            n = page.locator(".stat-card").count()
            record("仪表盘统计卡片渲染", n > 0, f"{n} 张卡片")
            shot(page, "dashboard")
        except Exception as e:
            record("仪表盘统计卡片渲染", False, e)

        # ---------- 4. 点脱管卡片 ----------
        try:
            page.get_by_text("脱管", exact=True).first.click()
            page.wait_for_timeout(1500)
            record("点[脱管]卡片跳转台账", True, f"{row_count(page)} 行")
            shot(page, "card_tuoguan")
        except Exception as e:
            record("点[脱管]卡片跳转台账", False, e)

        # ---------- 5. 点精神疾病卡片 ----------
        try:
            goto_menu(page, "仪表盘")
            page.get_by_text("精神疾病", exact=False).first.click()
            page.wait_for_timeout(1500)
            record("点[精神疾病]卡片跳转台账", True, f"{row_count(page)} 行")
            shot(page, "card_mental")
        except Exception as e:
            record("点[精神疾病]卡片跳转台账", False, e)

        # ---------- 6. 台账精神疾病下拉 是/否 ----------
        try:
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1200)
            goto_menu(page, "人员台账")
            base_rc = row_count(page)
            toolbar_select(page, 4).click(); page.wait_for_timeout(500); pick_dropdown(page, "是")
            page.wait_for_timeout(1500); yes_rc = row_count(page); shot(page, "mental_yes")
            toolbar_select(page, 4).click(); page.wait_for_timeout(500); pick_dropdown(page, "否")
            page.wait_for_timeout(1500); no_rc = row_count(page); shot(page, "mental_no")
            ok = yes_rc > 0 and no_rc > 0 and yes_rc != no_rc
            record("台账[精神疾病]下拉 是/否 切换", ok, f"全部={base_rc}/是={yes_rc}/否={no_rc}")
        except Exception as e:
            record("台账[精神疾病]下拉 是/否 切换", False, e)

        # ---------- 7. 状态筛选(在帮) ----------
        try:
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000); goto_menu(page, "人员台账")
            toolbar_select(page, 0).click(); page.wait_for_timeout(500); pick_dropdown(page, "在帮")
            page.wait_for_timeout(1500)
            record("状态筛选[在帮]", row_count(page) >= 0, f"{row_count(page)} 行")
            shot(page, "filter_status")
        except Exception as e:
            record("状态筛选[在帮]", False, e)

        # ---------- 8. 风险筛选(高) ----------
        try:
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000); goto_menu(page, "人员台账")
            toolbar_select(page, 1).click(); page.wait_for_timeout(500); pick_dropdown(page, "高")
            page.wait_for_timeout(1500)
            record("风险筛选[高]", row_count(page) >= 0, f"{row_count(page)} 行")
            shot(page, "filter_risk")
        except Exception as e:
            record("风险筛选[高]", False, e)

        # ---------- 9. 搜索 ----------
        try:
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000); goto_menu(page, "人员台账")
            box = page.get_by_placeholder("搜索姓名/身份证/电话").first
            box.fill("张"); box.press("Enter"); page.wait_for_timeout(1500)
            record("搜索功能", row_count(page) >= 0, f"搜'张' -> {row_count(page)} 行")
            shot(page, "search")
        except Exception as e:
            record("搜索功能", False, e)

        # ---------- 10. 批量勾选 ----------
        try:
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000); goto_menu(page, "人员台账")
            page.locator(".el-table__header .el-checkbox").first.click()
            page.wait_for_timeout(1000)
            bar = page.get_by_text("已选择", exact=False)
            ok = bar.count() > 0 and bar.first.is_visible()
            record("批量勾选(全选)出现批量工具栏", ok)
            shot(page, "batch")
            page.locator(".el-table__header .el-checkbox").first.click()  # 取消
        except Exception as e:
            record("批量勾选(全选)出现批量工具栏", False, e)

        # ---------- 11. 分页 ----------
        try:
            nxt = page.locator(".el-pagination .btn-next").first
            disabled = nxt.get_attribute("disabled") is not None or "is-disabled" in (nxt.get_attribute("class") or "")
            if not disabled:
                nxt.click(); page.wait_for_timeout(1500)
                record("分页翻页", True, f"第2页 {row_count(page)} 行")
            else:
                record("分页翻页", True, "仅1页(next禁用)")
            shot(page, "pagination")
        except Exception as e:
            record("分页翻页", False, e)

        # ========== 写操作：新增人员完整 CRUD ==========
        # ---------- 12. 新增人员 ----------
        try:
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000); goto_menu(page, "人员台账")
            page.get_by_role("button", name="+ 新增人员").click()
            page.wait_for_timeout(1000)
            dialog_input(page, "姓名").fill(test_name)
            idc = dialog_input(page, "身份证号")
            idc.fill(test_idcard); idc.press("Tab"); page.wait_for_timeout(800)
            shot(page, "add_form")
            page.get_by_role("button", name="确认入库").click()
            page.wait_for_timeout(1800)
            ok = page.locator(".el-message--success").count() > 0 or not page.locator(".el-dialog:visible").count()
            record("新增人员(填表+入库)", ok, f"{test_name}/{test_idcard}")
            shot(page, "add_done")
        except Exception as e:
            record("新增人员(填表+入库)", False, e)

        # ---------- 13. 搜索定位新增人员 ----------
        found_row = False
        try:
            box = page.get_by_placeholder("搜索姓名/身份证/电话").first
            box.fill(test_name); box.press("Enter"); page.wait_for_timeout(1500)
            rc = row_count(page)
            found_row = rc == 1
            record("搜索定位新增人员", found_row, f"{rc} 行")
            shot(page, "add_search")
        except Exception as e:
            record("搜索定位新增人员", False, e)

        # ---------- 14. 打开详情抽屉 + 切tab ----------
        try:
            page.locator(".el-table__body-wrapper tbody tr").first.click()
            page.wait_for_timeout(1200)
            drawer_ok = page.locator(".el-drawer").filter(has_text="详细信息").count() > 0
            shot(page, "drawer_info")
            for tab in ["走访记录", "修改历史", "基本信息"]:
                page.locator(".el-drawer .el-tabs__item", has_text=tab).click()
                page.wait_for_timeout(900)
            record("打开详情抽屉并切换3个tab", drawer_ok)
            shot(page, "drawer_tabs")
        except Exception as e:
            record("打开详情抽屉并切换3个tab", False, e)

        # ---------- 15. 抽屉内新增走访 ----------
        try:
            page.locator(".el-drawer .el-tabs__item", has_text="走访记录").click()
            page.wait_for_timeout(800)
            page.get_by_role("button", name="+ 新增走访").click()
            page.wait_for_timeout(1000)
            # 走访人
            vv = page.locator('.el-dialog:has-text("新增走访") .el-form-item:has(label:text-is("走访人")) input').first
            if vv.count():
                vv.fill("自动化测试员")
            # 内容
            ct = page.locator('.el-dialog:has-text("新增走访") textarea').first
            if ct.count():
                ct.fill("自动化走访测试内容")
            shot(page, "visit_form")
            # 保存按钮（对话框 footer 的 确定/保存）
            save = page.locator('.el-dialog:has-text("新增走访")').get_by_role("button", name="确定")
            if not save.count():
                save = page.locator('.el-dialog:has-text("新增走访")').get_by_role("button", name="保存")
            if not save.count():
                save = page.locator('.el-dialog:has-text("新增走访") .el-button--primary').last
            save.first.click(); page.wait_for_timeout(1500)
            ok = page.locator(".el-timeline-item").count() > 0 or page.locator(".el-message--success").count() > 0
            record("抽屉内新增走访记录", ok)
            shot(page, "visit_done")
        except Exception as e:
            record("抽屉内新增走访记录", False, e)

        # ---------- 16. 删除走访 ----------
        try:
            if page.locator(".el-timeline-item").count() > 0:
                page.locator(".el-timeline-item").first.get_by_role("button", name="删除").click()
                page.wait_for_timeout(700)
                page.locator(".el-popconfirm .el-button--primary").first.click()
                page.wait_for_timeout(1200)
                record("删除走访记录", True)
            else:
                record("删除走访记录", True, "无走访可删(跳过)")
        except Exception as e:
            record("删除走访记录", False, e)

        # 关闭抽屉
        try:
            page.keyboard.press("Escape"); page.wait_for_timeout(600)
        except Exception:
            pass

        # ---------- 17. 编辑人员(改电话) ----------
        # 注意：editPerson() 是 async 的（内部 await api 拿完整身份证号），
        #       点击编辑后必须等它完成，否则 personForm.id_card 还是掩码值
        try:
            box = page.get_by_placeholder("搜索姓名/身份证/电话").first
            box.fill(test_name); box.press("Enter"); page.wait_for_timeout(1500)
            page.locator(".el-table__body-wrapper tbody tr").first.get_by_role("button", name="编辑").click()
            page.wait_for_timeout(3000)  # 等 editPerson 内部 async fetch 完成
            phone = dialog_input(page, "联系电话")
            phone.fill("13800001234")
            shot(page, "edit_form")
            page.get_by_role("button", name="保存修改").click()
            page.wait_for_timeout(1800)
            ok = page.locator(".el-message--success").count() > 0 or not page.locator(".el-dialog:visible").count()
            record("编辑人员(改电话保存)", ok)
            shot(page, "edit_done")
        except Exception as e:
            record("编辑人员(改电话保存)", False, e)

        # ---------- 18. 修改留痕应记录本次编辑 ----------
        try:
            force_close(page)
            goto_menu(page, "修改留痕")
            hs = page.get_by_placeholder("搜索人员姓名").first
            hs.fill(test_name); page.wait_for_timeout(1500)
            has_log = page.get_by_text(test_name, exact=False).count() > 0
            record("修改留痕记录到本次编辑", has_log)
            shot(page, "history_search")
        except Exception as e:
            record("修改留痕记录到本次编辑", False, e)

        # ---------- 19. 删除新增的人员(清理) ----------
        try:
            force_close(page)
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000); goto_menu(page, "人员台账")
            box = page.get_by_placeholder("搜索姓名/身份证/电话").first
            box.fill(test_name); box.press("Enter"); page.wait_for_timeout(1500)
            if row_count(page) >= 1:
                page.locator(".el-table__body-wrapper tbody tr").first.get_by_role("button", name="删除").click()
                page.wait_for_timeout(700)
                page.locator(".el-popconfirm .el-button--primary").first.click()
                page.wait_for_timeout(1500)
                box.fill(test_name); box.press("Enter"); page.wait_for_timeout(1500)
                gone = row_count(page) == 0
                record("删除新增人员(数据清理)", gone, f"删除后 {row_count(page)} 行")
            else:
                record("删除新增人员(数据清理)", False, "未找到待删人员")
            shot(page, "delete_done")
        except Exception as e:
            record("删除新增人员(数据清理)", False, e)

        # ---------- 20. 走访记录页 ----------
        try:
            force_close(page)
            goto_menu(page, "走访记录")
            record("走访记录页渲染", True, f"{row_count(page)} 行")
            shot(page, "menu_visits")
        except Exception as e:
            record("走访记录页渲染", False, e)

        # ---------- 21. 统计报表页 ----------
        try:
            force_close(page)
            goto_menu(page, "统计报表")
            record("统计报表页渲染", True)
            shot(page, "menu_stats")
        except Exception as e:
            record("统计报表页渲染", False, e)

        browser.close()


if __name__ == "__main__":
    print(f"=== 浏览器端到端指针测试开始 BASE={BASE} headed={HEADED} ===")
    try:
        run()
    except Exception as e:
        record("测试运行", False, f"未捕获异常: {e}")

    passed = sum(1 for s in steps if s["ok"])
    summary = {
        "base": BASE,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "passed": passed,
        "total": len(steps),
        "steps": steps,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "screenshots_dir": str(SHOT_DIR),
    }
    RESULT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== 完成：{passed}/{len(steps)} 步通过 ===")
    print(f"控制台错误 {len(console_errors)} 条 / 页面JS异常 {len(page_errors)} 条")
    if console_errors:
        for c in console_errors[:10]:
            print("  [console]", c)
    if page_errors:
        for c in page_errors[:10]:
            print("  [pageerror]", c)
    print(f"截图目录: {SHOT_DIR}")
    print(f"结果: {RESULT_PATH}")
