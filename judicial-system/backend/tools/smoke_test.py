#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接口级"指针测试"脚本 —— 模拟前端逐个调用所有功能/接口，最大化触发后端日志。

等价于用自动化方式"点"遍每个功能点：覆盖正常路径 + 典型异常路径（错误密码、重复身份证、
无效 token、不存在的人员、非法文件类型等），从而让后端每个接口/函数的日志都被收集到。

用法：
    cd judicial-system/backend
    python tools/smoke_test.py                # 默认 http://localhost:8000
    python tools/smoke_test.py http://localhost:8001

前置：
    1) 先启动服务（双击 start.bat，或 uvicorn app.main:app --port 8000）
    2) 默认管理员 admin / admin123 可用

依赖：
    标准库即可；导入测试需要 openpyxl（项目已依赖，缺失则自动跳过该项）。

输出：
    控制台逐接口结果；并写 tools/smoke_result.json 汇总。
"""
import sys
import os
import io
import json
import random
import datetime
import urllib.request
import urllib.error

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
ADMIN = ("admin", "admin123")
results = []


def _make_id_card() -> str:
    """生成一个校验位合法的 18 位身份证号（测试用，尽量唯一）"""
    region = f"{random.randint(110000, 659004):06d}"
    d = datetime.date(1970 + random.randint(0, 30), random.randint(1, 12), random.randint(1, 28))
    body = region + d.strftime("%Y%m%d") + f"{random.randint(0, 999):03d}"
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    s = sum(int(body[i]) * weights[i] for i in range(17))
    check = "10X98765432"[s % 11]
    return body + check


def call(method, path, *, json_body=None, token=None, raw=False, multipart=None):
    url = BASE + path
    data = None
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if multipart is not None:
        ct, data = multipart
        headers["Content-Type"] = ct
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", "replace")
            status = resp.status
        parsed = None
        if not raw and body:
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = None
        return status, parsed, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = None
        return e.code, parsed, None
    except Exception as e:  # 网络/连接错误
        return None, None, str(e)


def record(name, method, path, status, err=None):
    ok = (status is not None and 200 <= status < 400)
    results.append({"name": name, "method": method, "path": path,
                    "status": status, "ok": ok, "error": err})
    if status is not None:
        tag = "OK  " if ok else f"HTTP {status}"
    else:
        tag = "ERR "
    print(f"[{tag}] {method:5s} {path}  -> {status if status is not None else err}")


def _multipart(fields: dict, file_tuple):
    boundary = "----smoketestboundary"
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{str(v)}\r\n'.encode("utf-8"))
    fname, fcontent, ftype = file_tuple
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\n'
        f"Content-Type: {ftype}\r\n\r\n".encode("utf-8") + fcontent + b"\r\n"
    )
    body = b"".join(parts) + f"--{boundary}--\r\n".encode("utf-8")
    return f"multipart/form-data; boundary={boundary}", body


def main():
    print(f"=== 指针测试开始 BASE={BASE} ===")

    # 1. 健康检查
    st, _, err = call("GET", "/health")
    record("健康检查", "GET", "/health", st, err)

    # 2. 登录（正确）
    st, body, err = call("POST", "/api/auth/login",
                         json_body={"username": ADMIN[0], "password": ADMIN[1]})
    record("登录(正确)", "POST", "/api/auth/login", st, err)
    token = body.get("access_token") if body else None

    # 3. 登录（错误密码，期望 401）
    st, _, err = call("POST", "/api/auth/login",
                      json_body={"username": "admin", "password": "wrong-password"})
    record("登录(错误密码,期望401)", "POST", "/api/auth/login", st, err)

    if not token:
        print("未获取到 token，无法继续鉴权接口测试。")
        _finish()
        return

    # 4. 统计汇总
    st, _, err = call("GET", "/api/persons/stats/summary", token=token)
    record("统计汇总", "GET", "/api/persons/stats/summary", st, err)

    # 5. 人员列表
    st, _, err = call("GET", "/api/persons?page=1&page_size=5", token=token)
    record("人员列表", "GET", "/api/persons", st, err)

    # 6. 新增人员
    idc = _make_id_card()
    st, body, err = call("POST", "/api/persons", json_body={
        "name": "指针测试员", "id_card": idc, "gender": "男",
        "status": "在帮", "risk_level": "低", "responsible_person": "测试员",
    }, token=token)
    record("新增人员", "POST", "/api/persons", st, err)
    pid = body.get("id") if body else None

    # 6b. 重复身份证（期望 400）
    if pid:
        st, _, err = call("POST", "/api/persons", json_body={
            "name": "重复人员", "id_card": idc, "status": "在帮", "risk_level": "低",
        }, token=token)
        record("新增人员(重复身份证,期望400)", "POST", "/api/persons", st, err)

    # 7-10. 人员详情/修改/修改历史/风险评分
    if pid:
        st, _, err = call("GET", f"/api/persons/{pid}", token=token)
        record("获取人员详情", "GET", f"/api/persons/{pid}", st, err)

        st, _, err = call("PUT", f"/api/persons/{pid}", json_body={
            "phone": "13800000000", "editor": "指针测试",
        }, token=token)
        record("修改人员", "PUT", f"/api/persons/{pid}", st, err)

        st, _, err = call("GET", f"/api/persons/{pid}/edit-logs", token=token)
        record("修改历史", "GET", f"/api/persons/{pid}/edit-logs", st, err)

        st, _, err = call("GET", f"/api/persons/{pid}/risk-score", token=token)
        record("风险评分", "GET", f"/api/persons/{pid}/risk-score", st, err)

    # 11-13. 服刑场所 / 趋势 / 季度报表
    st, _, err = call("GET", "/api/persons/prisons", token=token)
    record("服刑场所", "GET", "/api/persons/prisons", st, err)

    st, _, err = call("GET", "/api/persons/stats/trend?months=6", token=token)
    record("月度趋势", "GET", "/api/persons/stats/trend", st, err)

    st, _, err = call("GET", "/api/persons/reports/quarterly", token=token)
    record("季度报表", "GET", "/api/persons/reports/quarterly", st, err)

    # 14. 走访记录
    if pid:
        st, body, err = call("POST", "/api/visits", json_body={
            "person_id": pid, "visit_date": "2026-07-01", "visit_method": "上门",
            "visitor": "测试员", "content": "指针测试走访",
        }, token=token)
        record("新增走访", "POST", "/api/visits", st, err)
        vid = body.get("id") if body else None

        st, _, err = call("GET", f"/api/visits?person_id={pid}", token=token)
        record("走访列表", "GET", "/api/visits", st, err)

        st, _, err = call("GET", "/api/visits/stats/quarterly", token=token)
        record("走访季度统计", "GET", "/api/visits/stats/quarterly", st, err)

        if vid:
            st, _, err = call("GET", f"/api/visits/{vid}", token=token)
            record("走访详情", "GET", f"/api/visits/{vid}", st, err)

            st, _, err = call("PUT", f"/api/visits/{vid}", json_body={
                "person_id": pid, "visit_date": "2026-07-02", "visit_method": "电话",
                "visitor": "测试员", "content": "修改后走访",
            }, token=token)
            record("修改走访", "PUT", f"/api/visits/{vid}", st, err)

            st, _, err = call("DELETE", f"/api/visits/{vid}", token=token)
            record("删除走访", "DELETE", f"/api/visits/{vid}", st, err)

    # 15. 提醒汇总
    st, _, err = call("GET", "/api/reminders", token=token)
    record("提醒汇总", "GET", "/api/reminders", st, err)

    # 16. 导出 / 导入模板
    st, _, err = call("GET", "/api/persons/export/excel", token=token, raw=True)
    record("导出Excel", "GET", "/api/persons/export/excel", st, err)

    st, _, err = call("GET", "/api/persons/import/template", token=token, raw=True)
    record("导入模板", "GET", "/api/persons/import/template", st, err)

    # 17. Excel 导入
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["姓名", "身份证号", "性别", "状态", "风险等级", "帮教责任人"])
        ws.append(["导入测试员", _make_id_card(), "男", "在帮", "低", "测试员"])
        buf = io.BytesIO()
        wb.save(buf)
        content = buf.getvalue()
        mp = _multipart(
            {"person_id": str(pid or 1)},
            ("import_test.xlsx", content,
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        )
        st, _, err = call("POST", "/api/persons/import/excel", multipart=mp, token=token)
        record("Excel导入", "POST", "/api/persons/import/excel", st, err)
    except Exception as e:
        record("Excel导入", "POST", "/api/persons/import/excel", None, f"跳过: {e}")

    # 18. 批量操作
    if pid:
        st, _, err = call("POST", "/api/persons/batch/status",
                          json_body={"ids": [pid], "status": "重点关注"}, token=token)
        record("批量改状态", "POST", "/api/persons/batch/status", st, err)

        st, _, err = call("POST", "/api/persons/batch/risk",
                          json_body={"ids": [pid], "risk_level": "中"}, token=token)
        record("批量改风险", "POST", "/api/persons/batch/risk", st, err)

    # 19. 文件上传（含非法类型 + 合法 pdf）
    if pid:
        mp = _multipart({"person_id": str(pid), "file_type": "扫描件"},
                        ("test.txt", b"hello", "text/plain"))
        st, _, err = call("POST", "/api/files/upload", multipart=mp, token=token)
        record("文件上传(非法类型,期望400)", "POST", "/api/files/upload", st, err)

        pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
        mp = _multipart({"person_id": str(pid), "file_type": "扫描件"},
                        ("scan.pdf", pdf, "application/pdf"))
        st, body, err = call("POST", "/api/files/upload", multipart=mp, token=token)
        record("文件上传(pdf)", "POST", "/api/files/upload", st, err)
        fid = body.get("id") if body else None

        if fid:
            st, _, err = call("GET", f"/api/files/list/{pid}", token=token)
            record("文件列表", "GET", f"/api/files/list/{pid}", st, err)

            st, _, err = call("DELETE", f"/api/files/{fid}", token=token)
            record("文件删除", "DELETE", f"/api/files/{fid}", st, err)

    # 20. 无效 token（期望 401）
    st, _, err = call("GET", "/api/persons", token="invalid.token.value")
    record("无效token(期望401)", "GET", "/api/persons", st, err)

    # 21. 不存在的人员（期望 404）
    st, _, err = call("GET", "/api/persons/999999999", token=token)
    record("不存在人员(期望404)", "GET", "/api/persons/999999999", st, err)

    # 22. 当前用户
    st, _, err = call("GET", "/api/auth/me", token=token)
    record("当前用户", "GET", "/api/auth/me", st, err)

    # 23. 改密码（原密码错误，期望 400）
    st, _, err = call("POST", "/api/auth/change-password", json_body={
        "old_password": "wrong", "new_password": "abc12345",
    }, token=token)
    record("改密码(原密码错,期望400)", "POST", "/api/auth/change-password", st, err)

    # 24. 刷新 token
    rft = body.get("refresh_token") if body else None
    if rft:
        st, _, err = call("POST", "/api/auth/refresh",
                          json_body={"refresh_token": rft}, token=token)
        record("刷新token", "POST", "/api/auth/refresh", st, err)

    # 25. 软删除创建的人员（清理）
    if pid:
        st, _, err = call("DELETE", f"/api/persons/{pid}", token=token)
        record("删除人员(软删)", "DELETE", f"/api/persons/{pid}", st, err)

    _finish()


def _finish():
    total = len(results)
    ok = sum(1 for r in results if r["ok"])
    print(f"\n=== 指针测试完成：{ok}/{total} 通过 ===")
    out = os.path.join(os.path.dirname(__file__), "smoke_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"base": BASE, "total": total, "ok": ok, "results": results},
                  f, ensure_ascii=False, indent=2)
    print(f"结果已写入: {out}")


if __name__ == "__main__":
    main()
