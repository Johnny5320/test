# -*- coding: utf-8 -*-
"""插入100条2026-01~07真实感人员台账：含修改留痕(edit_logs)与走访(visits)。
运行前已备份 backend/data.db（data.db.bak.20260729_213229）。"""
import sqlite3, random, sys
from datetime import date, datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")
random.seed(20260729)

# ---------- 身份证：GB11643 合法校验位 ----------
COEF = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
CHECK = "10X98765432"
AREAS = ["522425", "522423", "522401", "520381", "520322", "522422"]

def make_id_card(birth: date, male: bool, used: set) -> str:
    while True:
        seq = random.randint(1, 499) * 2 - (1 if male else 0)  # 17位奇=男偶=女
        body = f"{random.choice(AREAS)}{birth:%Y%m%d}{seq:03d}"
        s = sum(int(c) * k for c, k in zip(body, COEF))
        idc = body + CHECK[s % 11]
        if idc not in used:
            used.add(idc)
            return idc

# ---------- 语料 ----------
SURNAMES = "李王张刘陈杨黄赵吴周徐孙马朱胡郭何罗高林郑梁谢宋唐许韩冯邓曹彭曾肖田董潘袁蔡蒋余杜"
M_NAMES = ["伟", "强", "军", "磊", "洪", "建国", "志远", "国华", "文斌", "永刚", "宗福", "明辉", "小平", "德才", "兴旺", "光明", "顺华", "开富", "泽民", "银山"]
F_NAMES = ["芳", "秀英", "丽", "娟", "艳", "玉兰", "桂花", "春梅", "红英", "小燕", "银花", "明珠", "凤仙", "淑芬"]
VILLAGES = ["青龙村", "红岩村", "大坪村", "柏杨社区", "沙坝村", "龙井社区", "水塘村", "岔河村", "石板社区", "白果村", "麻窝村", "梨树坪村"]
CRIMES = [("盗窃罪", "有期徒刑一年六个月", 18), ("危险驾驶罪", "拘役三个月，缓刑六个月", 3), ("故意伤害罪", "有期徒刑二年", 24),
          ("诈骗罪", "有期徒刑三年", 36), ("交通肇事罪", "有期徒刑一年，缓刑二年", 12), ("寻衅滋事罪", "有期徒刑一年二个月", 14),
          ("贩卖毒品罪", "有期徒刑五年", 60), ("开设赌场罪", "有期徒刑一年八个月", 20), ("非法捕捞水产品罪", "拘役四个月", 4),
          ("帮助信息网络犯罪活动罪", "有期徒刑八个月", 8), ("醉酒驾驶机动车", "拘役二个月，缓刑四个月", 2), ("故意毁坏财物罪", "有期徒刑十个月", 10)]
PRISONS = ["省第一监狱", "省第三监狱", "市看守所", "省未成年犯管教所", "省女子监狱", "市强制隔离戒毒所"]
STAFF = ["王明辉", "刘晓芳", "陈国平"]
EMPLOY = ["务农", "外出务工", "个体经营", "灵活就业", "无业", "企业务工"]
EDU_LV = ["小学", "初中", "高中", "中专", "大专"]
HEALTH = ["健康", "健康", "健康", "慢性病（高血压）", "慢性病（糖尿病）", "体弱"]
ECON = ["一般", "一般", "困难", "较好", "低保户"]
V_METHODS = ["上门", "上门", "上门", "电话", "电话", "视频", "到所"]
V_CONTENTS = [
    "到其家中走访，本人在家，情绪稳定，目前{emp}，收入基本稳定，无异常情况。已进行法治教育，叮嘱其遵纪守法。",
    "电话联系本人，询问近期生活及就业情况，其表示{emp}，家庭关系和睦，无重新违法犯罪迹象。",
    "本人到所报到，汇报近期思想动态，态度端正，表示将安心{emp}，服从管理。",
    "会同村（社区）干部上门走访，了解到其{emp}，邻里关系正常，帮教措施落实到位。",
    "视频连线核实其外出务工情况，工作地点稳定，嘱其定期汇报，遵守相关规定。",
    "走访其家属，家属反映本人近期表现良好，{emp}，未发现酗酒、赌博等不良行为。",
    "上门走访并开展心理疏导，本人对之前所犯罪行有悔改认识，生活态度积极。",
    "结合安全生产宣传入户走访，本人配合良好，签订遵纪守法承诺书。",
]
ABNORMALS = [
    "本人近期常与社会闲散人员来往，已当面告诫并加强关注。",
    "家属反映其有酗酒情况，已进行批评教育，约定下次重点回访。",
    "电话多次未接通，后经村干部联系确认在邻县务工，责令其一周内到所说明。",
    "情绪波动较大，因家庭纠纷有过激言语，已联系村调解委员会介入。",
]
NOTES_POOL = ["家庭主要劳动力，育有两子女", "父母年迈需照顾", "有一定种养殖技术", "曾外出务工多年",
              "性格内向，话少", "家庭经济困难，已纳入低保", "配偶在外务工", "独居，需重点关注生活状况", ""]

def q(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"

def rand_dt(d: date) -> str:
    return f"{d} {random.randint(8,17):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}"

def rand_date(a: date, b: date) -> date:
    return a + timedelta(days=random.randint(0, max((b - a).days, 0)))

TODAY = date(2026, 7, 29)
con = sqlite3.connect("backend/data.db")
cur = con.cursor()
used_ids = {r[0] for r in cur.execute("SELECT id_card FROM persons")}
used_names = set()

n_person = n_visit = n_log = 0
for i in range(100):
    male = random.random() < 0.82
    # 姓名去重
    while True:
        name = random.choice(SURNAMES) + random.choice(M_NAMES if male else F_NAMES)
        if name not in used_names:
            used_names.add(name)
            break
    birth = rand_date(date(1966, 1, 1), date(2003, 12, 31))
    idc = make_id_card(birth, male, used_ids)
    crime, sentence, months = random.choice(CRIMES)
    release = rand_date(date(2024, 6, 1), date(2026, 6, 30))
    sent_start = release - timedelta(days=months * 30)
    edu_start = release
    edu_years = random.choice([1, 1, 2, 2, 3, 5])
    edu_end = date(min(edu_start.year + edu_years, 2031), edu_start.month, min(edu_start.day, 28))

    status = random.choices(["在帮", "已解除", "重点关注", "脱管"], weights=[80, 10, 7, 3])[0]
    risk = random.choices(["低", "中", "高"], weights=[70, 22, 8])[0]
    if status == "重点关注" and risk == "低":
        risk = "中"
    key = status == "重点关注" or risk == "高"
    interval = 30 if key else (60 if risk == "中" else 90)
    village = random.choice(VILLAGES)
    emp = random.choice(EMPLOY)
    resp = random.choice(STAFF)
    phone = f"1{random.choice('3589')}{random.randint(10000000,99999999):08d}0"[:11]
    created = rand_date(date(2026, 1, 5), date(2026, 7, 20))
    created_dt = rand_dt(created)
    updated_dt = created_dt

    cur.execute("""INSERT INTO persons(name,id_card,gender,birth_date,household_province,household_city,
        household_district,household_town,household_addr,current_addr,village,phone,original_crime,
        original_sentence,prison_place,sentence_start_date,release_date,edu_start_date,edu_end_date,
        responsible_person,status,is_key_target,category,risk_level,family_name,family_phone,
        marital_status,education_level,employment,health_status,economic_status,has_housing,
        has_drug_history,is_recidivist,has_subsidy,is_minor,is_xj,is_mental,visit_interval_days,
        risk_score,last_visit_date,responsible_org,notes,is_deleted,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        name, idc, "男" if male else "女", str(birth), "贵州省", "毕节市", "织金县", "某镇",
        f"贵州省毕节市织金县某镇{village}{random.randint(1,15)}组", f"某镇{village}{random.randint(1,15)}组",
        village, phone, crime, sentence, random.choice(PRISONS), str(sent_start), str(release),
        str(edu_start), str(edu_end), resp, status, int(key), "刑满释放", risk,
        random.choice(SURNAMES) + random.choice(F_NAMES if male else M_NAMES),
        f"1{random.choice('358')}{random.randint(10000000,99999999):08d}0"[:11],
        random.choice(["已婚", "已婚", "未婚", "离异", "丧偶"]), random.choice(EDU_LV), emp,
        random.choice(HEALTH), random.choice(ECON), int(random.random() < 0.85),
        int(crime == "贩卖毒品罪"), int(random.random() < 0.08), int(random.random() < 0.25),
        0, 0, int(random.random() < 0.03), interval,
        {"低": random.randint(5, 30), "中": random.randint(31, 60), "高": random.randint(61, 90)}[risk],
        None, "某镇司法所", random.choice(NOTES_POOL), 0, created_dt, updated_dt))
    pid = cur.lastrowid
    n_person += 1

    # ---------- 修改留痕：约65%的人被改过1~3个字段 ----------
    if random.random() < 0.65:
        n_edit = random.randint(1, 3)
        edit_day = created
        for _ in range(n_edit):
            edit_day = rand_date(edit_day + timedelta(days=3), min(edit_day + timedelta(days=90), TODAY))
            field, old, new = random.choice([
                ("phone", phone, f"1{random.choice('358')}{random.randint(10000000,99999999):08d}0"[:11]),
                ("current_addr", f"某镇{village}组", f"某镇{random.choice(VILLAGES)}{random.randint(1,15)}组"),
                ("employment", emp, random.choice(EMPLOY)),
                ("risk_level", risk, random.choice(["低", "中", "高"])),
                ("health_status", "健康", random.choice(HEALTH)),
                ("family_phone", "-", f"1{random.choice('358')}{random.randint(10000000,99999999):08d}0"[:11]),
                ("notes", "", random.choice(NOTES_POOL[:-1])),
            ])
            edit_dt = rand_dt(edit_day)
            cur.execute("""INSERT INTO edit_logs(table_name,record_id,field_name,old_value,new_value,editor,edited_at)
                        VALUES('persons',?,?,?,?,?,?)""", (pid, field, str(old), str(new), resp, edit_dt))
            # 真正落库该字段的新值 + updated_at
            if field == "risk_level":
                cur.execute("UPDATE persons SET risk_level=?, updated_at=? WHERE id=?", (new, edit_dt, pid))
            elif field in ("phone", "current_addr", "employment", "health_status", "family_phone", "notes"):
                cur.execute(f"UPDATE persons SET {field}=?, updated_at=? WHERE id=?", (new, edit_dt, pid))
            n_log += 1

    # ---------- 走访：1~4次，间隔贴合 visit_interval ----------
    n_v = random.randint(1, 4) if status != "脱管" else random.randint(0, 1)
    vday = rand_date(created, min(created + timedelta(days=interval), TODAY))
    last_v = None
    for _ in range(n_v):
        if vday > TODAY:
            break
        method = random.choice(V_METHODS)
        content = random.choice(V_CONTENTS).format(emp=emp)
        abnormal = random.random() < 0.07
        cur.execute("""INSERT INTO visits(person_id,visit_date,visitor,visit_method,visit_location,
                    companions,content,has_abnormal,abnormal_detail,photo_paths,quarter,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
            pid, str(vday), resp, method,
            f"某镇{village}其家中" if method == "上门" else ("司法所" if method == "到所" else None),
            random.choice(["村支书", "驻村干部", "网格员", None, None]),
            content + ("" if not abnormal else "走访中发现异常情况。"),
            int(abnormal), random.choice(ABNORMALS) if abnormal else None, None, q(vday), rand_dt(vday)))
        last_v = vday
        n_visit += 1
        vday = vday + timedelta(days=random.randint(int(interval * 0.7), int(interval * 1.2)))
    if last_v:
        cur.execute("UPDATE persons SET last_visit_date=? WHERE id=?", (str(last_v), pid))

con.commit()
cur.execute("SELECT count(*) FROM persons")
tp = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM visits")
tv = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM edit_logs")
tl = cur.fetchone()[0]
cur.execute("SELECT status, count(*) FROM persons GROUP BY status")
st = cur.fetchall()
cur.execute("SELECT min(created_at), max(created_at) FROM persons")
rng = cur.fetchone()
con.close()
print(f"inserted persons={n_person} visits={n_visit} edit_logs={n_log}")
print(f"DB totals: persons={tp} visits={tv} edit_logs={tl}")
print("status dist:", st)
print("created_at range:", rng)
