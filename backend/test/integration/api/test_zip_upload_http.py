"""真实 TCP HTTP 与隔离 MinIO 的上传边界；认证固定为测试身份。"""

import hashlib
import os
import socket
import threading
import time
import uuid
import zipfile
from types import SimpleNamespace

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Header, HTTPException

pytestmark = pytest.mark.skipif(os.getenv("YUXI_ZIP_HTTP_TEST") != "1", reason="需要隔离 MinIO")


def test_zip_upload_real_http_and_minio(tmp_path):
    """经真实路由上传，回读对象校验内容，覆盖硬上限并清理测试对象。"""
    from server.routers.chat_router import chat
    from server.utils.auth_middleware import get_required_user
    from yuxi.storage.minio import get_minio_client

    uid = "zip-test-" + uuid.uuid4().hex
    app = FastAPI()
    app.include_router(chat, prefix="/api")

    async def test_user(authorization: str | None = Header(default=None)):
        """隔离测试身份，业务鉴权链路不在本测试范围内。"""
        if authorization != "Bearer zip-test":
            raise HTTPException(status_code=401)
        return SimpleNamespace(uid=uid)

    app.dependency_overrides[get_required_user] = test_user
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    runner = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    runner.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started
    storage = get_minio_client()
    bucket = storage.KB_BUCKETS["documents"]
    objects = []
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=180) as client:
            assert client.post("/api/chat/attachments/tmp", files={"file": ("a.txt", b"a")}).status_code == 401
            client.headers["Authorization"] = "Bearer zip-test"
            for size in [6 * 1024**2, 10 * 1024**2, 10 * 1024**2 + 1]:
                path = tmp_path / "plain.txt"
                with path.open("wb") as stream:
                    stream.truncate(size)
                with path.open("rb") as stream:
                    response = client.post("/api/chat/attachments/tmp", files={"file": (path.name, stream)})
                assert response.status_code == (200 if size <= 10 * 1024**2 else 400), response.text
                if response.status_code == 200:
                    objects.append(response.json()["object_name"])
                    assert storage.client.stat_object(bucket, objects[-1]).size == size

            for size in [11 * 1024**2, 200 * 1024**2, 200 * 1024**2 + 1]:
                path = tmp_path / "case.zip"
                # STORED 的固定头部开销由空包实测，避免巨型内存 fixture。
                with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
                    archive.writestr("a.txt", b"")
                payload_size = size - path.stat().st_size
                with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
                    with archive.open("a.txt", "w") as target:
                        while payload_size:
                            chunk = b"x" * min(1024 * 1024, payload_size)
                            target.write(chunk)
                            payload_size -= len(chunk)
                assert path.stat().st_size == size
                with path.open("rb") as stream:
                    response = client.post("/api/chat/attachments/tmp", files={"file": (path.name, stream)})
                assert response.status_code == (200 if size <= 200 * 1024**2 else 400), response.text
                if response.status_code == 200:
                    name = response.json()["object_name"]
                    objects.append(name)
                    downloaded = storage.client.get_object(bucket, name)
                    try:
                        actual = hashlib.sha256()
                        while chunk := downloaded.read(1024 * 1024):
                            actual.update(chunk)
                    finally:
                        downloaded.close()
                        downloaded.release_conn()
                    with path.open("rb") as stream:
                        assert actual.digest() == hashlib.file_digest(stream, "sha256").digest()
            response = client.post("/api/chat/attachments/tmp", files={"file": ("fake.zip", b"fake")})
            assert response.status_code == 400
            assert len(
                list(storage.client.list_objects(bucket, prefix=f"tmp/chat_attachments/{uid}/", recursive=True))
            ) == len(objects)
    finally:
        for name in objects:
            storage.client.remove_object(bucket, name)
        server.should_exit = True
        runner.join(timeout=10)
        sock.close()
