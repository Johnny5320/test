"""注入100条完整测试数据 — 每个字段都填充"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import Session, select
from app.core.database import engine, create_db_and_tables
from app.core.security import hash_password
from app.models import Person, User, Visit, EditLog

NAMES = [
    "张伟","王芳","李强","赵敏","刘洋","陈静","杨帆","黄磊","周涛","吴刚",
    "郑丽","孙浩","朱峰","马超","胡婷","林森","何勇","高峰","罗敏","梁鑫",
    "宋杰","唐亮","韩冰","曹宁","邓辉","冯博","许建","彭勇","萧然","程刚",
    "蔡磊","潘涛","袁浩","于慧","董明","蒋华","余波","叶枫","杜强","梁静",
    "沈刚","卢芳","姚远","崔健","苏铭","任杰","卢勇","傅磊","钟灵","姜涛",
    "崔浩","彭刚","曹磊","龚涛","丁勇","邓浩","郝明","邵强","白刚","田亮",
    "范伟","汪洋","方圆","石磊","熊刚","金鑫","陆峰","郝健","段强","雷鸣",
    "常勇","武刚","龙飞","万磊","康健","秦涛","侯勇","邓磊","毛杰","邱明",
    "江涛","史刚","顾强","龙磊","孟杰","阎浩","薛涛","段磊","雷刚","常杰",
    "贺勇","武强","龚明","毛涛","邱磊","江浩","史杰","顾刚","龙涛","孟强",
]

PROVINCES = ["江苏省","安徽省","浙江省","山东省","河南省","湖北省","湖南省","四川省","广东省","福建省"]
CITIES = ["南京市","合肥市","杭州市","济南市","郑州市","武汉市","长沙市","成都市","广州市","福州市"]
DISTRICTS = ["玄武区","蜀山区","西湖区","历下区","金水区","武昌区","雨花区","武侯区","天河区","鼓楼区"]
TOWNS = ["孝陵卫街道","五里墩街道","翠苑街道","泉城路街道","花园路街道","中南路街道","雨花街道","玉林街道","天河南街道","湖南路街道"]
VILLAGES = ["孝陵卫社区","五里墩社区","翠苑社区","泉城路社区","花园路社区","中南路社区","雨花社区","玉林社区","天河南社区","湖南路社区",
            "光华门社区","瑞金路社区","红花街道","双塘街道","夫子庙社区","秦虹街道","月牙湖社区","沧波门社区","马群街道","麒麟街道"]

PRISONS = ["南京监狱","江苏省未成年犯管教所","镇江监狱","常州监狱","盐城监狱","连云港监狱","徐州监狱","南京市公安局看守所","苏州市看守所","无锡市看守所"]
CRIMES = ["盗窃罪","抢劫罪","故意伤害罪","诈骗罪","寻衅滋事罪","交通肇事罪","聚众斗殴罪","敲诈勒罪","强奸罪","贩毒罪",
          "非法拘禁罪","故意杀人罪","放火罪","爆炸罪","投放危险物质罪","绑架罪","抢劫枪支罪","劫持航空器罪"]
SENTENCES = ["1年","1年6个月","2年","2年6个月","3年","3年6个月","4年","5年","6年","7年","8年","10年","12年","15年","无期徒刑"]
CATEGORIES = ["刑满释放","社区矫正","假释","保外就医","缓刑","管制","剥夺政治权利"]
STATUSES = ["在帮","已解除","脱管","重点关注"]
RISK_LEVELS = ["高","中","低"]
HEALTH_STATES = ["健康","一般","较差","有慢性病","残疾","精神疾病"]
ECONOMIC_STATES = ["好","一般","困难","特别困难"]
MARITAL_STATES = ["未婚","已婚","离异","丧偶"]
EDUCATION_LEVELS = ["文盲","小学","初中","高中","大专及以上"]
EMPLOYMENTS = ["无业","务农","个体经营","企业员工","临时工","自由职业","退休","学生"]
FAMILY_NAMES = ["张","王","李","赵","刘","陈","杨","黄","周","吴","郑","孙","朱","马","胡"]

def gen_id_card(birth_date: date, gender: str) -> str:
    """生成18位身份证号"""
    area = random.choice(["320102","320104","320105","320106","320111","320113","320114","320115","320116","320117"])
    seq = f"{random.randint(0,9999):04d}"
    g = random.randint(0,9) * 10 + (1 if gender == "男" else 0)
    birth_str = f"{birth_date.year}{birth_date.month:02d}{birth_date.day:02d}"
    day_code = f"{area}{birth_str}{seq}{g}"
    weights = [7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2]
    check_chars = "10X98765432"
    total = sum(int(day_code[i]) * weights[i] for i in range(17))
    return day_code + check_chars[total % 11]


def gen_person(idx: int) -> dict:
    """生成一条完整人员数据"""
    gender = random.choice(["男","女"])
    name = random.choice(NAMES)
    birth_year = random.randint(1965, 2012)
    birth_month = random.randint(1, 12)
    birth_day = random.randint(1, 28)
    birth_date = date(birth_year, birth_month, birth_day)

    id_card = gen_id_card(birth_date, gender)
    province = random.choice(PROVINCES)
    city = random.choice(CITIES)
    district = random.choice(DISTRICTS)
    town = random.choice(TOWNS)
    village = random.choice(VILLAGES)
    prison = random.choice(PRISONS)
    crime = random.choice(CRIMES)
    sentence = random.choice(SENTENCES)
    category = random.choice(CATEGORIES)
    status = random.choice(STATUSES)
    risk = random.choice(RISK_LEVELS)
    health = random.choice(HEALTH_STATES)
    econ = random.choice(ECONOMIC_STATES)
    marital = random.choice(MARITAL_STATES)
    edu = random.choice(EDUCATION_LEVELS)
    emp = random.choice(EMPLOYMENTS)

    sentence_start = date(random.randint(2015,2023), random.randint(1,12), random.randint(1,28))
    release_date = sentence_start + timedelta(days=random.randint(365, 2000))
    edu_start = release_date
    edu_end = edu_start + timedelta(days=random.choice([180,365,730,1095]))

    is_key_target = random.random() < 0.2
    is_minor = birth_year >= 2008
    is_xj = random.random() < 0.05
    is_mental = random.random() < 0.05
    has_drug_history = random.random() < 0.1
    is_recidivist = random.random() < 0.08
    has_housing = random.random() < 0.7
    has_subsidy = random.random() < 0.3

    family_name = random.choice(FAMILY_NAMES) + random.choice(["父","母","兄","姐","妻","夫","子","女","叔","姑"])
    family_phone = f"1{random.choice(['38','39','58','59','86','87','36','37'])}{random.randint(10000000,99999999)}"
    family_name2 = random.choice(FAMILY_NAMES) + random.choice(["父","母","兄","姐","妻","夫","子","女","叔","姑"])
    family_phone2 = f"1{random.choice(['38','39','58','59','86','87','36','37'])}{random.randint(10000000,99999999)}"

    visit_interval = random.choice([30,60,90])

    return {
        "name": name,
        "id_card": id_card,
        "gender": gender,
        "birth_date": birth_date,
        "household_province": province,
        "household_city": city,
        "household_district": district,
        "household_town": town,
        "household_addr": f"{province}{city}{district}{town}{random.randint(1,100)}号",
        "current_addr": f"{province}{city}{district}{town}{random.randint(1,200)}号",
        "village": village,
        "phone": f"1{random.choice(['38','39','58','59','86','87','36','37'])}{random.randint(10000000,99999999)}",
        "original_crime": crime,
        "original_sentence": sentence,
        "prison_place": prison,
        "sentence_start_date": sentence_start,
        "release_date": release_date,
        "edu_start_date": edu_start,
        "edu_end_date": edu_end,
        "responsible_person": random.choice(["张警官","李警官","王警官","赵警官","刘警官","陈警官","杨警官","周警官"]),
        "status": status,
        "is_key_target": is_key_target,
        "category": category,
        "risk_level": risk,
        "family_name": family_name,
        "family_phone": family_phone,
        "family_name2": family_name2,
        "family_phone2": family_phone2,
        "marital_status": marital,
        "education_level": edu,
        "employment": emp,
        "employment_unit": "" if emp in ["无业","务农","退休","学生"] else f"{random.choice(['南京','苏州','无锡','常州'])}市{random.choice(['某某','科技','制造','商贸'])}有限公司",
        "health_status": health,
        "economic_status": econ,
        "has_housing": has_housing,
        "has_drug_history": has_drug_history,
        "is_recidivist": is_recidivist,
        "has_subsidy": has_subsidy,
        "visit_interval_days": visit_interval,
        "responsible_org": random.choice(["XX司法所","YY司法所","ZZ司法所","WW司法所"]),
        "notes": random.choice(["","表现良好","需要重点关注","有稳定工作","家庭困难","定期报到","外出务工","低保户","残疾人","退伍军人"]),
        "is_minor": is_minor,
        "is_xj": is_xj,
        "is_mental": is_mental,
    }


def main():
    create_db_and_tables()
    with Session(engine) as session:
        # 检查是否已有数据
        existing = session.exec(select(Person)).all()
        if existing:
            print(f"已有 {len(existing)} 条数据，跳过注入")
            return

        # 确保admin用户存在
        admin = session.exec(select(User).where(User.username == "admin")).first()
        if not admin:
            admin = User(username="admin", hashed_password=hash_password("admin123"), real_name="系统管理员", role="director", force_change_password=True)
            session.add(admin)
            session.commit()
            print("[OK] 创建默认管理员")

        # 注入100条人员数据
        print("注入100条测试数据...")
        for i in range(100):
            data = gen_person(i)
            person = Person(**data)
            session.add(person)

        session.commit()
        print(f"[OK] 已注入100条完整数据")

        # 统计
        persons = session.exec(select(Person)).all()
        print(f"\n=== 数据统计 ===")
        print(f"总人数: {len(persons)}")
        print(f"未成年: {sum(1 for p in persons if p.is_minor)}")
        print(f"xj: {sum(1 for p in persons if p.is_xj)}")
        print(f"精神疾病: {sum(1 for p in persons if p.is_mental)}")
        print(f"重点: {sum(1 for p in persons if p.is_key_target)}")
        print(f"在帮: {sum(1 for p in persons if p.status == '在帮')}")
        print(f"已解除: {sum(1 for p in persons if p.status == '已解除')}")
        print(f"脱管: {sum(1 for p in persons if p.status == '脱管')}")
        print(f"风险-高: {sum(1 for p in persons if p.risk_level == '高')}")
        print(f"风险-中: {sum(1 for p in persons if p.risk_level == '中')}")
        print(f"风险-低: {sum(1 for p in persons if p.risk_level == '低')}")


if __name__ == "__main__":
    main()
