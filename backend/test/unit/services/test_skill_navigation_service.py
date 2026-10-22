"""验证 Basic 共享技能导航的数据与权限边界。"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from yuxi.services.skill_navigation_service import (
    NavigationConfig,
    NavigationConflict,
    filter_navigation_for_role,
    get_skill_navigation,
    save_skill_navigation,
)

pytestmark = pytest.mark.unit


def node(node_id="entry", **values):
    """构造测试用导航节点。"""
    return {
        "id": node_id,
        "name": "入口",
        "skillSlug": "sample-skill",
        "children": [],
        "material": "材料",
        "result": "结果",
        "prompt": "处理材料",
        "visibleRoles": ["user", "admin", "superadmin"],
        **values,
    }


@pytest.mark.parametrize("bad", ["duplicate", "depth", "unknown_role", "extra"])
def test_navigation_config_rejects_invalid_tree(bad):
    """拒绝重复标识、超深树、未知角色和额外字段。"""
    entry = node()
    if bad == "duplicate":
        entry["children"] = [node()]
    elif bad == "depth":
        current = entry
        for node_id in ("two", "three", "four"):
            current["children"] = [node(node_id)]
            current = current["children"][0]
    elif bad == "unknown_role":
        entry["visibleRoles"] = ["inspector"]
    else:
        entry["workspace"] = "inspection"
    with pytest.raises(ValidationError):
        NavigationConfig.model_validate({"revision": 0, "tree": [entry]})


@pytest.mark.parametrize("skill_slug", [None, ""])
def test_group_skill_slug_normalizes_to_empty_string(skill_slug):
    """分组接受 UI 的空串或旧值 null，并统一输出空串。"""
    group = node(skillSlug=skill_slug, children=[node("child")])
    config = NavigationConfig.model_validate({"revision": 0, "tree": [group]})
    assert config.model_dump()["tree"][0]["skillSlug"] == ""


def test_role_and_skill_permission_filter_prunes_groups_and_preserves_order():
    """只有角色可见且包含可访问技能后代的分组才保留。"""
    tree = [
        node("group", skillSlug=None, children=[node("allowed"), node("denied", skillSlug="private")]),
        node(
            "restricted-parent",
            skillSlug="private",
            material="private material",
            result="private result",
            prompt="private prompt",
            children=[node("visible-descendant")],
        ),
        node("hidden-role", skillSlug=None, visibleRoles=["admin"], children=[node("role-child")]),
        node("private-only", skillSlug="private"),
    ]
    result = filter_navigation_for_role({"revision": 3, "tree": tree, "configured": True}, "user", {"sample-skill"})
    assert [item["id"] for item in result["tree"]] == ["group", "restricted-parent"]
    assert [item["id"] for item in result["tree"][0]["children"]] == ["allowed"]
    restricted_parent = result["tree"][1]
    assert restricted_parent["skillSlug"] == ""
    assert (restricted_parent["material"], restricted_parent["result"], restricted_parent["prompt"]) == ("", "", "")
    assert [item["id"] for item in restricted_parent["children"]] == ["visible-descendant"]


@pytest.mark.asyncio
async def test_unconfigured_and_explicit_empty_tree_are_distinct(monkeypatch):
    """缺少配置行与已保存空树返回不同 configured 状态。"""

    class Repository:
        value = None

        def __init__(self, db):
            pass

        async def read(self):
            return self.value

    monkeypatch.setattr("yuxi.services.skill_navigation_service.SkillNavigationRepository", Repository)
    assert await get_skill_navigation(object()) == {"revision": 0, "tree": [], "configured": False}
    Repository.value = {"revision": 4, "tree": []}
    assert await get_skill_navigation(object()) == {"revision": 4, "tree": [], "configured": True}


@pytest.mark.parametrize("defect", ["missing", "disabled", "personal", "inaccessible"])
@pytest.mark.asyncio
async def test_new_invalid_skill_binding_is_rejected(monkeypatch, defect):
    """新增绑定必须指向启用且当前管理员可访问的共享技能。"""

    class NavigationRepository:
        def __init__(self, db):
            del db

        async def read(self):
            return None

    class Skills:
        async def get_by_slug(self, slug):
            if defect == "missing":
                return None
            return SimpleNamespace(
                slug=slug,
                enabled=defect != "disabled",
                source_type="personal" if defect == "personal" else "managed",
                created_by="another-user",
                share_config={
                    "version": 2,
                    "read_scope": {
                        "access_level": "user" if defect == "inaccessible" else "global",
                        "department_ids": [],
                        "user_uids": ["different-user"] if defect == "inaccessible" else [],
                    },
                    "manage_scope": None,
                },
            )

    monkeypatch.setattr("yuxi.services.skill_navigation_service.SkillNavigationRepository", NavigationRepository)
    monkeypatch.setattr("yuxi.services.skill_navigation_service.SkillRepository", lambda db: Skills())
    user = SimpleNamespace(uid="admin-user", role="admin", department_id=1)
    with pytest.raises(ValueError, match="技能"):
        await save_skill_navigation(object(), NavigationConfig(revision=0, tree=[node()]), user)


@pytest.mark.asyncio
async def test_stale_revision_is_rejected_and_rolled_back(monkeypatch):
    """旧 revision 不覆盖现有配置并回滚当前事务。"""

    class NavigationRepository:
        def __init__(self, db):
            del db

        async def read(self):
            return {"revision": 2, "tree": []}

        async def save(self, tree, revision, uid):
            assert revision == 1
            return None

    class Database:
        rolled_back = False

        async def rollback(self):
            self.rolled_back = True

    monkeypatch.setattr("yuxi.services.skill_navigation_service.SkillNavigationRepository", NavigationRepository)
    db = Database()
    config = NavigationConfig(revision=1, tree=[])
    with pytest.raises(NavigationConflict):
        await save_skill_navigation(db, config, SimpleNamespace(uid="admin"))
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_unchanged_legacy_binding_can_be_kept(monkeypatch):
    """旧配置中的失效绑定可原样保留以便管理员逐步整理菜单。"""
    stored_tree = [node(skillSlug="retired-skill")]

    class NavigationRepository:
        def __init__(self, db):
            del db

        async def read(self):
            return {"revision": 3, "tree": stored_tree}

        async def save(self, tree, revision, uid):
            assert revision == 3
            return {"revision": 4, "tree": tree}

    class Skills:
        async def get_by_slug(self, slug):
            raise AssertionError("unchanged binding must not be revalidated")

    class Database:
        committed = False

        async def commit(self):
            self.committed = True

    monkeypatch.setattr("yuxi.services.skill_navigation_service.SkillNavigationRepository", NavigationRepository)
    monkeypatch.setattr("yuxi.services.skill_navigation_service.SkillRepository", lambda db: Skills())
    db = Database()
    config = NavigationConfig(revision=3, tree=stored_tree)

    result = await save_skill_navigation(db, config, SimpleNamespace(uid="admin"))

    assert result["revision"] == 4
    assert result["configured"] is True
    assert db.committed is True
