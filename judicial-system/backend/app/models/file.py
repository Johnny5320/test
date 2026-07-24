"""附件/扫描件模型"""
from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone


class File(SQLModel, table=True):
    __tablename__ = "files"

    id: Optional[int] = Field(default=None, primary_key=True)
    person_id: int = Field(foreign_key="persons.id", index=True)
    file_type: str = Field(max_length=50)        # 类型：身份证/判决书/释放证明/帮教协议/走访照片
    file_path: str = Field(max_length=500)       # 存储路径
    original_name: Optional[str] = Field(default=None, max_length=200)  # 原始文件名
    ocr_raw_text: Optional[str] = Field(default=None, max_length=10000)  # OCR原始识别结果
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
