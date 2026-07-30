"""认证 API — 登录用姓名；管理员可新增用户/重置密码"""
import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.deps import get_current_user, require_role
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
    AdminResetPasswordRequest,
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UpdateUserRequest,
    UserResponse,
)
from app.schemas.common import BizError, ErrorCode, ok

logger = logging.getLogger("judicial.api.auth")

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse)
@log_call
def login(req: LoginRequest, session: Session = Depends(get_session)):
    """登录（用姓名 + 密码）"""
    user = session.exec(select(User).where(User.real_name == req.real_name)).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise BizError(ErrorCode.UNAUTHORIZED, "姓名或密码错误")
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
    """修改自己的密码"""
    if not verify_password(req.old_password, current_user.hashed_password):
        raise BizError(ErrorCode.WRONG_PASSWORD, "原密码错误")

    current_user.hashed_password = hash_password(req.new_password)
    current_user.force_change_password = False
    session.add(current_user)
    session.commit()
    return ok(message="密码修改成功")


# ---- 管理员接口 ----

@router.get("/users", response_model=List[UserResponse])
@log_call
def list_users(
    current_user: User = Depends(require_role("director")),
    session: Session = Depends(get_session),
):
    """管理员：查看所有用户"""
    users = session.exec(select(User)).all()
    return users


@router.post("/users")
@log_call
def create_user(
    req: CreateUserRequest,
    current_user: User = Depends(require_role("director")),
    session: Session = Depends(get_session),
):
    """管理员：新增用户"""
    # 检查姓名是否重复
    existing = session.exec(select(User).where(User.real_name == req.real_name)).first()
    if existing:
        raise BizError(ErrorCode.VALIDATION_ERROR, "该姓名已存在")

    # 生成用户名（姓名拼音首字母或姓名本身）
    username = req.real_name

    user = User(
        username=username,
        hashed_password=hash_password(req.password),
        real_name=req.real_name,
        role=req.role,
        force_change_password=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return ok(UserResponse.model_validate(user).model_dump(), "用户创建成功")


@router.post("/admin-reset-password")
@log_call
def admin_reset_password(
    req: AdminResetPasswordRequest,
    current_user: User = Depends(require_role("director")),
    session: Session = Depends(get_session),
):
    """管理员：重置用户密码"""
    user = session.get(User, req.user_id)
    if not user:
        raise BizError(ErrorCode.PERSON_NOT_FOUND, "用户不存在")

    user.hashed_password = hash_password(req.new_password)
    user.force_change_password = True  # 重置后强制改密
    session.add(user)
    session.commit()
    return ok(message=f"已重置 {user.real_name} 的密码")


@router.patch("/users/{user_id}")
@log_call
def update_user(
    user_id: int,
    req: UpdateUserRequest,
    current_user: User = Depends(require_role("director")),
    session: Session = Depends(get_session),
):
    """管理员：编辑用户（姓名/角色/启用状态）"""
    user = session.get(User, user_id)
    if not user:
        raise BizError(ErrorCode.PERSON_NOT_FOUND, "用户不存在")
    if user.id == current_user.id and req.is_active is False:
        raise BizError(ErrorCode.VALIDATION_ERROR, "不能禁用自己")
    changes = req.model_dump(exclude_unset=True)
    if "real_name" in changes:
        existing = session.exec(
            select(User).where(User.real_name == changes["real_name"], User.id != user_id)
        ).first()
        if existing:
            raise BizError(ErrorCode.VALIDATION_ERROR, "该姓名已存在")
        user.real_name = changes["real_name"]
        user.username = changes["real_name"]
    if "role" in changes:
        user.role = changes["role"]
    if "is_active" in changes:
        user.is_active = changes["is_active"]
    session.add(user)
    session.commit()
    session.refresh(user)
    return ok(UserResponse.model_validate(user).model_dump(), "更新成功")


@router.delete("/users/{user_id}")
@log_call
def delete_user(
    user_id: int,
    current_user: User = Depends(require_role("director")),
    session: Session = Depends(get_session),
):
    """管理员：删除用户"""
    user = session.get(User, user_id)
    if not user:
        raise BizError(ErrorCode.PERSON_NOT_FOUND, "用户不存在")
    if user.id == current_user.id:
        raise BizError(ErrorCode.VALIDATION_ERROR, "不能删除自己")
    session.delete(user)
    session.commit()
    return ok(None, "用户已删除")
