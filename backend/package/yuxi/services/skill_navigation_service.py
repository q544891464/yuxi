"""侧栏技能的受控配置与发布。"""

import json
from typing import Literal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from yuxi.agents.skills.repository import SkillRepository
from yuxi.permissions import ResourcePermission, resolve_skill_permission
from yuxi.repositories.skill_navigation_repository import SkillNavigationRepository


class NavigationNode(BaseModel):
    """可调用的业务入口；数组顺序即展示顺序。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    label: str = Field(min_length=1, max_length=60)
    skillSlug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=100)
    skillDisplayName: str = Field(min_length=1, max_length=60)
    inputHint: str = Field(min_length=1, max_length=2000)
    outputHint: str = Field(min_length=1, max_length=2000)
    presetPrompt: str = Field(min_length=1, max_length=10000)
    visibleRoles: list[Literal["user", "ducha", "admin", "superadmin"]] = Field(
        default_factory=lambda: ["user", "ducha", "admin", "superadmin"], max_length=4
    )
    children: list["NavigationNode"] = Field(default_factory=list, max_length=100)


class NavigationConfig(BaseModel):
    """限制树深度、总节点数和标识唯一性。"""

    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    nodes: list[NavigationNode] = Field(max_length=100)

    @model_validator(mode="after")
    def validate_tree(self):
        """拒绝歧义标识和无法展示的过深层级。"""
        seen = set()

        def visit(nodes, depth):
            for node in nodes:
                if depth > 3 or node.id in seen or len(seen) >= 100:
                    raise ValueError("最多 100 个入口、三级层级，入口标识不得重复")
                seen.add(node.id)
                visit(node.children, depth + 1)

        visit(self.nodes, 1)
        return self


class NavigationConflict(ValueError):
    """另一管理员已经保存新版本。"""


def filter_navigation_for_role(config, role):
    """父入口不可见时隐藏整个子树，保留可见入口的顺序。"""

    def visible(nodes):
        return [{**node, "children": visible(node["children"])} for node in nodes if role in node["visibleRoles"]]

    return {**config, "nodes": visible(config["nodes"])}


async def get_skill_navigation(db):
    """未配置时返回发行默认值；空配置保持为空。"""
    stored = await SkillNavigationRepository(db).read()
    if stored is None:
        path = Path(__file__).parents[1] / "config/static/skill_navigation.json"
        stored = {"revision": 0, "nodes": json.loads(path.read_text(encoding="utf-8"))}
    return NavigationConfig.model_validate(stored).model_dump()


async def save_skill_navigation(db, config, user):
    """校验新绑定权限并在提交后返回发布版本。"""
    existing = await get_skill_navigation(db)

    def bindings(nodes):
        return {n["id"]: n["skillSlug"] for n in nodes} | {
            id: slug for n in nodes for id, slug in bindings(n["children"]).items()
        }

    nodes = [node.model_dump() for node in config.nodes]
    # 仅原入口未改变的失效绑定允许保留；新增或改绑仍需校验。
    old_bindings = bindings(existing["nodes"])
    changed_slugs = {slug for id, slug in bindings(nodes).items() if old_bindings.get(id) != slug}
    for slug in changed_slugs:
        skill = await SkillRepository(db).get_by_slug(slug)
        if not skill or not skill.enabled or resolve_skill_permission(user, skill) == ResourcePermission.NONE:
            raise ValueError(f"技能 {slug} 不存在、未启用或无访问权限，请先安装为共享技能")
    result = await SkillNavigationRepository(db).save(nodes, config.revision, str(user.uid))
    if result is None:
        await db.rollback()
        raise NavigationConflict("配置已被其他管理员修改，请重新加载后编辑")
    await db.commit()
    return result
