"""业务技能导航在 PostgreSQL 中的持久化边界。"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from yuxi.storage.postgres.models_business import ConfigOption

NAVIGATION_KEY = "skill_navigation"


class SkillNavigationRepository:
    """复用配置表，串行检查版本并保存整棵导航树。"""

    def __init__(self, db):
        self.db = db

    async def read(self):
        """返回已保存值，缺失由服务层提供默认菜单。"""
        row = await self.db.scalar(select(ConfigOption).where(ConfigOption.key == NAVIGATION_KEY))
        return row.value if row else None

    async def save(self, nodes, revision, uid):
        """锁住同一配置记录，拒绝旧版本覆盖。"""
        await self.db.execute(
            insert(ConfigOption)
            .values(
                key=NAVIGATION_KEY,
                name="侧栏技能",
                description="业务技能导航配置",
                params={"internal": True, "fields": []},
                value={"revision": 0, "nodes": []},
                created_by=uid,
            )
            .on_conflict_do_nothing(index_elements=[ConfigOption.key])
        )
        row = await self.db.scalar(select(ConfigOption).where(ConfigOption.key == NAVIGATION_KEY).with_for_update())
        if row.value["revision"] != revision:
            return None
        row.value = {"revision": revision + 1, "nodes": nodes}
        row.updated_by = uid
        await self.db.flush()
        return row.value
