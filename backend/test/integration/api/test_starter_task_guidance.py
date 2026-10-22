"""首次任务读模型通过真实 HTTP 与持久员工配置核对。"""

import copy
import json
import os
import uuid

import asyncpg
import pytest

from yuxi.agents.presets.default_chatbot import PRESET as ASSISTANT
from yuxi.agents.presets.deep_research import PRESET as RESEARCH

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.mark.parametrize("preset", [ASSISTANT, RESEARCH])
async def test_starter_profile_tracks_persisted_role_without_changing_it(test_client, standard_user, preset):
    """普通用户读取预置及改写配置，接口投影不能反向修改持久事实。"""
    conn = await asyncpg.connect(os.environ["POSTGRES_URL"].replace("+asyncpg", ""))
    saved = await conn.fetchval("SELECT config_json FROM agents WHERE slug = $1", preset.slug)
    assert saved is not None, "隔离环境必须初始化预置员工"
    headers = standard_user["headers"]
    try:
        for context, expected in [
            (copy.deepcopy(preset.context), preset.slug),
            ({**preset.context, "system_prompt": "仅负责合成验收任务"}, None),
        ]:
            value = json.dumps({"context": context})
            await conn.execute("UPDATE agents SET config_json = $1::jsonb WHERE slug = $2", value, preset.slug)
            detail = await test_client.get(f"/api/agent/{preset.slug}", headers=headers)
            assert detail.status_code == 200, detail.text
            assert detail.json()["agent"]["starter_task_profile"] == expected
            listing = await test_client.get("/api/agent", headers=headers)
            assert listing.status_code == 200, listing.text
            row = next(item for item in listing.json()["agents"] if item["slug"] == preset.slug)
            assert row["starter_task_profile"] == expected
            persisted = json.loads(await conn.fetchval("SELECT config_json FROM agents WHERE slug = $1", preset.slug))
            assert persisted == {"context": context}
    finally:
        await conn.execute("UPDATE agents SET config_json = $1::jsonb WHERE slug = $2", saved, preset.slug)
        await conn.close()


async def test_same_name_custom_employee_has_no_examples_or_cross_user_visibility(
    test_client, admin_headers, standard_user
):
    """同名私有员工不继承预置示例，普通账号仍无法读取。"""
    slug = f"pytest-starter-{uuid.uuid4().hex[:10]}"
    try:
        created = await test_client.post(
            "/api/agent",
            headers=admin_headers,
            json={
                "slug": slug,
                "name": "深度研究",
                "backend_id": "ChatbotAgent",
                "config_json": {"context": RESEARCH.context},
            },
        )
        assert created.status_code == 200, created.text
        assert created.json()["agent"]["starter_task_profile"] is None
        hidden = await test_client.get(f"/api/agent/{slug}", headers=standard_user["headers"])
        assert hidden.status_code in {403, 404}, hidden.text
        listing = await test_client.get("/api/agent", headers=standard_user["headers"])
        assert all(item["slug"] != slug for item in listing.json()["agents"])
    finally:
        deleted = await test_client.delete(f"/api/agent/{slug}", headers=admin_headers)
        assert deleted.status_code in {200, 404}, deleted.text
