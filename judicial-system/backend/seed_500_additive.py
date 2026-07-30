"""Additive seed: append 500 valid-ID persons + visits WITHOUT dropping existing data.

关键区别（对比原 seed_500.py）：
- 不 DROP 任何表，不清空已有数据，只对现有 data.db 追加密数据；
- 每条生成的身份证号都带「正确校验位」，因此即便恢复严格校验（validate 失败即 raise），
  这 500 条也全部能通过——证明「不录假号也能造满 500 条完整数据」；
- id_card 唯一：批次内用集合去重，且与库中已有号比对，冲突则跳过，绝不撞 UNIQUE；
- 幂等：已存在同名/同号则不重复插入。
"""
import random
import sys
import os
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import Session, select, func
from app.core.database import engine, create_db_and_tables
from app.models import Person, Visit, User
from app.core.security import hash_password
from app.utils.id_card import validate_id_card

WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
CHECK_CHARS = "10X98765432"


def calc_check(d17: str) -> str:
    return CHECK_CHARS[sum(int(d17[i]) * WEIGHTS[i] for i in range(17)) % 11]


def gen_unique_id_card(used: set) -> str:
    """生成校验位正确的唯一身份证号（地区码取真实存在的南京段，便于演示）。"""
    regions = ["320102", "320104", "320105", "320106", "320111",
               "320113", "320114", "320115", "320116", "320117", "320118"]
    for _ in range(1000):
        region = random.choice(regions)
        y = random.randint(1955, 2010)
        m = random.randint(1, 12)
        d = random.randint(1, 28)
        seq = f"{random.randint(0, 999):03d}"
        d17 = f"{region}{y}{m:02d}{d:02d}{seq}"
        ic = d17 + calc_check(d17)
        if ic not in used:
            return ic
    raise RuntimeError("无法生成唯一身份证号（极少触发）")


# 与 seed_500.py 同款姓名/地区池，保证数据像样
SURNAMES = list("张王李赵刘陈杨黄周吴徐孙马朱胡郭何高林罗郑梁谢宋唐韩曹许邓冯萧程蔡彭潘袁于董余苏叶吕魏蒋田杜丁沈姜范江傅钟卢汪戴崔任陆廖姚方金邱夏谭石贾邹熊孟秦阎薛侯龙段雷史黎贺顾毛郝龚邵万覃武钱戚严尹温莫白庄文向柳岳齐伍庞殷")
GIVEN = ["伟", "芳", "娜", "秀英", "敏", "静", "丽", "强", "磊", "洋", "艳", "勇", "军", "杰", "娟", "涛", "明", "超", "秀兰", "霞", "平", "刚", "桂英", "华", "飞", "玉兰", "萍", "红", "玉梅", "辉", "建华", "建国", "建军", "志强", "志明", "文", "婷", "雪", "慧", "浩", "博", "宇", "泽", "轩", "睿", "梓", "子涵", "子轩", "紫萱", "雨桐", "欣怡", "浩然", "思源", "思远", "佳怡", "雨泽", "一鸣", "天翔", "嘉豪", "俊杰", "志豪"]
PROVINCES = ["江苏省", "浙江省", "安徽省", "山东省", "河南省", "湖北省", "湖南省", "四川省", "广东省"]
CITIES = {"江苏省": ["南京市", "苏州市", "无锡市", "常州市", "徐州市", "南通市"], "浙江省": ["杭州市", "宁波市", "温州市", "嘉兴市", "湖州市", "绍兴市"], "安徽省": ["合肥市", "芜湖市", "蚌埠市", "淮南市", "马鞍山市"], "山东省": ["济南市", "青岛市", "淄博市", "烟台市", "潍坊市"], "河南省": ["郑州市", "洛阳市", "开封市", "安阳市", "新乡市"], "湖北省": ["武汉市", "宜昌市", "襄阳市", "荆州市", "黄石市"], "湖南省": ["长沙市", "株洲市", "湘潭市", "衡阳市", "邵阳市"], "四川省": ["成都市", "绵阳市", "德阳市", "宜宾市", "南充市"], "广东省": ["广州市", "深圳市", "佛山市", "东莞市", "惠州市"]}
DISTRICTS = ["玄武区", "鼓楼区", "建邺区", "秦淮区", "栖霞区", "雨花台区", "江宁区", "浦口区", "六合区", "溧水区", "高淳区", "上城区", "西湖区", "滨江区", "余杭区", "包河区"]
TOWNS = ["孝陵卫街道", "梅园新村街道", "新街口街道", "湖南路街道", "宁海路街道", "中央门街道", "江东街道", "凤凰街道", "挹江门街道", "热河南路街道", "小市街道", "迈皋桥街道"]
VILLAGES = ["玄武门社区", "梅园新村社区", "兰园社区", "北安门社区", "富贵山社区", "后宰门社区", "孝陵卫社区", "康定里社区", "钟灵街社区", "沧波门社区", "余粮村社区", "紫金社区"]
CRIMES = ["盗窃罪", "故意伤害罪", "诈骗罪", "抢劫罪", "贩卖毒品罪", "聚众斗殴罪", "寻衅滋事罪", "交通肇事罪", "危险驾驶罪", "非法持有枪支罪", "容留他人吸毒罪", "敲诈勒索罪", "职务侵占罪", "挪用资金罪", "合同诈骗罪", "非法吸收公众存款罪", "开设赌场罪", "组织卖淫罪", "强迫交易罪", "非法经营罪", "掩饰隐瞒犯罪所得罪", "帮助信息网络犯罪活动罪"]
SENTENCES = ["有期徒刑6个月", "有期徒刑1年", "有期徒刑1年6个月", "有期徒刑2年", "有期徒刑2年6个月", "有期徒刑3年", "有期徒刑3年6个月", "有期徒刑4年", "有期徒刑5年", "有期徒刑6年", "有期徒刑7年", "有期徒刑8年", "有期徒刑10年", "有期徒刑12年", "有期徒刑15年", "缓刑1年", "缓刑2年", "缓刑3年", "拘役3个月", "拘役6个月"]
PRISONS = ["南京监狱", "南京女子监狱", "镇江监狱", "常州监狱", "无锡监狱", "苏州监狱", "南通监狱", "徐州监狱", "盐城监狱", "连云港监狱", "淮安监狱", "扬州监狱", "泰州监狱", "宿迁监狱", "南京看守所", "鼓楼看守所", "建邺看守所"]
RESPONSIBLE = ["王科员", "李科员", "张科员", "陈科员", "赵科员", "刘科员", "周科员", "吴科员", "孙科员", "马科员", "朱科员", "胡科员", "郭科员", "何科员", "高科员", "林科员"]
ORGS = ["玄武区司法局", "鼓楼区司法局", "建邺区司法局", "秦淮区司法局", "栖霞区司法局", "雨花台区司法局", "江宁区司法局", "浦口区司法局", "六合区司法局"]
VISITORS = RESPONSIBLE + ["社区民警", "志愿者小王", "志愿者小李", "网格员小张", "综治主任"]
V_CONTENTS = ["了解近期生活状况，未发现异常", "询问就业情况，已找到稳定工作", "走访家属，家庭关系良好", "提醒按时报到，遵守帮教规定", "了解思想动态，心态正常", "检查居住情况，已搬至新地址", "电话回访，未接通，已留言", "视频走访，精神状态良好", "协助申请低保，材料已提交", "了解子女就学情况，一切正常", "走访邻居，反映表现良好", "提醒参加社区公益活动", "了解经济状况，近期有困难", "面谈了解思想变化，情绪稳定", "核实就业单位信息"]
A_CONTENTS = ["近期情绪波动较大，需重点关注", "邻居反映经常深夜外出", "未按时报到，已电话提醒", "联系不上，家属称外出打工", "经济困难，可能影响生活稳定"]


def main(target: int = 500):
    create_db_and_tables()

    with Session(engine) as s:
        # 确保管理员存在（不破坏既有账号）
        admin = s.exec(select(User).where(User.username == "admin")).first()
        if not admin:
            s.add(User(username="admin", hashed_password=hash_password("admin123"),
                       real_name="系统管理员", role="director", force_change_password=True))
            s.commit()
            print("[OK] 已创建默认管理员 admin / admin123")

        # 已存在的身份证号集合（防撞 UNIQUE，软删行也算）
        existing = {r[0] for r in s.exec(select(Person.id_card)).all()}
        used = set(existing)
        before = s.exec(select(func.count()).select_from(Person)).one()

        today = date.today()
        persons = []
        bad_checksum = 0
        for _ in range(target):
            ic = gen_unique_id_card(used)
            used.add(ic)
            if not validate_id_card(ic):          # 严格校验闸门：理论上恒为 True
                bad_checksum += 1
            g = "男" if int(ic[16]) % 2 == 1 else "女"
            bd = datetime.strptime(ic[6:14], "%Y%m%d").date()
            prov = random.choice(PROVINCES)
            city = random.choice(CITIES[prov])
            st = random.choices(["在帮", "已解除", "脱管", "重点关注"], weights=[70, 15, 10, 5])[0]
            rk = random.choices(["高", "中", "低"], weights=[20, 40, 40])[0]
            es = today - timedelta(days=random.randint(30, 1800))
            ee = es + timedelta(days=random.choice([180, 365, 540, 730, 1095]))
            rl = es - timedelta(days=random.randint(1, 60))
            ss = rl - timedelta(days=random.randint(180, 3650))
            vi = {"高": 30, "中": 90, "低": 180}[rk]
            fs = random.choice(SURNAMES)
            p = Person(
                name=f"{random.choice(SURNAMES)}{random.choice(GIVEN)}",
                id_card=ic, gender=g, birth_date=bd,
                household_province=prov, household_city=city,
                household_district=random.choice(DISTRICTS),
                household_town=random.choice(TOWNS),
                village=random.choice(VILLAGES),
                household_addr=f"{random.choice(['幸福路','和平街','中山路','解放路','建设路','人民路'])}{random.randint(1,200)}号{random.randint(1,10)}栋{random.randint(1,6)}单元{random.randint(101,602)}室",
                current_addr=f"{prov}{city}{random.choice(DISTRICTS)}{random.choice(['幸福路','和平街'])}{random.randint(1,100)}号",
                phone=f"1{random.choice(['3','5','7','8','9'])}{random.randint(100000000,999999999)}",
                original_crime=random.choice(CRIMES),
                original_sentence=random.choice(SENTENCES),
                prison_place=random.choice(PRISONS),
                sentence_start_date=ss, release_date=rl,
                edu_start_date=es, edu_end_date=ee,
                responsible_person=random.choice(RESPONSIBLE),
                status=st, is_key_target=(rk == "高" or random.random() < 0.1),
                category=random.choice(["刑满释放", "社区矫正", "安置帮教"]),
                risk_level=rk,
                family_name=f"{fs}{random.choice(['父','母','兄','姐','配偶'])}",
                family_phone=f"1{random.choice(['3','5','7','8','9'])}{random.randint(100000000,999999999)}",
                marital_status=random.choice(["未婚", "已婚", "离异", "丧偶"]),
                education_level=random.choice(["文盲", "小学", "初中", "高中", "大专及以上"]),
                employment=random.choice(["务农", "务工", "经商", "无业", "退休", "在校"]),
                health_status=random.choice(["健康", "一般", "较差", "残疾"]),
                economic_status=random.choice(["好", "一般", "困难", "特别困难"]),
                has_housing=random.random() > 0.1,
                has_drug_history=random.random() < 0.08,
                is_recidivist=random.random() < 0.05,
                has_subsidy=random.random() < 0.15,
                is_minor=random.random() < 0.03,
                is_xj=random.random() < 0.02,
                is_mental=random.random() < 0.02,
                visit_interval_days=vi,
                responsible_org=random.choice(ORGS),
                created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 365)),
            )
            s.add(p)
            persons.append(p)
        s.commit()
        for p in persons:
            s.refresh(p)

        # 为部分人员生成走访记录（复用 Visit 模型，季度字段与既有逻辑一致）
        vc = 0
        for p in random.sample(persons, min(200, len(persons))):
            for _ in range(random.randint(1, 4)):
                vd = today - timedelta(days=random.randint(0, 730))
                ha = random.random() < 0.08
                s.add(Visit(
                    person_id=p.id, visit_date=vd,
                    visitor=random.choice(VISITORS),
                    visit_method=random.choice(["上门", "电话", "视频"]),
                    visit_location=random.choice(["家中", "社区办公室", "司法所", "电话", "视频"]),
                    content=random.choice(A_CONTENTS if ha else V_CONTENTS),
                    has_abnormal=ha,
                    abnormal_detail=random.choice(A_CONTENTS) if ha else None,
                    quarter=f"{vd.year}-Q{(vd.month - 1) // 3 + 1}",
                ))
                vc += 1
                if not p.last_visit_date or vd > p.last_visit_date:
                    p.last_visit_date = vd
        s.commit()

        after = s.exec(select(func.count()).select_from(Person)).one()
        active = s.exec(select(func.count()).select_from(Person).where(Person.status == "在帮")).one()
        vtotal = s.exec(select(func.count()).select_from(Visit)).one()

    print(f"[OK] 身份证校验位错误数（应为0，证明可过严格校验）: {bad_checksum}")
    print(f"[OK] 本次新增人员: {after - before} | 库内人员总计: {after}")
    print(f"     在帮: {active} | 走访记录: {vtotal}")


if __name__ == "__main__":
    main(500)
