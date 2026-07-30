"""一次性修复所有测试文件中的身份证号校验位（两遍替换，避免子串冲突）"""
import re, glob, uuid

ID_CARD_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
ID_CARD_CHECK_CHARS = "10X98765432"

def fix_checksum(id17: str) -> str:
    total = sum(int(id17[i]) * ID_CARD_WEIGHTS[i] for i in range(17))
    return id17 + ID_CARD_CHECK_CHARS[total % 11]

# 收集所有测试文件中出现的18位身份证号
all_ids = set()
for f in glob.glob("tests/*.py"):
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            for m in re.finditer(r'"(\d{17}[\dXx])"', line):
                all_ids.add(m.group(1))

# 构建替换映射
mapping = {}
for old_id in sorted(all_ids):
    id17 = old_id[:17]
    if not id17.isdigit():
        continue
    new_id = fix_checksum(id17)
    if new_id != old_id:
        mapping[old_id] = new_id

# 特殊处理小写x：找校验位为X的基值
mapping["32010219900101123x"] = "320102199001010070x"
mapping["32010219900101123X"] = "320102199001010070X"

print("=== 替换映射 ===")
for old, new in sorted(mapping.items()):
    print(f'  "{old}" → "{new}"')

# 两遍替换：先用唯一占位符，再替换为新值
test_dir = "tests"
placeholders = {}
for old_id in mapping:
    placeholders[old_id] = f"__IDPH_{uuid.uuid4().hex[:8]}__"

total_replaced = 0
for fname in sorted(glob.glob(f"{test_dir}/*.py")):
    with open(fname, encoding="utf-8") as f:
        content = f.read()

    original = content

    # 第一遍：旧ID → 占位符
    for old_id in mapping:
        content = content.replace(f'"{old_id}"', f'"{placeholders[old_id]}"')

    # 第二遍：占位符 → 新ID
    for old_id, new_id in mapping.items():
        content = content.replace(placeholders[old_id], new_id)

    if content != original:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(content)
        count = sum(original.count(f'"{old}"') for old in mapping)
        total_replaced += count
        print(f"  ✓ {fname}: {count} 处替换")
    else:
        print(f"  - {fname}: 无变更")

print(f"\n总计: {total_replaced} 处替换")
