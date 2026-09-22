"""真实 HTTP 和独立 PostgreSQL 数据库验证导航发布，不使用生产数据库。"""

import copy
import asyncio
from uuid import uuid4
from yuxi.storage.minio.client import get_minio_client
import yuxi.services.formal_document_service as document_service
from minio.error import S3Error
import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from yuxi.storage.postgres.manager import PostgresManager

from server.routers.formal_document_router import formal_documents
from server.routers.system_router import system
from server.utils.auth_middleware import get_db
from yuxi.storage.postgres.models_business import (
    ConfigOption,
    Department,
    User,
    FormalDocument,
    FormalDocumentFile,
    FormalDocumentEvent,
)
from yuxi.utils.auth_utils import AuthUtils

TEST_BUCKET = "document-verify-" + uuid4().hex


def test_internal_document_guard_preserves_system_settings(document_server, monkeypatch):
    """内部文书保护不能阻断管理员单项及批量保存系统配置。"""
    from yuxi.config.options import ensure_options_in_db
    import server.routers.system_router as system_router

    client, tokens, engine = document_server

    async def initialize_options():
        """为隔离数据库初始化正式配置定义。"""
        async_engine = create_async_engine(os.environ["TEST_NAV_DATABASE_URL"], poolclass=NullPool)
        try:
            async with async_sessionmaker(async_engine)() as session:
                await ensure_options_in_db(session)
                await session.commit()
        finally:
            await async_engine.dispose()

    async def invalidate_cache(key):
        """本例验证持久化，不连接共享 Redis。"""
        assert key == "system_options"

    asyncio.run(initialize_options())
    monkeypatch.setattr(system_router, "invalidate_option_cache", invalidate_cache)
    for endpoint, payload, expected in [
        ("/config", {"key": "default_model", "value": "fixture:single"}, {"default_model": "fixture:single"}),
        (
            "/config/update",
            {"default_model": "fixture:batch", "fast_model": "fixture:fast"},
            {"default_model": "fixture:batch", "fast_model": "fixture:fast"},
        ),
    ]:
        assert client.post("/api/system" + endpoint, json=payload, headers=tokens["user"]).status_code == 403
        response = client.post("/api/system" + endpoint, json=payload, headers=tokens["admin"])
        assert response.status_code == 200, response.text
        with engine.connect() as connection:
            value = connection.execute(
                select(ConfigOption.value).where(ConfigOption.key == "system_options")
            ).scalar_one()
        for key, expected_value in expected.items():
            assert value[key] == expected_value

    assert (
        client.post("/api/system/config/update", json={"unknown": "value"}, headers=tokens["admin"]).status_code == 400
    )


@pytest.fixture(scope="module")
def document_server():
    """只在专用 nav_verify 数据库启动真实路由和认证依赖。"""
    url = os.environ.get("TEST_NAV_DATABASE_URL", "")
    if not url:
        pytest.skip("需要独立 TEST_NAV_DATABASE_URL")
    assert "/nav_verify_" in url, "禁止在业务数据库运行"
    original_bucket = document_service.DOCUMENT_BUCKET
    document_service.DOCUMENT_BUCKET = TEST_BUCKET
    engine = create_engine(url.replace("postgresql+asyncpg", "postgresql+psycopg"))
    tables = [
        Department.__table__,
        User.__table__,
        ConfigOption.__table__,
        FormalDocument.__table__,
        FormalDocumentFile.__table__,
        FormalDocumentEvent.__table__,
    ]
    for table in tables[:3]:
        table.create(engine, checkfirst=True)

    async def migrate_formal_tables():
        """对真实旧库重复执行 owning DDL，验证幂等升级。"""
        manager = PostgresManager()
        manager.async_engine = create_async_engine(url, poolclass=NullPool)
        manager._initialized = True
        try:
            await manager.create_formal_document_tables()
            await manager.create_formal_document_tables()
        finally:
            await manager.async_engine.dispose()
            manager._initialized = False

    asyncio.run(migrate_formal_tables())
    with engine.begin() as conn:
        conn.execute(Department.__table__.insert().values(id=1, name="验证部门"))
        for id, role in [(1, "admin"), (2, "user"), (3, "superadmin"), (4, "ducha")]:
            conn.execute(
                User.__table__.insert().values(
                    id=id,
                    uid=f"nav-{role}",
                    username=f"nav-{role}",
                    role=role,
                    department_id=1,
                    password_hash="not-a-login-password",
                )
            )
    async_engine = create_async_engine(url, poolclass=NullPool)
    sessions = async_sessionmaker(async_engine, expire_on_commit=False)

    async def database():
        """为每个真实 HTTP 请求提供独立 PostgreSQL 事务。"""
        async with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(formal_documents, prefix="/api")
    app.include_router(system, prefix="/api")
    app.dependency_overrides[get_db] = database
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started
    tokens = {
        role: {"Authorization": "Bearer " + AuthUtils.create_access_token({"sub": str(id)})}
        for id, role in [(1, "admin"), (2, "user"), (3, "superadmin"), (4, "ducha")]
    }
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{sock.getsockname()[1]}") as client:
            yield client, tokens, engine
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        engine.dispose()
        storage = get_minio_client().client
        if storage.bucket_exists(TEST_BUCKET):
            for obj in storage.list_objects(TEST_BUCKET, recursive=True):
                storage.remove_object(TEST_BUCKET, obj.object_name)
            storage.remove_bucket(TEST_BUCKET)
        document_service.DOCUMENT_BUCKET = original_bucket


def test_formal_document_workflow_and_private_files(document_server):
    """真实网络、PG 与私有对象验证权限、版本、退回及归档。"""
    client, tokens, engine = document_server
    root = "/api/formal-documents"

    def scope(**kwargs):
        """生成明确范围。"""
        return {"user_uids": [], "roles": [], "department_ids": [], **kwargs}

    workflow = {
        "id": "review",
        "name": "稽查至督查",
        "enabled": True,
        "starters": scope(user_uids=["nav-user"]),
        "steps": [
            {"name": "审理", "recipients": scope(roles=["admin"], department_ids=[1])},
            {"name": "督查", "recipients": scope(user_uids=["nav-ducha"])},
        ],
        "archive_readers": scope(),
    }
    config = {"revision": 0, "workflows": [workflow]}
    assert client.get(root).status_code == 401
    assert client.get(root + "/workflows?manage=true", headers=tokens["user"]).status_code == 403
    assert client.put(root + "/workflows", json=config, headers=tokens["admin"]).status_code == 403
    invalid = copy.deepcopy(config)
    invalid["workflows"][0]["steps"][0]["recipients"] = scope()
    assert client.put(root + "/workflows", json=invalid, headers=tokens["superadmin"]).status_code == 400
    result = client.put(root + "/workflows", json=config, headers=tokens["superadmin"])
    assert result.status_code == 200, result.text
    assert (
        client.put(
            "/api/system/config/options/document_workflows", json={"value": {}}, headers=tokens["admin"]
        ).status_code
        == 400
    )
    assert client.put(root + "/workflows", json=config, headers=tokens["superadmin"]).status_code == 409
    assert client.get(root + "/workflows", headers=tokens["ducha"]).json() == {"workflows": []}
    request = {"request_id": str(uuid4()), "title": "测试正式文书", "case_number": "TEST-1", "workflow_id": "review"}
    assert client.post(root, json=request, headers=tokens["ducha"]).status_code == 403
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post(root, json=request, headers=tokens["user"]), range(2)))
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    document = results[0].json()
    path = root + "/" + document["id"]
    assert client.get(path, headers=tokens["admin"]).status_code == 404
    assert client.get(root + "?category=all", headers=tokens["ducha"]).json()["items"] == []
    content = b"%PDF-1.7\nformal-version-one"
    upload = client.post(
        path + "/files", headers=tokens["user"], data={"revision": 0}, files={"file": ("正式文书.pdf", content)}
    )
    assert upload.status_code == 200, upload.text
    document = upload.json()
    file_id = document["files"][0]["id"]
    download = path + "/files/" + file_id
    assert client.get(download, headers=tokens["ducha"]).status_code == 404
    assert client.get(download, headers=tokens["user"]).content == content
    with engine.connect() as conn:
        stored = (
            conn.execute(select(FormalDocumentFile.__table__).where(FormalDocumentFile.id == file_id)).mappings().one()
        )
        assert stored["size"] == len(content)
        key = stored["object_key"]
    storage = get_minio_client()
    assert storage.download_file(TEST_BUCKET, key) == content
    with pytest.raises(S3Error) as no_policy:
        storage.client.get_bucket_policy(TEST_BUCKET)
    assert no_policy.value.code == "NoSuchBucketPolicy"
    # 删除已发布流程不改变既有文书快照。
    assert (
        client.put(root + "/workflows", headers=tokens["superadmin"], json={"revision": 1, "workflows": []}).status_code
        == 200
    )
    action = {"revision": 1, "action": "submit", "confirmed": True, "file_ids": [file_id]}
    assert (
        client.post(path + "/actions", headers=tokens["user"], json={**action, "confirmed": False}).status_code == 400
    )
    assert (
        client.post(path + "/actions", headers=tokens["user"], json={**action, "file_ids": [str(uuid4())]}).status_code
        == 400
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: client.post(path + "/actions", headers=tokens["user"], json=action), range(2))
        )
    assert sorted(r.status_code for r in results) == [200, 403]
    document = client.get(path, headers=tokens["admin"]).json()
    assert document["can_edit"] and document["step"] == "审理"
    assert client.get(download, headers=tokens["admin"]).content == content
    assert client.get(path, headers=tokens["ducha"]).status_code == 404
    returned = client.post(
        path + "/actions", headers=tokens["admin"], json={"revision": 2, "action": "return", "comment": "补充附件"}
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == "returned"
    second = client.post(
        path + "/files", headers=tokens["user"], data={"revision": 3}, files={"file": ("正式文书.pdf", b"version-two")}
    )
    assert second.status_code == 200, second.text
    new_id = second.json()["files"][-1]["id"]
    assert len(second.json()["files"]) == 2
    assert client.get(download, headers=tokens["user"]).content == content
    action.update(revision=4, file_ids=[new_id])
    assert client.post(path + "/actions", headers=tokens["user"], json=action).status_code == 200
    action["revision"] = 5
    assert client.post(path + "/actions", headers=tokens["admin"], json=action).status_code == 200
    action["revision"] = 6
    archived = client.post(path + "/actions", headers=tokens["ducha"], json=action)
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"
    assert client.post(path + "/actions", headers=tokens["ducha"], json={**action, "revision": 7}).status_code == 403
    assert (
        client.post(
            path + "/files", headers=tokens["ducha"], data={"revision": 7}, files={"file": ("x.pdf", b"bad")}
        ).status_code
        == 403
    )
    assert len(client.get(root + "?category=archived", headers=tokens["user"]).json()["items"]) == 1
    with engine.connect() as conn:
        assert conn.scalar(select(FormalDocument.status).where(FormalDocument.id == document["id"])) == "archived"
        events = (
            conn.execute(select(FormalDocumentEvent.__table__).where(FormalDocumentEvent.document_id == document["id"]))
            .mappings()
            .all()
        )
        assert sorted(e["revision"] for e in events) == list(range(8))
        assert next(e for e in events if e["action"] == "archive")["detail"]["file_ids"] == [new_id]


def test_direct_archive_is_private_and_validates_files(document_server):
    """直接归档保持个人可见，伪造路径、超限与旧版本不能产生文件记录。"""
    client, tokens, engine = document_server
    root = "/api/formal-documents"
    result = client.post(root, headers=tokens["ducha"], json={"request_id": str(uuid4()), "title": "个人归档"})
    assert result.status_code == 200, result.text
    path = root + "/" + result.json()["id"]
    for name, data, expected in [
        ("../x.pdf", b"x", 400),
        ("x.exe", b"x", 400),
        ("x.pdf", b"x" * (10 * 1024 * 1024 + 1), 413),
    ]:
        assert (
            client.post(
                path + "/files", headers=tokens["ducha"], data={"revision": 0}, files={"file": (name, data)}
            ).status_code
            == expected
        )
    assert client.get(path, headers=tokens["ducha"]).json()["files"] == []
    result = client.post(
        path + "/files", headers=tokens["ducha"], data={"revision": 0}, files={"file": ("x.wps", b"official")}
    )
    assert result.status_code == 200, result.text
    assert (
        client.post(
            path + "/files", headers=tokens["ducha"], data={"revision": 0}, files={"file": ("x.pdf", b"stale")}
        ).status_code
        == 409
    )
    file_id = result.json()["files"][0]["id"]
    archived = client.post(
        path + "/actions",
        headers=tokens["ducha"],
        json={"revision": 1, "action": "submit", "confirmed": True, "file_ids": [file_id]},
    )
    assert archived.json()["status"] == "archived"
    assert client.get(path, headers=tokens["user"]).status_code == 404
    assert client.get(path, headers=tokens["superadmin"]).status_code == 200


def test_department_intersection_and_extra_archive_readers(document_server):
    """同角色不同部门不能接收，归档额外读者仅在归档后获权。"""
    client, tokens, engine = document_server
    with engine.begin() as conn:
        conn.execute(Department.__table__.insert().values(id=2, name="其他部门"))
        for user_id, uid, role in [(5, "other-ducha", "ducha"), (6, "archive-reader", "user")]:
            conn.execute(
                User.__table__.insert().values(
                    id=user_id, uid=uid, username=uid, role=role, department_id=2, password_hash="not-a-login-password"
                )
            )
    other = {"Authorization": "Bearer " + AuthUtils.create_access_token({"sub": "5"})}
    reader = {"Authorization": "Bearer " + AuthUtils.create_access_token({"sub": "6"})}
    root = "/api/formal-documents"
    current = client.get(root + "/workflows?manage=true", headers=tokens["superadmin"]).json()
    candidate = {
        "revision": current["revision"],
        "workflows": [
            {
                "id": "dept",
                "name": "部门范围",
                "starters": {"user_uids": ["nav-user"]},
                "steps": [{"name": "督查", "recipients": {"roles": ["ducha"], "department_ids": [1]}}],
                "archive_readers": {"user_uids": ["archive-reader"]},
            }
        ],
    }
    invalid = copy.deepcopy(candidate)
    invalid["workflows"][0]["starters"]["user_uids"] = ["missing-user"]
    assert client.put(root + "/workflows", json=invalid, headers=tokens["superadmin"]).status_code == 400
    assert client.put(root + "/workflows", json=candidate, headers=tokens["superadmin"]).status_code == 200
    created = client.post(
        root, headers=tokens["user"], json={"request_id": str(uuid4()), "title": "部门移交", "workflow_id": "dept"}
    )
    assert created.status_code == 200
    path = root + "/" + created.json()["id"]
    uploaded = client.post(
        path + "/files", headers=tokens["user"], data={"revision": 0}, files={"file": ("记录.txt", b"confirmed")}
    ).json()
    file_id = uploaded["files"][0]["id"]
    action = {"revision": 1, "action": "submit", "confirmed": True, "file_ids": [file_id]}
    assert client.post(path + "/actions", headers=tokens["user"], json=action).status_code == 200
    assert client.get(path, headers=other).status_code == 404
    assert client.get(path, headers=reader).status_code == 404
    assert (
        client.post(path + "/actions", headers=tokens["ducha"], json={"revision": 2, "action": "return"}).status_code
        == 400
    )
    action["revision"] = 2
    assert client.post(path + "/actions", headers=tokens["ducha"], json=action).status_code == 200
    assert client.get(path + "/files/" + file_id, headers=reader).content == b"confirmed"
    assert client.get(path, headers=other).status_code == 404
