"""角色页面访问在 PostgreSQL 中的持久化边界。"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from yuxi.storage.postgres.models_business import ConfigOption

PAGE_ACCESS_KEY = "role_page_access"


class PageAccessRepository:
    """复用配置表，串行检查版本并保存角色规则。"""

    def __init__(self, db):
        self.db = db

    async def read(self):
        """返回已保存值，缺失由服务层提供默认规则。"""
        row = await self.db.scalar(select(ConfigOption).where(ConfigOption.key == PAGE_ACCESS_KEY))
        return row.value if row else None

    async def save(self, rules, revision, uid):
        """锁住同一配置记录，拒绝旧版本覆盖。"""
        await self.db.execute(
            insert(ConfigOption)
            .values(
                key=PAGE_ACCESS_KEY,
                name="角色页面权限",
                description="角色页面访问配置",
                params={"internal": True, "fields": []},
                value={"revision": 0, "rules": {}},
                created_by=uid,
            )
            .on_conflict_do_nothing(index_elements=[ConfigOption.key])
        )
        row = await self.db.scalar(select(ConfigOption).where(ConfigOption.key == PAGE_ACCESS_KEY).with_for_update())
        if row.value["revision"] != revision:
            return None
        row.value = {"revision": revision + 1, "rules": rules}
        row.updated_by = uid
        await self.db.flush()
        return row.value
