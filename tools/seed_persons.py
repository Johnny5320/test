"""注入 100 条字段齐全的测试人员到 data.db

用法：
    python tools/seed_persons.py [数量]
默认 100 条。基于 frontend/data/regions.json 生成真实可校验的
18 位身份证号，并填充 Person 模型全部业务字段。
"""
import os
import sys
import json
import random
from datetime import date, timedelta

BACKEND = os.path.join(os.path.dirname(__file__), "..", "judicial-system", "backend")
FRONTEND = os.path.join(os.path.dirname(__file__), "..", "judicial-system", "frontend")
sys.path.insert(0, os.path.abspath(BACKEND))

from sqlmodel import Session
import app.models  # noqa
from app.core.database import engine
from app.models.person import Person

REGIONS_PATH = os.path.join(FRONTEND, "data", "regions.json")
COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 100

# ---------------- 数据池 ----------------
SURNAMES = list("王李张刘陈杨黄赵周吴徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾萧田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢傅钟姜崔谭廖范汪廖戴夏邱方侯邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段漕钱汤尹黎易常武乔贺赖龚文")
GIVEN_M = ["伟","强","磊","军","洋","勇","杰","涛","明","超","刚","平","辉","斌","鹏","华","飞","旭","宇","浩然","子轩","俊杰","志强","建国","晓东"]
GIVEN_F = ["芳","娟","敏","静","丽","燕","娜","秀英","霞","秀兰","艳","婷","雪","倩","璐","悦","欣","佳","梦琪","雨欣","梓涵","诗涵","佳怡","婷婷","雅雯"]
CRIMES = ["盗窃","诈骗","故意伤害","抢劫","寻衅滋事","开设赌场","贩卖毒品","交通肇事","职务侵占","非法拘禁","聚众斗殴","危险驾驶"]
SENTENCE_UNIT = ["有期徒刑","拘役","缓刑"]
STATUS = ["在帮","待帮教","解除帮教","脱管"]
RISK = ["高","中","低"]
CATEGORY = ["刑满释放人员","社区矫正对象","解除强制隔离戒毒人员","肇事肇祸精神病人"]
MARITAL = ["未婚","已婚","离异","丧偶"]
EDU = ["小学","初中","高中","中专","大专","本科"]
EMPLOY = ["务农","务工","个体经营","无业","企业员工","灵活就业"]
HEALTH = ["健康","一般","患有慢性病","残疾"]
ECON = ["困难","一般","较好"]
PRISON_SUFFIX = ["监狱","看守所","戒毒所"]


def load_regions():
    data = json.load(open(REGIONS_PATH, encoding="utf-8"))
    flat = []
    for pcode, p in data.items():
        pname = p.get("name", "")
        for ccode, c in p.get("cities", {}).items():
            cname = c.get("name", "")
            for dcode, dname in c.get("districts", {}).items():
                flat.append((pcode, pname, ccode, cname, dcode, dname))
    return flat


def id_card_checksum(body17: str) -> str:
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    codes = "10X98765432"
    s = sum(int(body17[i]) * weights[i] for i in range(17))
    return codes[s % 11]


def make_id_card(district_code: str, birth: date, gender_digit: int) -> str:
    # 17 位：6 位地区码 + 8 位出生日期 + 3 位顺序码（末位奇偶表性别）
    seq = f"{random.randint(0, 99):02d}{gender_digit}"
    body = district_code + birth.strftime("%Y%m%d") + seq
    return body + id_card_checksum(body)


def rand_date(start_year, end_year):
    y = random.randint(start_year, end_year)
    m = random.randint(1, 12)
    d = random.randint(1, 28)
    return date(y, m, d)


def main():
    regions = load_regions()
    if not regions:
        print("[错误] regions.json 解析为空")
        return

    existing = set()
    used_cards = set()

    def gen_card(dcode):
        # 避免与已存在或本次重复
        for _ in range(50):
            birth = rand_date(1955, 2006)
            gd = random.choice([1, 3, 5, 7, 9]) if random.random() < 0.5 else random.choice([0, 2, 4, 6, 8])
            card = make_id_card(dcode, birth, gd)
            if card not in used_cards and card not in existing:
                used_cards.add(card)
                return card, birth, "男" if gd % 2 == 1 else "女"
        raise RuntimeError("生成唯一身份证失败")

    with Session(engine) as session:
        # 已有 id_card 收集，避免唯一冲突
        from sqlmodel import select, func
        rows = session.exec(select(Person.id_card)).all()
        existing = set(rows)

        added = 0
        for _ in range(COUNT):
            pcode, pname, ccode, cname, dcode, dname = random.choice(regions)
            card, birth, gender = gen_card(dcode)

            release = rand_date(2020, 2025)
            sen_years = random.choice([1, 2, 3, 4, 5])
            sentence_start = date(release.year - sen_years, release.month, min(release.day, 28))
            edu_start = release
            edu_end = date(min(release.year + random.choice([3, 5]), 2030), release.month, min(release.day, 28))

            is_minor = birth.year >= 2007
            is_mental = random.random() < 0.08
            is_xj = random.random() < 0.05
            has_drug = random.random() < 0.15
            is_recid = random.random() < 0.2
            has_subsidy = random.random() < 0.4
            has_housing = random.random() < 0.85

            given = random.choice(GIVEN_M if gender == "男" else GIVEN_F)
            name = random.choice(SURNAMES) + given
            town = dname.replace("区", "").replace("县", "") + random.choice(["镇", "街道", "乡"])
            village = random.choice(["村", "社区"]) and (random.choice(
                ["和平", "幸福", "建设", "朝阳", "光明", "前进", "新民", "安乐", "团结", "红旗"]) + random.choice(["村", "社区"]))

            person = Person(
                name=name,
                id_card=card,
                gender=gender,
                birth_date=birth,
                household_province=pname,
                household_city=cname,
                household_district=dname,
                household_town=town,
                household_addr=f"{pname}{cname}{dname}{town}{random.randint(1,99)}号",
                current_addr=f"{cname}{random.choice(['XX路','XX小区','XX街'])}{random.randint(1,200)}号",
                village=village,
                phone="1" + str(random.choice([3,5,7,8,9])) + "".join(random.choice("0123456789") for _ in range(9)),
                original_crime=random.choice(CRIMES),
                original_sentence=random.choice(SENTENCE_UNIT) + str(random.choice([6,12,18,24,36])) + "个月",
                prison_place=random.choice(["第一", "第二", "第三"]) + random.choice(PRISON_SUFFIX),
                sentence_start_date=sentence_start,
                release_date=release,
                edu_start_date=edu_start,
                edu_end_date=edu_end,
                responsible_person=random.choice(["张建国","李卫东","王志强","赵为民","陈晓红","刘海燕"]) + "（司法所）",
                status=random.choices(STATUS, weights=[70, 10, 15, 5])[0],
                is_key_target=random.random() < 0.15,
                category=random.choice(CATEGORY),
                risk_level=random.choices(RISK, weights=[15, 35, 50])[0],
                family_name=random.choice(SURNAMES) + "某",
                family_phone="1" + str(random.choice([3,5,7,8,9])) + "".join(random.choice("0123456789") for _ in range(9)),
                family_name2=random.choice(SURNAMES) + "某",
                family_phone2="1" + str(random.choice([3,5,7,8,9])) + "".join(random.choice("0123456789") for _ in range(9)),
                marital_status=random.choice(MARITAL),
                education_level=random.choice(EDU),
                employment=random.choice(EMPLOY),
                employment_unit=random.choice(["暂无", "XX有限公司", "个体经营", "XX工厂"]) if random.random() < 0.5 else None,
                health_status=random.choice(HEALTH),
                economic_status=random.choice(ECON),
                has_housing=has_housing,
                has_drug_history=has_drug,
                is_recidivist=is_recid,
                has_subsidy=has_subsidy,
                is_minor=is_minor,
                is_xj=is_xj,
                is_mental=is_mental,
                visit_interval_days=random.choice([30, 60, 90]),
                risk_score=random.randint(0, 100),
                last_visit_date=release + timedelta(days=random.randint(10, 200)),
                responsible_org=random.choice(["XX镇司法所", "XX街道司法所", "XX乡司法所"]),
                photo_path=None,
                notes=random.choice(["", "需重点关注", "家庭困难", "就业意向明确", "情绪稳定"]),
                is_deleted=False,
            )
            session.add(person)
            added += 1
            if added % 20 == 0:
                session.commit()
        session.commit()
        print(f"成功注入 {added} 条测试人员（含原有数据，总库现有 {len(existing) + added} 条）。")


if __name__ == "__main__":
    main()
