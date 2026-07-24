"""应用配置"""
import sys
from pydantic_settings import BaseSettings
from pathlib import Path


def get_base_dir() -> Path:
    """获取应用根目录（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "安置帮教智能台账系统"
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-to-a-random-string-in-production"
    DATABASE_URL: str = "sqlite:///./data.db"

    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 文件上传
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 10

    # OCR
    OCR_ENGINE: str = "rapidocr"
    OCR_MAX_PAGES: int = 10
    OCR_SCALE: float = 1.5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# 确保上传目录存在（使用绝对路径）
BASE_DIR = get_base_dir()
upload_path = Path(settings.UPLOAD_DIR)
if not upload_path.is_absolute():
    upload_path = BASE_DIR / upload_path
upload_path.mkdir(parents=True, exist_ok=True)

# 修正 DATABASE_URL 为绝对路径
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///./"):
    db_path = Path(db_url.replace("sqlite:///./", ""))
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
    settings.DATABASE_URL = f"sqlite:///{db_path}"
