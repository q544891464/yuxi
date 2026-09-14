"""分享登录链接的数据访问边界。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_business import ShareLoginLink
from yuxi.utils.datetime_utils import utc_now_naive


class ShareLoginLinkRepository:
    """读写分享登录链接事实。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, key_hash: str, user_id: int, created_by: int, name: str) -> ShareLoginLink:
        """创建链接；明文密钥不进入持久化对象。"""

        link = ShareLoginLink(key_hash=key_hash, user_id=user_id, created_by=created_by, name=name)
        self.db.add(link)
        await self.db.flush()
        await self.db.refresh(link)
        return link

    async def list_for_user(self, user_id: int) -> list[ShareLoginLink]:
        """返回目标用户所有链接，包括已撤销记录。"""

        result = await self.db.execute(
            select(ShareLoginLink).where(ShareLoginLink.user_id == user_id).order_by(ShareLoginLink.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_user(self, *, user_id: int, link_id: int, for_update: bool = False) -> ShareLoginLink | None:
        """读取指定目标用户的链接。"""

        statement = select(ShareLoginLink).where(ShareLoginLink.id == link_id, ShareLoginLink.user_id == user_id)
        if for_update:
            statement = statement.with_for_update()
        return await self.db.scalar(statement)

    async def get_by_key_hash(self, key_hash: str) -> ShareLoginLink | None:
        """按哈希读取候选链接；后续必须按用户顺序加锁后再次确认。"""

        return await self.db.scalar(select(ShareLoginLink).where(ShareLoginLink.key_hash == key_hash))

    async def revoke(self, link: ShareLoginLink) -> None:
        """撤销链接并保留审计 tombstone。"""

        if link.revoked_at is None:
            link.revoked_at = utc_now_naive()
            await self.db.flush()
