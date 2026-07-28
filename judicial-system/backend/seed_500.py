"""生成500人全字段台账 + 200条走访记录"""
import random
import sys
import os
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import Session, create_engine, SQLModel
from app.core.database import create_db_and_tables, engine
from app.models import User, Person, Visit
from app.core.security import hash_password


# ========== 身份证工具 ==========
def calc_check(d17):
    w = [7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2]
    cs = '10X98765432'
    return cs[sum(int(d17[i])*w[i] for i in range(17)) % 11]

def gen_id_card(seq):
    """生成合法身份证号"""
    year = 1960 + (seq % 50)
    month = 1 + (seq % 12)
    day = 1 + (seq % 28)
    d17 = f"320102{year}{month:02d}{day:02d}{seq % 1000:03d}"[:17]
    return d17 + calc_check(d17)


# ========== 姓名池 ==========
SURNAMES = ["张","王","李","赵","刘","陈","杨","黄","周","吴","徐","孙","马","朱","胡",
            "郭","何","高","林","罗","郑","梁","谢","宋","唐","韩","曹","许","邓","冯",
            "萧","程","蔡","彭","潘","袁","于","董","余","苏","叶","吕","魏","蒋","田",
            "杜","丁","沈","姜","范","江","傅","钟","卢","汪","戴","崔","任","陆","廖",
            "姚","方","金","邱","夏","谭","石","贾","邹","熊","孟","秦","阎","薛","侯",
            "龙","段","雷","史","黎","贺","顾","毛","郝","龚","邵","万","覃","武","钱",
            "戚","严","尹","温","莫","白","庄","文","向","柳","岳","齐","伍","庞","殷"]

GIVEN_NAMES = ["伟","芳","娜","秀英","敏","静","丽","强","磊","洋","艳","勇","军","杰",
               "娟","涛","明","超","秀兰","霞","平","刚","桂英","华","飞","玉兰","萍",
               "红","玉梅","辉","建华","建国","建军","志强","志明","文","婷","雪","慧",
               "浩","博","宇","泽","轩","睿","梓","子涵","子轩","紫萱","雨桐","欣怡",
               "浩然","思源","思远","佳怡","雨泽","一鸣","天翔","嘉豪","俊杰","志豪"]


# ========== 地址池 ==========
PROVINCES = ["江苏省","浙江省","安徽省","山东省","河南省","湖北省","湖南省","四川省","广东省"]
CITIES = {
    "江苏省": ["南京市","苏州市","无锡市","常州市","徐州市","南通市"],
    "浙江省": ["杭州市","宁波市","温州市","嘉兴市","湖州市","绍兴市"],
    "安徽省": ["合肥市","芜湖市","蚌埠市","淮南市","马鞍山市"],
    "山东省": ["济南市","青岛市","淄博市","烟台市","潍坊市"],
    "河南省": ["郑州市","洛阳市","开封市","安阳市","新乡市"],
    "湖北省": ["武汉市","宜昌市","襄阳市","荆州市","黄石市"],
    "湖南省": ["长沙市","株洲市","湘潭市","衡阳市","邵阳市"],
    "四川省": ["成都市","绵阳市","德阳市","宜宾市","南充市"],
    "广东省": ["广州市","深圳市","佛山市","东莞市","惠州市"],
}
DISTRICTS = ["玄武区","鼓楼区","建邺区","秦淮区","栖霞区","雨花台区","江宁区","浦口区",
             "六合区","溧水区","高淳区","上城区","西湖区","滨江区","余杭区","包河区"]
TOWNS = ["孝陵卫街道","梅园新村街道","新街口街道","湖南路街道","宁海路街道","中央门街道",
         "江东街道","凤凰街道","挹江门街道","热河南路街道","小市街道","迈皋桥街道"]
VILLAGES = ["玄武门社区","梅园新村社区","兰园社区","北安门社区","富贵山社区","后宰门社区",
            "孝陵卫社区","康定里社区","钟灵街社区","沧波门社区","余粮村社区","紫金社区"]


# ========== 罪名/刑期/场所池 ==========
CRIMES = ["盗窃罪","故意伤害罪","诈骗罪","抢劫罪","贩卖毒品罪","聚众斗殴罪","寻衅滋事罪",
          "交通肇事罪","危险驾驶罪","非法持有枪支罪","容留他人吸毒罪","敲诈勒索罪",
          "职务侵占罪","挪用资金罪","合同诈骗罪","非法吸收公众存款罪","开设赌场罪",
          "组织卖淫罪","强迫交易罪","非法经营罪","掩饰隐瞒犯罪所得罪","帮助信息网络犯罪活动罪"]
SENTENCES = ["有期徒刑6个月","有期徒刑1年","有期徒刑1年6个月","有期徒刑2年","有期徒刑2年6个月",
             "有期徒刑3年","有期徒刑3年6个月","有期徒刑4年","有期徒刑5年","有期徒刑6年",
             "有期徒刑7年","有期徒刑8年","有期徒刑10年","有期徒刑12年","有期徒刑15年",
             "缓刑1年","缓刑2年","缓刑3年","拘役3个月","拘役6个月"]
PRISONS = ["南京监狱","南京女子监狱","镇江监狱","常州监狱","无锡监狱","苏州监狱",
           "南通监狱","徐州监狱","盐城监狱","连云港监狱","淮安监狱","扬州监狱",
           "泰州监狱","宿迁监狱","南京看守所","鼓楼看守所","建邺看守所"]
RESPONSIBLE = ["王科员","李科员","张科员","陈科员","赵科员","刘科员","周科员","吴科员",
               "孙科员","马科员","朱科员","胡科员","郭科员","何科员","高科员","林科员"]
ORGANIZATIONS = ["玄武区司法局","鼓楼区司法局","建邺区司法局","秦淮区司法局","栖霞区司法局",
                 "雨花台区司法局","江宁区司法局","浦口区司法局","六合区司法局"]


# ========== 访问方式/内容 ==========
VISIT_METHODS = ["上门","电话","视频"]
VISITORS = RESPONSIBLE + ["社区民警","志愿者小王","志愿者小李","网格员小张","综治主任"]
VISIT_CONTENTS = [
    "了解近期生活状况，未发现异常",
    "询问就业情况，已找到稳定工作",
    "走访家属，家庭关系良好",
    "提醒按时报到，遵守帮教规定",
    "了解思想动态，心态正常",
    "检查居住情况，已搬至新地址",
    "电话回访，未接通，已留言",
    "视频走访，精神状态良好",
    "协助申请低保，材料已提交",
    "了解子女就学情况，一切正常",
    "走访邻居，反映表现良好",
    "提醒参加社区公益活动",
    "了解经济状况，近期有困难",
    "面谈了解思想变化，情绪稳定",
    "核实就业单位信息",
]
ABNORMAL_CONTENTS = [
    "近期情绪波动较大，需重点关注",
    "邻居反映经常深夜外出",
    "未按时报到，已电话提醒",
    "联系不上，家属称外出打工",
    "经济困难，可能影响生活稳定",
]


def generate():
    # 初始化数据库
    create_db_and_tables()
    
    with Session(engine) as session:
        # 创建管理员
        admin = User(
            username="admin",
            hashed_password=hash_password("admin123"),
            real_name="系统管理员",
            role="director",
            force_change_password=False,
        )
        session.add(admin)
        session.commit()
        print("✅ 管理员已创建: admin / admin123")
        
        # ========== 生成500人 ==========
        today = date.today()
        persons = []
        
        for i in range(500):
            province = random.choice(PROVINCES)
            city = random.choice(CITIES[province])
            district = random.choice(DISTRICTS)
            town = random.choice(TOWNS)
            village = random.choice(VILLAGES)
            
            # 状态分布：在帮70%, 已解除15%, 脱管10%, 重点关注5%
            status = random.choices(
                ["在帮","已解除","脱管","重点关注"],
                weights=[70,15,10,5]
            )[0]
            
            # 风险等级：高20%, 中40%, 低40%
            risk = random.choices(["高","中","低"], weights=[20,40,40])[0]
            
            # 时间线
            edu_start = today - timedelta(days=random.randint(30, 1800))
            edu_end = edu_start + timedelta(days=random.choice([180,365,540,730,1095]))
            release = edu_start - timedelta(days=random.randint(1, 60))
            sentence_start = release - timedelta(days=random.randint(180, 3650))
            
            # 走访间隔（根据风险等级）
            visit_interval = {"高": 30, "中": 90, "低": 180}[risk]
            
            # 标签
            is_minor = random.random() < 0.03  # 3%
            is_xj = random.random() < 0.02     # 2%
            is_mental = random.random() < 0.02  # 2%
            is_key = risk == "高" or random.random() < 0.1
            
            # 家属
            family_surname = random.choice(SURNAMES)
            
            id_card = gen_id_card(i)
            gender = "男" if int(id_card[16]) % 2 == 1 else "女"
            birth = datetime.strptime(id_card[6:14], "%Y%m%d").date()
            
            p = Person(
                name=f"{random.choice(SURNAMES)}{random.choice(GIVEN_NAMES)}",
                id_card=id_card,
                gender=gender,
                birth_date=birth,
                household_province=province,
                household_city=city,
                household_district=district,
                household_town=town,
                household_addr=f"{random.choice(['幸福路','和平街','中山路','解放路','建设路','人民路','文化路','光明街'])}{random.randint(1,200)}号{random.randint(1,10)}栋{random.randint(1,6)}单元{random.randint(101,602)}室",
                current_addr=f"{province}{city}{district}{random.choice(['幸福路','和平街','中山路'])}{random.randint(1,100)}号",
                village=village,
                phone=f"1{random.choice(['3','5','7','8','9'])}{random.randint(100000000,999999999)}",
                original_crime=random.choice(CRIMES),
                original_sentence=random.choice(SENTENCES),
                prison_place=random.choice(PRISONS),
                sentence_start_date=sentence_start,
                release_date=release,
                edu_start_date=edu_start,
                edu_end_date=edu_end,
                responsible_person=random.choice(RESPONSIBLE),
                status=status,
                is_key_target=is_key,
                category=random.choice(["刑满释放","社区矫正","安置帮教"]),
                risk_level=risk,
                family_name=f"{family_surname}{random.choice(['父','母','兄','姐','配偶'])}",
                family_phone=f"1{random.choice(['3','5','7','8','9'])}{random.randint(100000000,999999999)}",
                family_name2=f"{family_surname}{random.choice(['叔','姑','舅'])}" if random.random() < 0.3 else None,
                family_phone2=f"1{random.choice(['3','5','7','8','9'])}{random.randint(100000000,999999999)}" if random.random() < 0.3 else None,
                marital_status=random.choice(["未婚","已婚","离异","丧偶"]),
                education_level=random.choice(["文盲","小学","初中","高中","大专及以上"]),
                employment=random.choice(["务农","务工","经商","无业","退休","在校"]),
                employment_unit=f"{random.choice(['XX工厂','YY公司','ZZ工地','个体经营'])}" if random.random() < 0.5 else None,
                health_status=random.choice(["健康","一般","较差","残疾"]),
                economic_status=random.choice(["好","一般","困难","特别困难"]),
                has_housing=random.random() > 0.1,
                has_drug_history=random.random() < 0.08,
                is_recidivist=random.random() < 0.05,
                has_subsidy=random.random() < 0.15,
                is_minor=is_minor,
                is_xj=is_xj,
                is_mental=is_mental,
                visit_interval_days=visit_interval,
                responsible_org=random.choice(ORGANIZATIONS),
                notes=random.choice([None, "表现良好", "需重点关注", "近期有困难", "已就业", "待核实"]),
                created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 365)),
            )
            session.add(p)
            persons.append(p)
        
        session.commit()
        # 刷新获取ID
        for p in persons:
            session.refresh(p)
        
        print(f"✅ 已生成 {len(persons)} 人员记录")
        
        # ========== 生成200条走访记录 ==========
        # 从500人中随机选200人
        visit_persons = random.sample(persons, min(200, len(persons)))
        visit_count = 0
        
        for p in visit_persons:
            # 每人1-5次走访
            num_visits = random.randint(1, 5)
            for j in range(num_visits):
                vdate = today - timedelta(days=random.randint(0, 730))
                has_abnormal = random.random() < 0.08
                
                # 计算季度
                q = (vdate.month - 1) // 3 + 1
                quarter = f"{vdate.year}-Q{q}"
                
                v = Visit(
                    person_id=p.id,
                    visit_date=vdate,
                    visitor=random.choice(VISITORS),
                    visit_method=random.choice(VISIT_METHODS),
                    visit_location=random.choice(["家中","社区办公室","司法所","电话","视频"]),
                    companions=random.choice([None, "社区民警", "网格员", "家属"]),
                    content=random.choice(ABNORMAL_CONTENTS if has_abnormal else VISIT_CONTENTS),
                    has_abnormal=has_abnormal,
                    abnormal_detail=random.choice(ABNORMAL_CONTENTS) if has_abnormal else None,
                    quarter=quarter,
                )
                session.add(v)
                visit_count += 1
                
                # 更新人员的最后走访日期
                if p.last_visit_date is None or vdate > p.last_visit_date:
                    p.last_visit_date = vdate
        
        session.commit()
        print(f"✅ 已生成 {visit_count} 条走访记录")
        
        # ========== 统计 ==========
        from sqlmodel import select, func
        
        total = session.exec(select(func.count()).select_from(select(Person).where(Person.is_deleted == False).subquery())).one()
        active = session.exec(select(func.count()).select_from(select(Person).where(Person.is_deleted == False, Person.status == "在帮").subquery())).one()
        visits = session.exec(select(func.count()).select_from(Visit.subquery())).one()
        
        print(f"\n{'='*40}")
        print(f"  数据库统计")
        print(f"  人员总数: {total}")
        print(f"  在帮: {active}")
        print(f"  走访记录: {visits}")
        print(f"{'='*40}")


if __name__ == "__main__":
    generate()
