"""侧栏技能导航的配置表持久化边界。"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from yuxi.storage.postgres.models_business import ConfigOption

NAVIGATION_KEY = "skill_navigation"


class SkillNavigationRepository:
    """通过 ConfigOption 保存共享导航树。"""

    def __init__(self, db):
        self.db = db

    async def read(self):
        """返回配置值；缺行与显式空树保持可区分。"""
        row = await self.db.scalar(select(ConfigOption).where(ConfigOption.key == NAVIGATION_KEY))
        return row.value if row else None

    async def save(self, tree, revision, uid):
        """锁定配置行并按 revision 比较后保存。"""
        await self.db.execute(
            insert(ConfigOption)
            .values(
                key=NAVIGATION_KEY,
                name="侧栏技能",
                description="共享技能导航配置",
                params={"internal": True, "fields": []},
                value={"revision": 0, "tree": []},
                created_by=uid,
            )
            .on_conflict_do_nothing(index_elements=[ConfigOption.key])
        )
        row = await self.db.scalar(
            select(ConfigOption)
            .where(ConfigOption.key == NAVIGATION_KEY)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        current = row.value
        if current.get("revision") != revision:
            return None
        row.value = {"revision": revision + 1, "tree": tree}
        row.updated_by = uid
        await self.db.flush()
        return row.value
