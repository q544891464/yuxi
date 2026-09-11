"""通过真实 HTTP、worker、SSE 与 PostgreSQL 验证专业子任务交付。"""

import asyncio
import json
import os
import uuid

import asyncpg
import pytest

from e2e_helpers import RUN_TIMEOUT_SECONDS, delete_agent, iter_sse, postgres_dsn, wait_for_run
from test.live_api_cleanup import make_test_conversation_metadata, make_test_conversation_title
from yuxi.agents.buildin.evidence_review.schema import FactEvidenceReviewResult


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_main_agent_receives_evidence_review_from_own_child_run(e2e_client, e2e_headers):
    """无证据合成案件由真实主 Agent 调度，最终结果绑定正确子 Run。"""
    model = os.getenv("EVIDENCE_REVIEW_E2E_MODEL")
    if not model:
        pytest.skip("未配置真实调度模型 EVIDENCE_REVIEW_E2E_MODEL")
    client, headers = e2e_client, e2e_headers
    suffix = uuid.uuid4().hex[:8]
    slug = f"e2e-evidence-main-{suffix}"
    thread_id = None
    me = (await client.get("/api/auth/me", headers=headers)).json()
    assert me["role"] in {"admin", "superadmin"}
    case_input = {
        "case_json": {
            "violations": [
                {
                    "violation_id": "V1",
                    "behavior": "合成收入事项",
                    "fact_summary": f"合成案件 {suffix}：企业收入100万元。",
                    "evidence_ids": [],
                }
            ],
            "evidence": [],
        }
    }
    response = await client.post(
        "/api/agent",
        headers=headers,
        json={
            "name": f"E2E 事实证据调度 {suffix}",
            "slug": slug,
            "backend_id": "ChatbotAgent",
            "config_json": {
                "context": {
                    "model": model,
                    "tools": [],
                    "knowledges": [],
                    "skills": [],
                    "mcps": [],
                    "subagents": ["evidence-review"],
                    "system_prompt": (
                        "你是测试调度主智能体。必须调用一次 task，subagent_slug=evidence-review，"
                        "description 为用户提供的完整 JSON 字符串。不得自行审查。"
                        "调用后根据子任务结果简述证据状态。不要调用其他工具。"
                    ),
                }
            },
            "share_config": {
                "version": 2,
                "read_scope": {"access_level": "user", "user_uids": [me["uid"]], "department_ids": []},
                "manage_scope": None,
            },
        },
    )
    assert response.status_code == 200, response.text
    try:
        response = await client.post(
            "/api/chat/thread",
            headers=headers,
            json={
                "agent_id": slug,
                "title": make_test_conversation_title("evidence-review-e2e"),
                "metadata": make_test_conversation_metadata("evidence-review-e2e", e2e=True),
            },
        )
        assert response.status_code == 200, response.text
        thread_id = response.json()["id"]
        response = await client.post(
            "/api/agent/runs",
            headers=headers,
            json={
                "agent_slug": slug,
                "thread_id": thread_id,
                "model_spec": model,
                "tool_approval_mode": "always_trust",
                "query": json.dumps(case_input, ensure_ascii=False),
                "meta": {"request_id": f"evidence-{suffix}"},
            },
        )
        assert response.status_code == 200, response.text
        run_id = response.json()["run_id"]
        events = []
        async with asyncio.timeout(RUN_TIMEOUT_SECONDS):
            async for event, payload in iter_sse(client, headers, run_id):
                assert payload["run_id"] == run_id
                events.append((event, payload))
                if event == "end":
                    break
        assert any(event == "messages" for event, _ in events), "缺少真实消息事件"
        assert events[-1][0] == "end", "事件流未完整交付终态"
        assert events[-1][1]["payload"]["status"] == "completed"
        parent = await wait_for_run(client, headers, run_id)
        assert parent["status"] == "completed", parent
        assert events[-1][1]["request_id"] == parent["request_id"]
        conn = await asyncpg.connect(postgres_dsn())
        try:
            children = await conn.fetch(
                """SELECT r.id, r.status, r.request_id, r.conversation_thread_id,
                          m.run_id AS output_run_id, m.request_id AS output_request_id, m.content
                   FROM agent_runs r JOIN messages m ON m.id = r.output_message_id
                   WHERE r.created_by_run_id = $1 AND r.run_type = 'subagent'""",
                run_id,
            )
            assert len(children) == 1
            child = children[0]
            assert child["status"] == "completed"
            assert child["output_run_id"] == child["id"]
            assert child["output_request_id"] == child["request_id"]
            result = FactEvidenceReviewResult.model_validate_json(child["content"])
            assert result.summary.insufficient_count == result.summary.high_risk_count == 1
            assert suffix in result.violation_reviews[0].inspection_fact
            outputs = await conn.fetch(
                """SELECT t.tool_output FROM tool_calls t JOIN messages m ON m.id=t.message_id
                   WHERE m.run_id=$1 AND t.tool_name='task' AND t.status='success'""",
                run_id,
            )
            assert outputs and any('"review_type":"fact_evidence_review"' in (r["tool_output"] or "") for r in outputs)
            response = await client.get(f"/api/agent/runs/{child['id']}/result", headers=headers)
            assert response.status_code == 200
            assert response.json()["output"] == child["content"]
        finally:
            await conn.close()
    finally:
        if thread_id:
            response = await client.delete(f"/api/chat/thread/{thread_id}", headers=headers)
            assert response.status_code in {200, 404}, response.text
        await delete_agent(client, headers, slug)
