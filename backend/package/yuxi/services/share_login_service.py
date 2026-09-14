"""用户分享登录链接的用例。"""

import hashlib
import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.repositories.share_login_link_repository import ShareLoginLinkRepository
from yuxi.services.operation_log_service import log_operation
from yuxi.storage.postgres.models_business import Department, ShareLoginLink, User
from yuxi.utils.auth_utils import AuthUtils
from yuxi.utils.datetime_utils import utc_now_naive


@dataclass
class ShareLoginError(Exception):
    """分享登录链接的公开失败语义。"""

    code: str
    message: str
    status_code: int


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _generate_key() -> str:
    return f"yxshare_{secrets.token_urlsafe(32)}"


def _assert_target_manageable(actor: User, target: User) -> None:
    if target.is_deleted:
        raise ShareLoginError("target_unavailable", "目标用户不存在", 404)
    if target.role != "user":
        raise ShareLoginError("target_forbidden", "只能为普通用户创建分享登录链接", 403)
    if actor.role != "superadmin" and actor.department_id != target.department_id:
        raise ShareLoginError("forbidden", "只能管理本部门用户", 403)


async def create_share_login_link(
    db: AsyncSession, *, actor: User, target_user_id: int, name: str | None
) -> tuple[ShareLoginLink, str]:
    """为可管理用户创建长期分享密钥，明文仅随本次响应返回。"""

    target = await db.scalar(select(User).where(User.id == target_user_id).with_for_update())
    if target is None:
        raise ShareLoginError("target_unavailable", "目标用户不存在", 404)
    _assert_target_manageable(actor, target)
    secret = _generate_key()
    link = await ShareLoginLinkRepository(db).create(
        key_hash=_hash_key(secret),
        user_id=target.id,
        created_by=actor.id,
        name=(name or "用户分享链接").strip()[:100] or "用户分享链接",
    )
    await log_operation(db, actor.id, "创建分享登录链接", f"为用户 {target.uid} 创建分享登录链接")
    await db.commit()
    await db.refresh(link)
    return link, secret


async def list_share_login_links(db: AsyncSession, *, actor: User, target_user_id: int) -> list[ShareLoginLink]:
    """列出管理员有权管理的用户分享链接。"""

    target = await db.scalar(select(User).where(User.id == target_user_id))
    if target is None:
        raise ShareLoginError("target_unavailable", "目标用户不存在", 404)
    _assert_target_manageable(actor, target)
    return await ShareLoginLinkRepository(db).list_for_user(target.id)


async def revoke_share_login_link(db: AsyncSession, *, actor: User, target_user_id: int, link_id: int) -> None:
    """撤销目标用户的指定分享链接。"""

    target = await db.scalar(select(User).where(User.id == target_user_id).with_for_update())
    if target is None:
        raise ShareLoginError("target_unavailable", "目标用户不存在", 404)
    _assert_target_manageable(actor, target)
    repository = ShareLoginLinkRepository(db)
    link = await repository.get_for_user(user_id=target.id, link_id=link_id, for_update=True)
    if link is None:
        raise ShareLoginError("not_found", "分享登录链接不存在", 404)
    await repository.revoke(link)
    await log_operation(db, actor.id, "撤销分享登录链接", f"撤销用户 {target.uid} 的分享登录链接")
    await db.commit()


async def exchange_share_login_key(db: AsyncSession, key: str) -> dict:
    """用有效链接交换为目标用户的常规短期浏览器会话。"""

    normalized_key = key.strip()
    if not normalized_key.startswith("yxshare_"):
        raise ShareLoginError("invalid_key", "分享登录链接无效", 401)
    repository = ShareLoginLinkRepository(db)
    candidate = await repository.get_by_key_hash(_hash_key(normalized_key))
    if candidate is None:
        raise ShareLoginError("invalid_key", "分享登录链接无效或已撤销", 401)
    # 先锁用户，再锁链接，与撤销流程保持一致，避免交换与撤销形成锁环。
    user = await db.scalar(select(User).where(User.id == candidate.user_id, User.is_deleted == 0).with_for_update())
    if user is None:
        raise ShareLoginError("invalid_key", "分享登录链接无效或已撤销", 401)
    link = await repository.get_for_user(user_id=user.id, link_id=candidate.id, for_update=True)
    if link is None or link.revoked_at is not None:
        raise ShareLoginError("invalid_key", "分享登录链接无效或已撤销", 401)
    if user.is_login_locked():
        raise ShareLoginError("account_locked", "账户当前被锁定", 423)
    link.last_used_at = utc_now_naive()
    await log_operation(db, user.id, "分享登录", "通过分享登录链接登录")
    await db.commit()
    department_name = await db.scalar(select(Department.name).where(Department.id == user.department_id))
    return {
        "access_token": AuthUtils.create_access_token({"sub": str(user.id)}),
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "uid": user.uid,
        "phone_number": user.phone_number,
        "avatar": user.avatar,
        "role": user.role,
        "department_id": user.department_id,
        "department_name": department_name,
    }
