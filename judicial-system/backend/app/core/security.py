"""JWT Token 工具"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.core.config import settings

import logging
from app.core.logging_config import log_call
logger = logging.getLogger("judicial.core.security")

ALGORITHM = "HS256"


@log_call
def hash_password(password: str) -> str:
    logger.debug("哈希密码（不记录明文）")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@log_call
def verify_password(plain_password: str, hashed_password: str) -> bool:
    ok = bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    logger.debug("密码校验结果: %s", "通过" if ok else "失败")
    return ok


@log_call
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    logger.info("签发 access token: sub=%s", data.get("sub"))
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


@log_call
def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    logger.info("签发 refresh token: sub=%s", data.get("sub"))
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


@log_call
def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        logger.debug("token 解码成功: sub=%s type=%s", payload.get("sub"), payload.get("type"))
        return payload
    except JWTError:
        logger.debug("token 解码失败（无效或过期）")
        return None
