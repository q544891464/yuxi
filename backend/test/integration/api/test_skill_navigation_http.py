"""侧栏技能导航的真实 HTTP 与 PostgreSQL 集成证据。"""

from __future__ import annotations

import copy
import os
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.agents.skills.service import delete_personal_skill, install_personal_skill_dir
from yuxi.repositories.skill_navigation_repository import SkillNavigationRepository
from yuxi.storage.postgres.models_business import ConfigOption, Skill

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest_asyncio.fixture
async def skill_navigation_context(
    test_client,
    admin_headers: dict[str, str],
    standard_user: dict,
    tmp_path: Path,
) -> AsyncGenerator[dict, None]:
    """在测试 PostgreSQL 中建立唯一技能数据并恢复原导航配置。"""
    admin_profile = await test_client.get("/api/auth/me", headers=admin_headers)
    assert admin_profile.status_code == 200, admin_profile.text
    admin_uid = admin_profile.json()["uid"]
    user_uid = standard_user["user"]["uid"]
    suffix = uuid.uuid4().hex
    accessible_slug = f"pytest-nav-{suffix}"
    inaccessible_slug = f"pytest-nav-private-{suffix}"
    personal_slug = f"pytest-nav-personal-{suffix}"
    other_uid = f"pytest-no-user-{suffix}"
    engine = create_async_engine(os.environ["POSTGRES_URL"], pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    saved_option: dict | None = None
    skill_ids: list[int] = []
    personal_installed = False
    try:
        async with session_factory() as db:
            existing = await db.scalar(select(ConfigOption).where(ConfigOption.key == "skill_navigation"))
            if existing is not None:
                saved_option = {
                    column.name: copy.deepcopy(getattr(existing, column.name))
                    for column in ConfigOption.__table__.columns
                }
                await db.delete(existing)

            shared_skill = Skill(
                slug=accessible_slug,
                name="Navigation fixture skill",
                description="Global shared skill for navigation integration tests",
                source_type="upload",
                tool_dependencies=[],
                mcp_dependencies=[],
                skill_dependencies=[],
                dir_path=f"shared/{accessible_slug}",
                share_config={
                    "version": 2,
                    "read_scope": {"access_level": "global", "department_ids": [], "user_uids": []},
                    "manage_scope": None,
                },
                enabled=True,
                created_by=admin_uid,
            )
            private_skill = Skill(
                slug=inaccessible_slug,
                name="Private navigation fixture skill",
                description="User-scoped shared skill for navigation integration tests",
                source_type="upload",
                tool_dependencies=[],
                mcp_dependencies=[],
                skill_dependencies=[],
                dir_path=f"shared/{inaccessible_slug}",
                share_config={
                    "version": 2,
                    "read_scope": {"access_level": "user", "department_ids": [], "user_uids": [other_uid]},
                    "manage_scope": None,
                },
                enabled=True,
                created_by=admin_uid,
            )
            db.add_all([shared_skill, private_skill])
            await db.commit()
            skill_ids = [shared_skill.id, private_skill.id]

        personal_source = tmp_path / "personal-skill"
        personal_source.mkdir()
        (personal_source / "SKILL.md").write_text(
            f"---\nname: Personal navigation fixture\nslug: {personal_slug}\ndescription: fixture skill\n---\n"
            "Only used to prove personal skills cannot appear in the shared menu.\n",
            encoding="utf-8",
        )
        await install_personal_skill_dir(user_uid, personal_source, expected_slug=personal_slug)
        personal_installed = True

        yield {
            "admin_uid": admin_uid,
            "accessible_slug": accessible_slug,
            "inaccessible_slug": inaccessible_slug,
            "personal_slug": personal_slug,
            "other_uid": other_uid,
            "user_headers": standard_user["headers"],
            "session_factory": session_factory,
        }
    finally:
        if personal_installed:
            await delete_personal_skill(user_uid, personal_slug)
        async with session_factory() as db:
            await db.execute(delete(Skill).where(Skill.id.in_(skill_ids)))
            current = await db.scalar(select(ConfigOption).where(ConfigOption.key == "skill_navigation"))
            if current is not None:
                await db.delete(current)
            if saved_option is not None:
                db.add(ConfigOption(**saved_option))
            await db.commit()
        await engine.dispose()


def _entry(node_id: str, skill_slug: str, *, visible_roles: list[str] | None = None) -> dict:
    """构造导航绑定节点请求体。"""
    return {
        "id": node_id,
        "name": node_id,
        "skillSlug": skill_slug,
        "children": [],
        "material": "测试材料",
        "result": "测试结果",
        "prompt": "处理测试材料",
        "visibleRoles": visible_roles or ["user", "admin", "superadmin"],
    }


async def test_admin_put_round_trips_to_get_and_config_option_and_rejects_stale_revision(
    test_client,
    admin_headers,
    skill_navigation_context,
):
    """真实管理员 PUT 后由 HTTP 与数据库回读确认提交，并拒绝旧 revision。"""
    context = skill_navigation_context
    payload = {
        "revision": 0,
        "tree": [
            {
                "id": "group",
                "name": "Group with an empty binding",
                "skillSlug": "",
                "children": [_entry("accessible", context["accessible_slug"])],
                "material": "",
                "result": "",
                "prompt": "",
                "visibleRoles": ["user", "admin", "superadmin"],
            }
        ],
    }

    response = await test_client.put("/api/system/skill-navigation", json=payload, headers=admin_headers)

    assert response.status_code == 200, response.text
    expected = {**payload, "revision": 1, "configured": True}
    assert response.json() == expected
    manage_response = await test_client.get("/api/system/skill-navigation/manage", headers=admin_headers)
    assert manage_response.status_code == 200, manage_response.text
    assert manage_response.json() == expected
    async with context["session_factory"]() as db:
        stored = await db.scalar(select(ConfigOption.value).where(ConfigOption.key == "skill_navigation"))
    assert stored == {"revision": 1, "tree": payload["tree"]}

    stale_response = await test_client.put(
        "/api/system/skill-navigation",
        json={"revision": 0, "tree": []},
        headers=admin_headers,
    )
    assert stale_response.status_code == 409, stale_response.text
    async with context["session_factory"]() as db:
        after_stale = await db.scalar(select(ConfigOption.value).where(ConfigOption.key == "skill_navigation"))
    assert after_stale == stored


async def test_ordinary_get_prunes_personal_inaccessible_and_role_hidden_bindings(
    test_client,
    admin_headers,
    skill_navigation_context,
):
    """普通 GET 仅返回可访问共享技能，并裁掉无后代分组和角色隐藏子树。"""
    context = skill_navigation_context
    tree = [
        {
            "id": "shared-group",
            "name": "共享分组",
            "children": [
                _entry("accessible", context["accessible_slug"]),
                _entry("inaccessible", context["inaccessible_slug"]),
            ],
            "visibleRoles": ["user", "admin", "superadmin"],
        },
        _entry("personal", context["personal_slug"]),
        {
            "id": "admin-only-group",
            "name": "管理员分组",
            "children": [_entry("admin-only-child", context["accessible_slug"])],
            "visibleRoles": ["admin", "superadmin"],
        },
        {
            "id": "empty-after-prune",
            "name": "仅含不可访问技能的分组",
            "children": [_entry("private-child", context["inaccessible_slug"])],
            "visibleRoles": ["user", "admin", "superadmin"],
        },
    ]
    async with context["session_factory"]() as db:
        option = ConfigOption(
            key="skill_navigation",
            name="侧栏技能",
            description="测试隔离导航配置",
            params={"internal": True, "fields": []},
            value={"revision": 7, "tree": tree},
            created_by=context["admin_uid"],
        )
        db.add(option)
        await db.commit()

    response = await test_client.get("/api/system/skill-navigation", headers=context["user_headers"])

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["configured"] is True
    assert payload["revision"] == 7
    assert [node["id"] for node in payload["tree"]] == ["shared-group"]
    assert [node["id"] for node in payload["tree"][0]["children"]] == ["accessible"]


async def test_ordinary_put_is_denied_without_changing_stored_option(
    test_client,
    admin_headers,
    skill_navigation_context,
):
    """普通用户 PUT 被真实认证依赖拒绝，且数据库配置保持不变。"""
    context = skill_navigation_context
    seed = {
        "revision": 5,
        "tree": [_entry("existing", context["accessible_slug"])],
    }
    async with context["session_factory"]() as db:
        db.add(
            ConfigOption(
                key="skill_navigation",
                name="侧栏技能",
                description="测试隔离导航配置",
                params={"internal": True, "fields": []},
                value=seed,
                created_by=context["admin_uid"],
            )
        )
        await db.commit()

    denied = await test_client.put(
        "/api/system/skill-navigation",
        json={"revision": 5, "tree": []},
        headers=context["user_headers"],
    )
    assert denied.status_code == 403, denied.text
    async with context["session_factory"]() as db:
        stored = await db.scalar(select(ConfigOption.value).where(ConfigOption.key == "skill_navigation"))
    assert stored == seed


async def test_cas_refreshes_stale_identity_map_between_two_sessions(skill_navigation_context):
    """session A 预读后，session B 的提交必须使 A 的旧 revision CAS 失败。"""
    context = skill_navigation_context
    session_a = context["session_factory"]()
    session_b = context["session_factory"]()
    tree_from_b = [{"id": "committed-by-b"}]
    tree_from_stale_a = [{"id": "stale-write-from-a"}]
    try:
        session_a.add(
            ConfigOption(
                key="skill_navigation",
                name="侧栏技能",
                description="CAS identity map integration fixture",
                params={"internal": True, "fields": []},
                value={"revision": 0, "tree": []},
                created_by=context["admin_uid"],
            )
        )
        await session_a.commit()

        first_read = await SkillNavigationRepository(session_a).read()
        assert first_read == {"revision": 0, "tree": []}
        committed_by_b = await SkillNavigationRepository(session_b).save(tree_from_b, 0, context["admin_uid"])
        assert committed_by_b == {"revision": 1, "tree": tree_from_b}
        await session_b.commit()

        stale_write = await SkillNavigationRepository(session_a).save(tree_from_stale_a, 0, context["admin_uid"])
        assert stale_write is None
        await session_a.rollback()

        async with context["session_factory"]() as verifier:
            stored = await verifier.scalar(select(ConfigOption.value).where(ConfigOption.key == "skill_navigation"))
        assert stored == {"revision": 1, "tree": tree_from_b}
    finally:
        await session_a.close()
        await session_b.close()
