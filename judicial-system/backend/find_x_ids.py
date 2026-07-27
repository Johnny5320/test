"""找一个前17位校验位为X的身份证号基值"""
ID_CARD_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
ID_CARD_CHECK_CHARS = "10X98765432"

def check_char(id17: str) -> str:
    total = sum(int(id17[i]) * ID_CARD_WEIGHTS[i] for i in range(17))
    return ID_CARD_CHECK_CHARS[total % 11]

# 搜索前缀 32010219900101 下找校验位为X的
prefix = "32010219900101"
for i in range(10000):
    id17 = f"{prefix}{i:04d}"
    if check_char(id17) == 'X':
        # 第17位是 i的最后一位
        last_digit = int(id17[16])
        gender = "男" if last_digit % 2 == 1 else "女"
        print(f"  {id17} → {id17}X  (第17位={last_digit}, {gender})")
        if last_digit % 2 == 1:  # 找奇数位(男)
            print(f"  ★ 推荐: {id17}x (小写测试)")
            break
