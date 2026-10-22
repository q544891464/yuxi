"""
Integration tests for dashboard router endpoints.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from yuxi.storage.postgres.models_business import Conversation

from test.live_api_cleanup import make_test_conversation_metadata, make_test_conversation_title

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _set_conversation_statuses(subagent_thread_id: str, deleted_thread_id: str) -> None:
    """使用绑定当前测试事件循环的一次性引擎写入状态事实。"""
    engine = create_async_engine(os.environ["POSTGRES_URL"])
    try:
        session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with session_factory() as db:
            await db.execute(
                update(Conversation).where(Conversation.thread_id == subagent_thread_id).values(status="subagent")
            )
            await db.execute(
                update(Conversation).where(Conversation.thread_id == deleted_thread_id).values(status="deleted")
            )
            await db.commit()
    finally:
        await engine.dispose()


async def test_dashboard_requires_authentication(test_client):
    response = await test_client.get("/api/dashboard/conversations")
    assert response.status_code == 401


async def test_satisfaction_http_distinguishes_unrated_zero_and_mixed_feedback(test_client, admin_headers):
    """回读真实反馈行，验证整体与员工的空值、零分及混合评价口径。"""
    from sqlalchemy import delete, select
    from yuxi.storage.postgres.models_business import (
        AUDIT_MESSAGE_TYPES,
        Agent,
        Message,
        MessageFeedback,
        Project,
        User,
    )

    identity = await test_client.get("/api/auth/me", headers=admin_headers)
    assert identity.status_code == 200
    uid = identity.json()["uid"]
    marker = uuid.uuid4().hex
    engine = create_async_engine(os.environ["POSTGRES_URL"])
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            try:
                db.add(Agent(slug=marker, backend_id="test", name="pytest satisfaction", share_config={}))
                db.add(
                    Project(
                        id=marker,
                        uid=uid,
                        selection_status="implicit",
                        workdir_path=f"pytest/{marker}",
                        directory_mode="managed",
                    )
                )
                await db.flush()
                conversation = Conversation(thread_id=marker, project_id=marker, uid=uid, agent_id=marker)
                db.add(conversation)
                await db.commit()
                for ratings, expected in [
                    ([], None),
                    (["dislike", "dislike"], 0),
                    (["like", "dislike"], 50),
                    (["like", "like", "dislike"], 66.67),
                ]:
                    message_ids = select(Message.id).where(Message.conversation_id == conversation.id)
                    await db.execute(delete(MessageFeedback).where(MessageFeedback.message_id.in_(message_ids)))
                    await db.execute(delete(Message).where(Message.conversation_id == conversation.id))
                    for rating in ratings:
                        message = Message(conversation_id=conversation.id, role="assistant", content="合成评价样本")
                        db.add(message)
                        await db.flush()
                        db.add(MessageFeedback(message_id=message.id, uid=uid, rating=rating))
                    await db.commit()

                    agent_response = await test_client.get("/api/dashboard/stats/agents", headers=admin_headers)
                    basic_response = await test_client.get("/api/dashboard/stats", headers=admin_headers)
                    assert agent_response.status_code == basic_response.status_code == 200
                    agent_stats = next(
                        item for item in agent_response.json()["agent_satisfaction_rates"] if item["agent_id"] == marker
                    )
                    assert agent_stats == {
                        "agent_id": marker,
                        "total_feedbacks": len(ratings),
                        "satisfaction_rate": expected,
                    }
                    stored_ratings = list(
                        (
                            await db.scalars(
                                select(MessageFeedback.rating)
                                .join(Message)
                                .join(Conversation)
                                .join(User, Conversation.uid == User.uid)
                                .join(Agent, Conversation.agent_id == Agent.slug)
                                .where(
                                    Conversation.status.notin_(["deleted", "subagent"]),
                                    User.is_deleted == 0,
                                    (Message.message_type.is_(None))
                                    | (Message.message_type.notin_(AUDIT_MESSAGE_TYPES)),
                                )
                            )
                        ).all()
                    )
                    expected_global = (
                        round(stored_ratings.count("like") / len(stored_ratings) * 100, 2) if stored_ratings else None
                    )
                    assert basic_response.json()["feedback_stats"] == {
                        "total_feedbacks": len(stored_ratings),
                        "satisfaction_rate": expected_global,
                    }
            finally:
                await db.rollback()
                own_messages = select(Message.id).join(Conversation).where(Conversation.thread_id == marker)
                await db.execute(delete(MessageFeedback).where(MessageFeedback.message_id.in_(own_messages)))
                await db.execute(delete(Message).where(Message.id.in_(own_messages)))
                await db.execute(delete(Conversation).where(Conversation.thread_id == marker))
                await db.execute(delete(Project).where(Project.id == marker))
                await db.execute(delete(Agent).where(Agent.slug == marker))
                await db.commit()
    finally:
        await engine.dispose()


async def test_standard_user_is_forbidden(test_client, standard_user):
    response = await test_client.get("/api/dashboard/conversations", headers=standard_user["headers"])
    assert response.status_code == 403


async def test_admin_can_fetch_conversations(test_client, admin_headers):
    response = await test_client.get("/api/dashboard/conversations", headers=admin_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data) == {"items", "total", "limit", "offset"}
    assert isinstance(data["items"], list)
    assert data["total"] >= len(data["items"])


async def test_admin_can_fetch_conversation_filter_options(test_client, admin_headers):
    response = await test_client.get("/api/dashboard/conversations/options", headers=admin_headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data) == {"users", "agents"}
    assert all("is_deleted" in item for item in data["users"])
    assert all("is_deleted" in item for item in data["agents"])


async def test_dashboard_rejects_invalid_query_ranges(test_client, admin_headers):
    responses = [
        await test_client.get("/api/dashboard/stats/threads?time_range=365days", headers=admin_headers),
        await test_client.get("/api/dashboard/conversations?limit=0", headers=admin_headers),
        await test_client.get("/api/dashboard/conversations?offset=-1", headers=admin_headers),
    ]

    assert [response.status_code for response in responses] == [422, 422, 422]


async def test_agent_stats_http_omits_removed_top_performers_contract(test_client, admin_headers):
    """智能体统计 HTTP 契约保留概览字段且不再发布 TOP 5 排行。"""
    response = await test_client.get("/api/dashboard/stats/agents", headers=admin_headers)

    assert response.status_code == 200, response.text
    assert set(response.json()) == {
        "total_agents",
        "agent_conversation_counts",
        "agent_satisfaction_rates",
        "agent_tool_usage",
        "agent_names",
    }


async def test_admin_can_fetch_stats(test_client, admin_headers):
    """Test that the timeseries stats endpoint returns consistent values."""
    response = await test_client.get(
        "/api/dashboard/stats/calls/timeseries?type=models&time_range=14days",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_count"] >= 0
    assert len(data["data"]) == 14
    assert isinstance(data["categories"], list)


async def test_knowledge_stats_matches_runtime_capability(test_client, admin_headers):
    response = await test_client.get("/api/dashboard/stats/knowledge", headers=admin_headers)

    assert response.status_code == 200, response.text
    assert set(response.json()) == {
        "total_databases",
        "total_files",
        "total_nodes",
        "total_storage_size",
        "databases_by_type",
        "file_type_distribution",
    }


async def test_admin_can_fetch_thread_analytics(test_client, admin_headers):
    """Test that thread analytics endpoint returns complete statistics schema."""
    response = await test_client.get(
        "/api/dashboard/stats/threads?time_range=30days",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "summary" in data
    assert "daily_trends" in data
    assert "depth_distribution" in data
    assert "agent_distribution" in data
    assert "top_users" in data
    assert "status_distribution" in data
    assert len(data["daily_trends"]) == 30
    assert data["summary"]["total_threads"] >= 0


async def test_dashboard_http_applies_subagent_and_deleted_conversation_scopes(test_client, admin_headers):
    default_agent = await test_client.get("/api/agent/default", headers=admin_headers)
    assert default_agent.status_code == 200, default_agent.text
    agent = default_agent.json()["agent"]
    agent_id = str(agent.get("slug") or agent["agent_id"])
    marker = f"dashboard-scope-{uuid.uuid4().hex[:10]}"

    async def analytics(*, include_subagents: bool) -> dict:
        response = await test_client.get(
            "/api/dashboard/stats/threads",
            params={
                "time_range": "30days",
                "agent_id": agent_id,
                "include_subagents": str(include_subagents).lower(),
            },
            headers=admin_headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    baseline_default = await analytics(include_subagents=False)
    baseline_including_subagents = await analytics(include_subagents=True)
    thread_ids = []
    for status in ("active", "subagent", "deleted"):
        response = await test_client.post(
            "/api/chat/thread",
            headers=admin_headers,
            json={
                "agent_id": agent_id,
                "title": make_test_conversation_title(f"{marker}-{status}"),
                "metadata": make_test_conversation_metadata(marker),
            },
        )
        assert response.status_code == 200, response.text
        thread_ids.append(str(response.json().get("thread_id") or response.json()["id"]))

    await _set_conversation_statuses(thread_ids[1], thread_ids[2])

    default_scope = await analytics(include_subagents=False)
    subagent_scope = await analytics(include_subagents=True)
    assert default_scope["summary"]["total_threads"] == baseline_default["summary"]["total_threads"] + 1
    assert subagent_scope["summary"]["total_threads"] == baseline_including_subagents["summary"]["total_threads"] + 2

    default_audit = await test_client.get(
        "/api/dashboard/conversations",
        params={"search": marker, "limit": 10},
        headers=admin_headers,
    )
    deleted_audit = await test_client.get(
        "/api/dashboard/conversations",
        params={"search": marker, "status": "deleted", "limit": 10},
        headers=admin_headers,
    )
    assert default_audit.status_code == 200, default_audit.text
    assert deleted_audit.status_code == 200, deleted_audit.text
    assert {item["thread_id"] for item in default_audit.json()["items"]} == set(thread_ids[:2])
    assert {item["thread_id"] for item in deleted_audit.json()["items"]} == {thread_ids[2]}


async def test_admin_can_fetch_feedbacks(test_client, admin_headers):
    """Test that feedback endpoint returns 200 and handles the User join correctly."""
    response = await test_client.get("/api/dashboard/feedbacks", headers=admin_headers)
    assert response.status_code == 200, f"feedbacks failed: {response.text}"
    assert isinstance(response.json(), list)


async def test_dashboard_http_reads_run_token_totals(test_client, admin_headers):
    """真实 HTTP 返回 PostgreSQL 同会话 Run 用量和缺失标记。"""
    from sqlalchemy import select
    from yuxi.storage.postgres.models_business import AgentRun, ConversationStats

    default_agent = await test_client.get("/api/agent/default", headers=admin_headers)
    assert default_agent.status_code == 200
    agent = default_agent.json()["agent"]
    agent_id = str(agent.get("slug") or agent["agent_id"])
    marker = f"dashboard-usage-{uuid.uuid4().hex[:10]}"
    response = await test_client.post(
        "/api/chat/thread",
        headers=admin_headers,
        json={
            "agent_id": agent_id,
            "title": make_test_conversation_title(marker),
            "metadata": make_test_conversation_metadata(marker),
        },
    )
    assert response.status_code == 200
    thread_id = str(response.json().get("thread_id") or response.json()["id"])
    engine = create_async_engine(os.environ["POSTGRES_URL"])
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            conversation = (
                await db.execute(select(Conversation).where(Conversation.thread_id == thread_id))
            ).scalar_one()
            await db.execute(
                update(ConversationStats)
                .where(ConversationStats.conversation_id == conversation.id)
                .values(total_tokens=9999)
            )
            for index, usage in enumerate(
                [
                    {"total": {"total_tokens": 120}, "complete": True, "usage_reported_call_count": 1},
                    {"total": {"total_tokens": 80}, "complete": True, "usage_reported_call_count": 1},
                ]
            ):
                db.add(
                    AgentRun(
                        id=f"{marker}-{index}",
                        request_id=f"{marker}-request-{index}",
                        conversation_id=conversation.id,
                        conversation_thread_id=thread_id,
                        runtime_scope_id=thread_id,
                        uid=conversation.uid,
                        agent_slug=agent_id,
                        status="completed",
                        token_usage=usage,
                    )
                )
            await db.commit()
            for expected, complete in [(200, True), (120, False), (None, False)]:
                listing = await test_client.get(
                    "/api/dashboard/conversations", headers=admin_headers, params={"search": marker}
                )
                detail = await test_client.get(f"/api/dashboard/conversations/{thread_id}", headers=admin_headers)
                assert listing.status_code == detail.status_code == 200
                item = listing.json()["items"][0]
                assert item["status"] == "active"
                assert item["total_tokens"] == detail.json()["total_tokens"] == expected
                assert item["token_usage_complete"] is complete
                assert detail.json()["token_usage_complete"] is complete
                run_id = f"{marker}-{1 if expected == 200 else 0}"
                await db.execute(update(AgentRun).where(AgentRun.id == run_id).values(token_usage={"available": False}))
                await db.commit()
    finally:
        await engine.dispose()
