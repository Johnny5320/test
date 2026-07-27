"""修复第一轮替换导致的重复ID问题 — 手动分配唯一ID"""
import re, glob

ID_CARD_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
ID_CARD_CHECK_CHARS = "10X98765432"

def fix_checksum(id17: str) -> str:
    total = sum(int(id17[i]) * ID_CARD_WEIGHTS[i] for i in range(17))
    return id17 + ID_CARD_CHECK_CHARS[total % 11]

# integration_full.py: 需要7个唯一ID
# 原来是 0001-0007，现在全变成了 0002
# 手动分配:
intg_ids = {
    "张三_5天到期":   "320102199001010003",  # 0001→0003 (check=3)
    "李四_15天到期":  "320102199001010005",  # 0002→0005 (check=5)
    "王五_25天到期":  "320102199001010007",  # 0003→0007 (check=7)
    "赵六_已超期":    "320102199001010009",  # 0004→0009 (check=9)
    "钱七_正常":      "320102199001011001",  # 新基值
    "孙八_已解除":    "320102199001011003",  # 新基值
    "周九_未成年精神": "320102199001011005",  # 新基值
}

# test_expiring_filter.py: 需要多个唯一ID
# 原来是 11001-11012，现在全变成了 11005
exp_ids = {
    "15天到期":     "320102199001011001",
    "15天到期B":    "320102199001011003",
    "已解除到期":   "320102199001011005",  # 保持
    "无截止日期":   "320102199001011007",
    "未成年到期":   "320102199001011009",
    "成年到期":     "320102199001011011",
    "精神到期":     "320102199001011013",
    "正常到期":     "320102199001011015",
    "提醒测试A":    "320102199001011017",
    "字段测试":     "320102199001011019",
    "走访字段测试":  "320102199001011021",
}

# 验证所有ID的校验位
print("=== 验证ID校验位 ===")
for name, idcard in {**intg_ids, **exp_ids}.items():
    valid = fix_checksum(idcard[:17])
    ok = "✓" if valid == idcard else f"✗ 应为 {valid}"
    print(f"  {name}: {idcard} {ok}")

# 修复 integration_full.py
print("\n=== 修复 integration_full.py ===")
with open("tests/integration_full.py", encoding="utf-8") as f:
    content = f.read()

for name, new_id in intg_ids.items():
    # 找到包含该名字的行，替换其中的ID
    pattern = r'("name":\s*"' + re.escape(name) + r'".*?"id_card":\s*")(\d{18})(")'
    match = re.search(pattern, content)
    if match:
        old_id = match.group(2)
        if old_id != new_id:
            content = content[:match.start(2)] + new_id + content[match.end(2):]
            print(f"  {name}: {old_id} → {new_id}")
        else:
            print(f"  {name}: {new_id} (已正确)")
    else:
        print(f"  {name}: 未找到!")

with open("tests/integration_full.py", "w", encoding="utf-8") as f:
    f.write(content)

# 修复 test_expiring_filter.py
print("\n=== 修复 test_expiring_filter.py ===")
with open("tests/test_expiring_filter.py", encoding="utf-8") as f:
    content = f.read()

for name, new_id in exp_ids.items():
    # 找到包含该名字的行，替换其中的ID
    pattern = r'("' + re.escape(name) + r'".*?"id_card":\s*")(\d{18})(")'
    match = re.search(pattern, content)
    if match:
        old_id = match.group(2)
        if old_id != new_id:
            content = content[:match.start(2)] + new_id + content[match.end(2):]
            print(f"  {name}: {old_id} → {new_id}")
        else:
            print(f"  {name}: {new_id} (已正确)")
    else:
        # 尝试另一种模式：名字在前面
        pattern2 = r'(_create_person\(.*?"' + re.escape(name) + r'".*?",\s*")(\d{18})(")'
        match2 = re.search(pattern2, content)
        if match2:
            old_id = match2.group(2)
            if old_id != new_id:
                content = content[:match2.start(2)] + new_id + content[match2.end(2):]
                print(f"  {name}: {old_id} → {new_id}")
            else:
                print(f"  {name}: {new_id} (已正确)")
        else:
            print(f"  {name}: 未找到!")

with open("tests/test_expiring_filter.py", "w", encoding="utf-8") as f:
    f.write(content)

# 检查 test_final.py 的3处替换
print("\n=== 检查 test_final.py ===")
with open("tests/test_final.py", encoding="utf-8") as f:
    content = f.read()
# test_final.py 使用 _next_id_card() 动态生成，少量硬编码ID
# 搜索硬编码的ID
for m in re.finditer(r'"(320102\d{12})"', content):
    old_id = m.group(1)
    id17 = old_id[:17]
    new_id = fix_checksum(id17)
    if old_id != new_id:
        print(f"  需修复: {old_id} → {new_id}")
        content = content.replace(f'"{old_id}"', f'"{new_id}"')
with open("tests/test_final.py", "w", encoding="utf-8") as f:
    f.write(content)
