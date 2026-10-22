"""
Integration tests for the task management router.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_task_routes_require_admin(test_client, standard_user):
    """Non-admin users should be blocked from accessing task APIs."""
    headers = standard_user["headers"]

    list_response = await test_client.get("/api/tasks", headers=headers)
    assert list_response.status_code == 403

    detail_response = await test_client.get("/api/tasks/some-task", headers=headers)
    assert detail_response.status_code == 403

    cancel_response = await test_client.post("/api/tasks/some-task/cancel", headers=headers)
    assert cancel_response.status_code == 403


async def test_admin_can_list_tasks(test_client, admin_headers):
    """Admin should receive a well-formed task list payload."""
    response = await test_client.get("/api/tasks", headers=admin_headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert "tasks" in payload
    assert isinstance(payload["tasks"], list)
    assert "summary" in payload
    assert isinstance(payload["summary"], dict)


async def test_task_file_results_preserve_history_and_read_current_file(test_client, admin_headers, standard_user):
    """真实 HTTP 与数据库证明部分失败、当前状态、缺失记录和授权边界。"""
    from sqlalchemy import delete, select, update
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from yuxi.storage.postgres.models_business import TaskRecord
    from yuxi.storage.postgres.models_knowledge import KnowledgeBase, KnowledgeFile

    identity = await test_client.get("/api/auth/me", headers=admin_headers)
    assert identity.status_code == 200
    uid = identity.json()["uid"]
    marker = uuid.uuid4().hex
    missing_id = uuid.uuid4().hex
    engine = create_async_engine(os.environ["POSTGRES_URL"])
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            try:
                db.add(
                    KnowledgeBase(
                        kb_id=marker,
                        name="pytest task result",
                        kb_type="milvus",
                        embedding_model_spec="siliconflow-cn:Pro/BAAI/bge-m3",
                        created_by=uid,
                        share_config={
                            "version": 2,
                            "read_scope": {"access_level": "user", "user_uids": [uid], "department_ids": []},
                            "manage_scope": None,
                        },
                    )
                )
                await db.flush()
                db.add(
                    KnowledgeFile(
                        kb_id=marker,
                        file_id=marker,
                        filename="合成失败文件.txt",
                        status="error_parsing",
                        error_message="合成解析失败",
                    )
                )
                historical_result = {
                    "processed": 2,
                    "failed": 0,
                    "items": [
                        {
                            "file_id": marker,
                            "filename": "合成失败文件.txt",
                            "status": "error_parsing",
                            "error_message": "合成解析失败",
                        },
                        {"filename": "成功文件.txt", "status": "parsed"},
                    ],
                }
                db.add(
                    TaskRecord(
                        id=marker,
                        name="pytest partial failure",
                        type="knowledge_parse",
                        status="success",
                        payload={"kb_id": marker},
                        result=historical_result,
                    )
                )
                db.add(
                    TaskRecord(
                        id=missing_id,
                        name="pytest missing result",
                        type="knowledge_index",
                        status="cancelled",
                        payload={"kb_id": marker, "file_ids": [marker]},
                        result=None,
                    )
                )
                await db.commit()
                listing = await test_client.get("/api/tasks", headers=admin_headers)
                detail = await test_client.get(f"/api/tasks/{marker}", headers=admin_headers)
                assert listing.status_code == detail.status_code == 200
                summary = next(item for item in listing.json()["tasks"] if item["id"] == marker)
                assert "result" not in summary and "payload" not in summary
                assert detail.json()["task"]["status"] == "success"
                assert detail.json()["task"]["result"] == historical_result
                expected = {
                    "total": 2,
                    "recorded": 2,
                    "succeeded": 1,
                    "failed": 1,
                    "pending": 0,
                    "unknown": 0,
                    "has_result": True,
                    "truncated": False,
                }
                assert summary["file_result_summary"] == detail.json()["task"]["file_result_summary"] == expected
                missing = await test_client.get(f"/api/tasks/{missing_id}", headers=admin_headers)
                assert missing.json()["task"]["file_result_summary"]["unknown"] == 1
                assert missing.json()["task"]["file_result_summary"]["has_result"] is False

                file_url = f"/api/knowledge/databases/{marker}/documents/{marker}/basic"
                before = await test_client.get(file_url, headers=admin_headers)
                assert before.status_code == 200
                assert before.json()["meta"]["status"] == "error_parsing"
                await db.execute(
                    update(KnowledgeFile)
                    .where(KnowledgeFile.file_id == marker)
                    .values(status="indexed", error_message=None)
                )
                await db.commit()
                current = await test_client.get(file_url, headers=admin_headers)
                assert current.status_code == 200
                assert current.json()["meta"]["status"] == "indexed"
                assert current.json()["meta"]["updated_at"]
                refreshed = await test_client.get(f"/api/tasks/{marker}", headers=admin_headers)
                assert refreshed.json()["task"]["result"] == historical_result
                assert (await db.scalar(select(TaskRecord.result).where(TaskRecord.id == marker))) == historical_result
                denied = await test_client.get(file_url, headers=standard_user["headers"])
                assert denied.status_code == 403
                await db.execute(delete(KnowledgeFile).where(KnowledgeFile.file_id == marker))
                await db.commit()
                removed = await test_client.get(file_url, headers=admin_headers)
                assert removed.status_code == 200
                assert removed.json()["status"] == "failed"
                assert "meta" not in removed.json()
                retained = await test_client.get(f"/api/tasks/{marker}", headers=admin_headers)
                assert retained.json()["task"]["result"] == historical_result
            finally:
                await db.rollback()
                await db.execute(delete(TaskRecord).where(TaskRecord.id.in_([marker, missing_id])))
                await db.execute(delete(KnowledgeBase).where(KnowledgeBase.kb_id == marker))
                await db.commit()
    finally:
        await engine.dispose()


async def test_cancel_unknown_task_returns_client_error(test_client, admin_headers):
    """Cancelling a non-existent task should surface a 400 response."""
    response = await test_client.post("/api/tasks/not-real/cancel", headers=admin_headers)
    assert response.status_code == 400, response.text


async def test_enqueue_document_creates_task(
    test_client,
    admin_headers,
):
    """Trigger knowledge ingestion to ensure a task record is materialised."""
    create_response = await test_client.post(
        "/api/knowledge/databases",
        json={
            "database_name": f"pytest_task_router_{uuid.uuid4().hex[:8]}",
            "description": "Task router integration test",
            "embedding_model_spec": "siliconflow-cn:Pro/BAAI/bge-m3",
            "kb_type": "milvus",
            "additional_params": {},
        },
        headers=admin_headers,
    )
    assert create_response.status_code == 200, create_response.text
    kb_id = create_response.json()["kb_id"]

    try:
        upload_response = await test_client.post(
            "/api/knowledge/files/upload",
            params={"kb_id": kb_id},
            files={
                "file": (
                    f"pytest_task_{uuid.uuid4().hex[:8]}.txt",
                    b"task router integration test",
                    "text/plain",
                )
            },
            headers=admin_headers,
        )
        assert upload_response.status_code == 200, upload_response.text
        upload_payload = upload_response.json()
        file_path = upload_payload["file_path"]

        enqueue_response = await test_client.post(
            f"/api/knowledge/databases/{kb_id}/documents",
            json={
                "items": [file_path],
                "params": {
                    "content_type": "file",
                    "content_hashes": {file_path: upload_payload["content_hash"]},
                    "file_sizes": {file_path: upload_payload["size"]},
                },
            },
            headers=admin_headers,
        )
        assert enqueue_response.status_code == 200, enqueue_response.text

        enqueue_payload = enqueue_response.json()
        assert enqueue_payload.get("status") == "queued"
        task_id = enqueue_payload.get("task_id")
        assert task_id, "Knowledge ingestion did not return a task_id"

        # The task should be queryable immediately after enqueueing.
        detail_response = await test_client.get(f"/api/tasks/{task_id}", headers=admin_headers)
        assert detail_response.status_code == 200, detail_response.text
        detail_payload = detail_response.json().get("task", {})
        assert detail_payload.get("id") == task_id
        assert detail_payload.get("status") in {"queued", "pending", "running", "failed", "success", "cancelled"}

        # Ensure the task surfaces in the list endpoint within a short window.
        for _ in range(10):
            list_response = await test_client.get("/api/tasks", headers=admin_headers)
            assert list_response.status_code == 200, list_response.text
            all_tasks = list_response.json().get("tasks", [])
            if any(entry.get("id") == task_id for entry in all_tasks):
                break
            await asyncio.sleep(0.2)
        else:
            pytest.fail("Task did not appear in list endpoint within timeout window")

        # Poll for successful worker completion, then independently read the persisted file result.
        detail_payload = {}
        for _ in range(120):
            detail_response = await test_client.get(f"/api/tasks/{task_id}", headers=admin_headers)
            assert detail_response.status_code == 200, detail_response.text
            detail_payload = detail_response.json().get("task", {})
            task_status = detail_payload.get("status")
            if task_status in {"success", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.5)
        else:
            pytest.fail("Task did not reach a terminal status within timeout window")

        assert task_status == "success", detail_payload
        result = detail_payload.get("result") or {}
        assert result.get("failed") == 0, result
        assert len(result.get("items") or []) == 1, result
        file_id = result["items"][0].get("file_id")
        assert file_id, result

        file_response = await test_client.get(
            f"/api/knowledge/databases/{kb_id}/documents/{file_id}/basic",
            headers=admin_headers,
        )
        assert file_response.status_code == 200, file_response.text
        file_payload = file_response.json()
        file_meta = file_payload.get("meta") or file_payload
        assert file_meta.get("file_id") == file_id
        assert file_meta.get("status") == "parsed", file_payload
        assert file_meta.get("markdown_file"), file_payload
    finally:
        await test_client.delete(f"/api/knowledge/databases/{kb_id}", headers=admin_headers)
