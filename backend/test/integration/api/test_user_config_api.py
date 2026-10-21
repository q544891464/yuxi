from __future__ import annotations

import json
import os
import uuid

import asyncpg
import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

USER_CONFIG_PATH = "/api/user/config"


async def test_user_config_requires_auth(test_client):
    response = await test_client.get(USER_CONFIG_PATH)
    assert response.status_code == 401


async def test_user_config_round_trip(test_client, standard_user):
    headers = standard_user["headers"]

    initial_response = await test_client.get(USER_CONFIG_PATH, headers=headers)
    assert initial_response.status_code == 200, initial_response.text
    initial_payload = initial_response.json()
    assert initial_payload["enable_memory"] is False

    save_response = await test_client.put(USER_CONFIG_PATH, json={"enable_memory": True}, headers=headers)
    assert save_response.status_code == 200, save_response.text
    assert save_response.json()["enable_memory"] is True

    final_response = await test_client.get(USER_CONFIG_PATH, headers=headers)
    assert final_response.status_code == 200, final_response.text
    assert final_response.json()["enable_memory"] is True
    assert final_response.json()["default_agent_id"] is None


async def test_user_default_agent_requires_visible_main_agent_and_keeps_memory(test_client, standard_user):
    """偏好写入只接受当前用户可见的主智能体并保留未修改字段。"""
    uid = str(standard_user["user"]["uid"])
    headers = standard_user["headers"]
    suffix = uuid.uuid4().hex[:12]
    visible_slug = f"user-pref-{suffix}"
    hidden_slug = f"user-pref-hidden-{suffix}"
    subagent_slug = f"user-pref-subagent-{suffix}"
    deleted_slug = f"user-pref-deleted-{suffix}"
    conn = await asyncpg.connect(os.environ["POSTGRES_URL"].replace("+asyncpg", ""))
    slugs = [visible_slug, hidden_slug, subagent_slug, deleted_slug]

    def scope(uids: list[str]) -> dict:
        """构造绑定用户的 Agent 读取范围。"""
        return {
            "version": 2,
            "read_scope": {"access_level": "user", "department_ids": [], "user_uids": uids},
            "manage_scope": None,
        }

    try:
        for slug, is_subagent, user_uids in (
            (visible_slug, False, [uid]),
            (hidden_slug, False, ["basic-qa-admin"]),
            (subagent_slug, True, [uid]),
            (deleted_slug, False, [uid]),
        ):
            await conn.execute(
                "INSERT INTO agents (slug, backend_id, name, pics, config_json, share_config, is_default, is_subagent) "
                "VALUES ($1, $2, $3, '[]'::jsonb, $4::jsonb, $5::jsonb, FALSE, $6)",
                slug,
                "SubAgentBackend" if is_subagent else "ChatbotAgent",
                slug,
                json.dumps({"context": {}}),
                json.dumps(scope(user_uids)),
                is_subagent,
            )

        saved = await test_client.put(
            USER_CONFIG_PATH,
            json={"enable_memory": True, "default_agent_id": visible_slug},
            headers=headers,
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["default_agent_id"] == visible_slug
        persisted = await conn.fetchrow("SELECT enable_memory, default_agent_id FROM user_config WHERE uid = $1", uid)
        assert tuple(persisted) == (True, visible_slug)

        memory_only = await test_client.put(USER_CONFIG_PATH, json={"enable_memory": False}, headers=headers)
        assert memory_only.status_code == 200, memory_only.text
        assert memory_only.json()["default_agent_id"] == visible_slug
        assert memory_only.json()["enable_memory"] is False
        persisted = await conn.fetchrow("SELECT enable_memory, default_agent_id FROM user_config WHERE uid = $1", uid)
        assert tuple(persisted) == (False, visible_slug)

        visible_agents = await test_client.get("/api/agent", headers=headers)
        assert visible_agents.status_code == 200, visible_agents.text
        visible_slugs = {agent["slug"] for agent in visible_agents.json()["agents"]}
        assert visible_slug in visible_slugs
        assert hidden_slug not in visible_slugs
        assert subagent_slug not in visible_slugs
        hidden_detail = await test_client.get(f"/api/agent/{hidden_slug}", headers=headers)
        assert hidden_detail.status_code == 404, hidden_detail.text

        for invalid_slug in (hidden_slug, subagent_slug, f"missing-{suffix}"):
            rejected = await test_client.put(USER_CONFIG_PATH, json={"default_agent_id": invalid_slug}, headers=headers)
            assert rejected.status_code == 422, rejected.text

        hidden_run = await test_client.post(
            "/api/agent/runs",
            headers=headers,
            json={
                "query": "must not run",
                "agent_slug": hidden_slug,
                "thread_id": uuid.uuid4().hex,
                "meta": {"request_id": f"user-pref-hidden-run-{suffix}"},
            },
        )
        assert hidden_run.status_code == 404, hidden_run.text

        deleted_default = await test_client.put(
            USER_CONFIG_PATH, json={"default_agent_id": deleted_slug}, headers=headers
        )
        assert deleted_default.status_code == 200, deleted_default.text
        await conn.execute("DELETE FROM agents WHERE slug = $1", deleted_slug)
        deleted_read = await test_client.get(USER_CONFIG_PATH, headers=headers)
        assert deleted_read.status_code == 200, deleted_read.text
        assert deleted_read.json()["default_agent_id"] is None

        restored_default = await test_client.put(
            USER_CONFIG_PATH, json={"default_agent_id": visible_slug}, headers=headers
        )
        assert restored_default.status_code == 200, restored_default.text

        await conn.execute(
            "UPDATE agents SET share_config = $2::jsonb WHERE slug = $1",
            visible_slug,
            json.dumps(scope(["basic-qa-admin"])),
        )
        read = await test_client.get(USER_CONFIG_PATH, headers=headers)
        assert read.status_code == 200, read.text
        assert read.json()["default_agent_id"] is None
        assert read.json()["enable_memory"] is False

        clear = await test_client.put(USER_CONFIG_PATH, json={"default_agent_id": None}, headers=headers)
        assert clear.status_code == 200, clear.text
        assert clear.json()["default_agent_id"] is None
    finally:
        await conn.execute("DELETE FROM agents WHERE slug = ANY($1::varchar[])", slugs)
        await conn.close()
