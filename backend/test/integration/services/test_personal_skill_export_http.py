"""在独立 PostgreSQL 上通过真实 HTTP 验证个人技能导出。"""

import io
import errno
import os
import socket
import threading
import time
import zipfile
from contextlib import asynccontextmanager

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

from server.routers.skill_router import user_skills
from yuxi.agents.skills import service as svc
from yuxi.storage.postgres.manager import pg_manager
from yuxi.storage.postgres.models_business import Base, Department, User
from yuxi.utils.auth_utils import AuthUtils


@pytest.mark.integration
def test_personal_export_over_http_with_postgres_auth(tmp_path, monkeypatch):
    """认证使用真实数据库用户；文件读取和响应清理使用真实文件系统。"""
    database_url = os.getenv("PERSONAL_EXPORT_TEST_POSTGRES_URL")
    if not database_url:
        pytest.skip("需提供独立的 PERSONAL_EXPORT_TEST_POSTGRES_URL 测试数据库")
    monkeypatch.setenv("POSTGRES_URL", database_url)
    monkeypatch.setenv("JWT_SECRET_KEY", "personal-export-isolated-test-secret-2026")
    # 隔离全局 manager，测试结束后由 monkeypatch 恢复原连接引用。
    for name in ("async_engine", "AsyncSession", "langgraph_pool", "langgraph_checkpointer"):
        monkeypatch.setattr(pg_manager, name, None)
    monkeypatch.setattr(pg_manager, "_initialized", False)
    monkeypatch.setattr(pg_manager, "_langgraph_checkpointer_setup", False)
    monkeypatch.setattr(svc, "get_personal_skills_root_dir", lambda uid: tmp_path / uid)
    exports = tmp_path / "exports"
    exports.mkdir()
    monkeypatch.setattr(svc.tempfile, "tempdir", str(exports))
    tokens = {}

    @asynccontextmanager
    async def lifespan(_app):
        """仅创建本测试所需的用户表，并在结束时释放连接。"""
        pg_manager.initialize()
        try:
            async with pg_manager.async_engine.begin() as connection:
                await connection.run_sync(
                    lambda conn: Base.metadata.create_all(conn, tables=[Department.__table__, User.__table__])
                )
            async with pg_manager.get_async_session_context() as db:
                department = Department(name=f"export-{tmp_path.name}")
                db.add(department)
                await db.flush()
                for uid, role in [("alice", "user"), ("bob", "admin")]:
                    user = User(uid=uid, username=uid, role=role, password_hash="unused", department_id=department.id)
                    db.add(user)
                    await db.flush()
                    tokens[uid] = {"Authorization": f"Bearer {AuthUtils.create_access_token({'sub': str(user.id)})}"}
                await db.commit()
            yield
        finally:
            await pg_manager.close()

    root = tmp_path / "alice" / "demo"
    root.mkdir(parents=True)
    (root / "SKILL.md").write_bytes(b"# Alice\n")
    (root / "resource.bin").write_bytes(bytes(range(256)))
    app = FastAPI(lifespan=lifespan)
    app.include_router(user_skills, prefix="/api")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 20
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started, "测试 HTTP 服务启动失败"
        with httpx.Client(base_url=f"http://127.0.0.1:{listener.getsockname()[1]}") as client:
            endpoint = "/api/skills/personal/demo/export"
            assert client.get(endpoint).status_code == 401
            assert client.get(endpoint, headers={"Authorization": "Bearer invalid"}).status_code == 401
            assert client.get(endpoint, headers=tokens["bob"], params={"uid": "alice"}).status_code == 404
            response = client.get(endpoint, headers=tokens["alice"])
            assert response.status_code == 200, response.text
            assert response.headers["content-type"] == "application/zip"
            assert "demo.zip" in response.headers["content-disposition"]
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                assert archive.read("demo/SKILL.md") == b"# Alice\n"
                assert archive.read("demo/resource.bin") == bytes(range(256))
            # 响应 body 到达后，后台文件清理可能尚未调度完成。
            deadline = time.monotonic() + 2
            while list(exports.iterdir()) and time.monotonic() < deadline:
                time.sleep(0.01)
            assert list(exports.iterdir()) == []
            (root / "leak").symlink_to(root / "SKILL.md")
            assert client.get(endpoint, headers=tokens["alice"]).status_code == 400
            assert list(exports.iterdir()) == []
            (root / "leak").unlink()

            def disk_full(*args, **kwargs):
                """在真实导出路径注入磁盘故障，验证 HTTP 错误类别。"""
                raise OSError(errno.ENOSPC, "No space left on device")

            monkeypatch.setattr(svc.zipfile.ZipFile, "open", disk_full)
            failure = client.get(endpoint, headers=tokens["alice"])
            assert failure.status_code == 500
            assert failure.json()["detail"] == "导出个人技能失败"
            assert list(exports.iterdir()) == []
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()
