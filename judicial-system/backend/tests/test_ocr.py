"""OCR 字段提取测试"""
import pytest
from app.api.ocr import extract_fields


def test_extract_id_card():
    """提取身份证号"""
    ocr_results = [
        ([], "姓名 张三", 0.95),
        ([], "身份证号 320102199001011234", 0.98),
        ([], "住址 南京市玄武区XX路100号", 0.90),
    ]
    fields = extract_fields(ocr_results)
    assert fields["id_card"] == "320102199001011234"
    assert fields["gender"] == "男"
    assert fields["birth_date"] == "1990-01-01"


def test_extract_id_card_female():
    """提取身份证号 — 女性（末尾第2位偶数）"""
    ocr_results = [([], "身份证号码320102199502021246", 0.98)]
    fields = extract_fields(ocr_results)
    assert fields.get("id_card") == "320102199502021246"
    assert fields["gender"] == "女"


def test_extract_name():
    """提取姓名"""
    ocr_results = [([], "姓名：李四", 0.95)]
    fields = extract_fields(ocr_results)
    assert fields["name"] == "李四"


def test_extract_phone():
    """提取电话"""
    ocr_results = [([], "联系电话 13800138000", 0.95)]
    fields = extract_fields(ocr_results)
    assert fields["phone"] == "13800138000"


def test_extract_crime():
    """提取罪名"""
    ocr_results = [([], "被告人犯盗窃罪，判处有期徒刑三年", 0.95)]
    fields = extract_fields(ocr_results)
    assert fields["original_crime"] == "盗窃罪"


def test_extract_sentence():
    """提取刑期"""
    ocr_results = [([], "判处有期徒刑三年六个月", 0.95)]
    fields = extract_fields(ocr_results)
    assert "original_sentence" in fields


def test_extract_dates():
    """提取日期"""
    ocr_results = [([], "释放日期 2025年6月15日", 0.95)]
    fields = extract_fields(ocr_results)
    assert "2025-06-15" in fields.get("dates_found", [])


def test_extract_empty():
    """空结果"""
    fields = extract_fields([])
    assert "id_card" not in fields


def test_extract_full_document():
    """完整文书提取"""
    ocr_results = [
        ([], "罪犯姓名：王五", 0.95),
        ([], "身份证号码320102198803031236", 0.98),
        ([], "住址南京市鼓楼区XX街50号", 0.90),
        ([], "罪名：诈骗罪", 0.95),
        ([], "判处有期徒刑二年六个月", 0.95),
        ([], "2025年3月10日释放", 0.90),
    ]
    fields = extract_fields(ocr_results)
    assert fields["name"] == "王五"
    assert fields.get("id_card") == "320102198803031236"
    assert fields["gender"] == "男"
    assert fields["original_crime"] == "诈骗罪"
    assert "2025-03-10" in fields["dates_found"]
