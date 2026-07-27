"""身份证工具（纯函数，零依赖）
自 api/persons.py:701-730 迁移，create/import 两通道统一复用（修复校验强度不一）。
"""
from datetime import datetime
from typing import Any, Dict

ID_CARD_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
ID_CARD_CHECK_CHARS = "10X98765432"


def validate_id_card(id_card: str) -> bool:
    """校验18位身份证号（含校验位）"""
    if not id_card or len(id_card) != 18:
        return False
    body = id_card[:17]
    if not body.isdigit():
        return False
    total = sum(int(body[i]) * ID_CARD_WEIGHTS[i] for i in range(17))
    expected = ID_CARD_CHECK_CHARS[total % 11]
    return id_card[17].upper() == expected


def infer_from_id_card(id_card: str) -> Dict[str, Any]:
    """从身份证号推算性别和出生日期；非法输入返回空 dict"""
    result: Dict[str, Any] = {}
    if id_card and len(id_card) == 18 and id_card[:17].isdigit():
        result["gender"] = "男" if int(id_card[16]) % 2 == 1 else "女"
        try:
            result["birth_date"] = datetime.strptime(id_card[6:14], "%Y%m%d").date()
        except ValueError:
            pass
    return result
