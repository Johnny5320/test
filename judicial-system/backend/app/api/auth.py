"""认证 API — 逻辑不变；HTTPException → BizError，裸返回 data"""
import logging

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.core.logging_config import log_call
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.common import BizError, ErrorCode, ok

logger = logging.getLogger("judicial.api.auth")

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse)
@log_call
def login(req: LoginRequest, session: Session = Depends(get_session)):
    """登录"""
    user = session.exec(select(User).where(User.username == req.username)).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise BizError(ErrorCode.UNAUTHORIZED, "用户名或密码错误")
    if not user.is_active:
        raise BizError(ErrorCode.ACCOUNT_DISABLED, "账号已禁用")

    return TokenResponse(
        access_token=create_access_token(data={"sub": user.username}),
        refresh_token=create_refresh_token(data={"sub": user.username}),
        force_change_password=user.force_change_password,
    )


@router.post("/refresh", response_model=TokenResponse)
@log_call
def refresh_token(req: RefreshRequest, session: Session = Depends(get_session)):
    """刷新Token"""
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise BizError(ErrorCode.UNAUTHORIZED, "无效的Refresh Token")

    username = payload.get("sub")
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not user.is_active:
        raise BizError(ErrorCode.UNAUTHORIZED, "用户不存在或已禁用")

    return TokenResponse(
        access_token=create_access_token(data={"sub": user.username}),
        refresh_token=create_refresh_token(data={"sub": user.username}),
        force_change_password=user.force_change_password,
    )


@router.get("/me", response_model=UserResponse)
@log_call
def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


@router.post("/change-password")
@log_call
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """修改密码"""
    if not verify_password(req.old_password, current_user.hashed_password):
        raise BizError(ErrorCode.WRONG_PASSWORD, "原密码错误")

    current_user.hashed_password = hash_password(req.new_password)
    current_user.force_change_password = False
    session.add(current_user)
    session.commit()
    return ok(message="密码修改成功")
