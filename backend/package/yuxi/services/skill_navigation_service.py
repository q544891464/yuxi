"""校验、保存并按权限裁剪共享侧栏技能导航。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from yuxi.agents.skills.repository import SkillRepository
from yuxi.agents.skills.service import list_accessible_shared_skills
from yuxi.permissions import ResourcePermission, resolve_skill_permission
from yuxi.repositories.skill_navigation_repository import SkillNavigationRepository

ROLES = ("user", "admin", "superadmin")


class NavigationNode(BaseModel):
    """描述一个分组或绑定共享技能的导航入口。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=80)
    skillSlug: str = Field(default="", pattern=r"^(?:[a-z0-9]+(-[a-z0-9]+)*)?$", max_length=100)
    children: list["NavigationNode"] = Field(default_factory=list, max_length=100)
    material: str = Field(default="", max_length=2000)
    result: str = Field(default="", max_length=2000)
    prompt: str = Field(default="", max_length=10000)
    visibleRoles: list[Literal["user", "admin", "superadmin"]] = Field(default_factory=lambda: list(ROLES))

    @field_validator("skillSlug", mode="before")
    @classmethod
    def normalize_empty_skill_slug(cls, value):
        """把空绑定统一保存为 API 契约使用的空串。"""
        return "" if value is None else value


class NavigationConfig(BaseModel):
    """校验 revision 与树内节点标识。"""

    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    tree: list[NavigationNode] = Field(max_length=100)

    @model_validator(mode="after")
    def validate_tree(self):
        """拒绝重复标识、过深层级和过大的导航树。"""
        seen: set[str] = set()
        count = 0

        def visit(nodes, depth):
            """递归统计节点并检查层级与唯一标识。"""
            nonlocal count
            for node in nodes:
                count += 1
                if depth > 3 or node.id in seen or count > 100:
                    raise ValueError("最多 100 个入口、三级层级，入口标识不得重复")
                seen.add(node.id)
                visit(node.children, depth + 1)

        visit(self.tree, 1)
        return self


class NavigationConflict(ValueError):
    """导航版本已被其他管理员更新。"""


async def get_skill_navigation(db):
    """读取配置并区分未配置与显式空树。"""
    stored = await SkillNavigationRepository(db).read()
    if stored is None:
        return {"revision": 0, "tree": [], "configured": False}
    config = NavigationConfig.model_validate(stored)
    return {"revision": config.revision, "tree": config.model_dump()["tree"], "configured": True}


def filter_navigation_for_role(config, role, accessible_slugs):
    """按角色及共享技能权限递归裁剪导航树。"""

    def filter_nodes(nodes):
        """保留可见技能入口和仍有可见后代的分组。"""
        visible = []
        for node in nodes:
            if role not in node["visibleRoles"]:
                continue
            children = filter_nodes(node["children"])
            skill_visible = node["skillSlug"] in accessible_slugs if node["skillSlug"] else False
            if skill_visible or children:
                filtered = {**node, "children": children}
                if node["skillSlug"] and not skill_visible:
                    filtered.update(skillSlug="", material="", result="", prompt="")
                visible.append(filtered)
        return visible

    return {**config, "tree": filter_nodes(config["tree"])}


async def get_accessible_skill_navigation(db, user):
    """返回当前用户可调用共享技能对应的菜单节点。"""
    config = await get_skill_navigation(db)
    skills = await list_accessible_shared_skills(db, user)
    slugs = {skill.slug for skill in skills}
    return filter_navigation_for_role(config, user.role, slugs)


async def save_skill_navigation(db, config, user):
    """校验新增绑定并以 revision CAS 发布整棵菜单。"""
    existing = await get_skill_navigation(db)

    def bindings(nodes):
        """收集节点标识到共享技能 slug 的绑定。"""
        result = {}
        for node in nodes:
            if node["skillSlug"]:
                result[node["id"]] = node["skillSlug"]
            result.update(bindings(node["children"]))
        return result

    tree = [node.model_dump() for node in config.tree]
    old_bindings = bindings(existing["tree"])
    changed_slugs = {slug for node_id, slug in bindings(tree).items() if old_bindings.get(node_id) != slug}
    repo = SkillRepository(db)
    for slug in changed_slugs:
        skill = await repo.get_by_slug(slug)
        if (
            not skill
            or not skill.enabled
            or skill.source_type == "personal"
            or resolve_skill_permission(user, skill) == ResourcePermission.NONE
        ):
            raise ValueError(f"技能 {slug} 不存在、未启用、不是共享技能或当前管理员无访问权限")

    result = await SkillNavigationRepository(db).save(tree, config.revision, str(user.uid))
    if result is None:
        await db.rollback()
        raise NavigationConflict("配置已被其他管理员修改，请重新加载后编辑")
    await db.commit()
    return {**result, "configured": True}
