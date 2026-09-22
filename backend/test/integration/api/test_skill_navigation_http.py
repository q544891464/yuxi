"""真实 HTTP 和独立 PostgreSQL 数据库验证导航发布，不使用生产数据库。"""

import copy
import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from sqlalchemy import create_engine, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from server.routers.system_router import system
from server.routers.auth_router import auth
from server.utils.auth_middleware import get_db
from yuxi.storage.postgres.models_business import ConfigOption, Department, Skill, User, OperationLog
from yuxi.utils.auth_utils import AuthUtils


@pytest.fixture(scope="module")
def navigation_server():
    """只在专用 nav_verify 数据库启动真实路由和认证依赖。"""
    url = os.environ.get("TEST_NAV_DATABASE_URL", "")
    if not url:
        pytest.skip("需要独立 TEST_NAV_DATABASE_URL")
    assert "/nav_verify_" in url, "禁止在业务数据库运行"
    engine = create_engine(url.replace("postgresql+asyncpg", "postgresql+psycopg"))
    tables = [Department.__table__, User.__table__, Skill.__table__, ConfigOption.__table__, OperationLog.__table__]
    for table in tables:
        table.create(engine)
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
        conn.execute(
            Skill.__table__.insert().values(
                slug="navigation-test",
                name="测试技能",
                description="验证导航绑定",
                dir_path="shared/navigation-test",
                enabled=True,
                share_config={
                    "version": 2,
                    "read_scope": {"access_level": "global", "department_ids": [], "user_uids": []},
                    "manage_scope": None,
                },
            )
        )
    async_engine = create_async_engine(url, poolclass=NullPool)
    sessions = async_sessionmaker(async_engine, expire_on_commit=False)

    async def database():
        """为每个真实 HTTP 请求提供独立 PostgreSQL 事务。"""
        async with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(system, prefix="/api")
    app.include_router(auth, prefix="/api")
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


def test_navigation_publish_permissions_conflict_and_persistence(navigation_server):
    """发布、并发保护、普通用户只读及空树保存都回读真实数据库。"""
    client, tokens, engine = navigation_server
    path = "/api/system/skill-navigation"
    assert client.get(path).status_code == 401
    initial = client.get(path, headers=tokens["user"]).json()
    assert initial["revision"] == 0 and initial["nodes"][0]["id"] == "inspection"
    candidate = copy.deepcopy(initial)
    entry = candidate["nodes"][0]
    entry.update(id="test-entry", label="验证入口", skillSlug="navigation-test", children=[])
    candidate["nodes"] = [entry]
    assert client.put(path, headers=tokens["user"], json=candidate).status_code == 403
    invalid = copy.deepcopy(candidate)
    invalid["nodes"][0]["skillSlug"] = "missing-skill"
    assert client.put(path, headers=tokens["admin"], json=invalid).status_code == 400
    invalid["nodes"][0]["skillSlug"] = "navigation-test"
    invalid["nodes"].append(copy.deepcopy(invalid["nodes"][0]))
    assert client.put(path, headers=tokens["admin"], json=invalid).status_code == 422
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda role: client.put(path, headers=tokens[role], json=candidate), ["admin", "superadmin"])
        )
    assert sorted(r.status_code for r in results) == [200, 409]
    published = client.get(path, headers=tokens["user"]).json()
    assert published == {"revision": 1, "nodes": candidate["nodes"]}
    with engine.connect() as conn:
        stored = conn.scalar(select(ConfigOption.value).where(ConfigOption.key == "skill_navigation"))
    assert stored == published
    with engine.begin() as conn:
        conn.execute(update(Skill).where(Skill.slug == "navigation-test").values(enabled=False))
    added = copy.deepcopy(published)
    added["nodes"].append({**added["nodes"][0], "id": "another-entry"})
    assert client.put(path, headers=tokens["admin"], json=added).status_code == 400
    assert client.put(path, headers=tokens["admin"], json=published).status_code == 200
    assert client.put(path, headers=tokens["admin"], json={"revision": 2, "nodes": []}).status_code == 200
    assert client.get(path, headers=tokens["user"]).json() == {"revision": 3, "nodes": []}
    with engine.connect() as conn:
        assert conn.scalar(select(Skill.slug).where(Skill.slug == "navigation-test")) == "navigation-test"


def test_ducha_role_and_navigation_http(navigation_server):
    """真实身份、配置持久化与入口过滤不能靠伪造客户端角色绕过。"""
    client, tokens, engine = navigation_server
    page = "/api/system/chat/ducha"
    path = "/api/system/skill-navigation"
    assert client.get(page).status_code == 401
    assert client.get(page, headers=tokens["user"]).status_code == 403
    for role in ["ducha", "admin", "superadmin"]:
        assert client.get(page, headers=tokens[role]).json()["specialist"] == "辅助督查专员"
    assert client.get(path + "/manage", headers=tokens["user"]).status_code == 403
    assert client.get(path + "/manage", headers=tokens["ducha"]).status_code == 403
    with engine.begin() as conn:
        conn.execute(update(Skill).where(Skill.slug == "navigation-test").values(enabled=True))
    config = client.get(path + "/manage", headers=tokens["admin"]).json()
    config["nodes"] = [
        {
            "id": "ducha-group",
            "label": "督查",
            "skillSlug": "navigation-test",
            "skillDisplayName": "测试",
            "inputHint": "材料",
            "outputHint": "结果",
            "presetPrompt": "检查",
            "visibleRoles": ["ducha"],
            "visibleWorkspaces": ["inspection", "ducha"],
            "childrenWorkspaces": ["inspection", "ducha"],
            "children": [
                {
                    "id": "child",
                    "label": "子项",
                    "skillSlug": "navigation-test",
                    "skillDisplayName": "测试",
                    "inputHint": "材料",
                    "outputHint": "结果",
                    "presetPrompt": "检查",
                    "visibleRoles": ["user", "ducha"],
                    "visibleWorkspaces": ["inspection", "ducha"],
                    "childrenWorkspaces": ["inspection", "ducha"],
                    "children": [],
                }
            ],
        }
    ]
    assert client.put(path, headers=tokens["ducha"], json=config).status_code == 403
    result = client.put(path, headers=tokens["admin"], json=config)
    assert result.status_code == 200, result.text
    assert client.get(path, headers=tokens["user"]).json()["nodes"] == []
    assert client.get(path, headers=tokens["admin"]).json()["nodes"] == []
    assert (
        client.get(path, params={"workspace": "ducha"}, headers=tokens["ducha"]).json()["nodes"][0]["children"][0]["id"]
        == "child"
    )
    with engine.connect() as conn:
        assert (
            conn.scalar(select(ConfigOption.value).where(ConfigOption.key == "skill_navigation"))["nodes"]
            == config["nodes"]
        )
    user_path = "/api/auth/users/2"
    assert client.put(user_path, headers=tokens["user"], json={"role": "ducha"}).status_code == 403
    assert client.put(user_path, headers=tokens["admin"], json={"role": "admin"}).status_code == 422
    assert client.put("/api/auth/users/3", headers=tokens["superadmin"], json={"role": "ducha"}).status_code == 403
    assigned = client.put(user_path, headers=tokens["admin"], json={"role": "ducha"})
    assert assigned.status_code == 200, assigned.text
    with engine.connect() as conn:
        assert conn.scalar(select(User.role).where(User.id == 2)) == "ducha"
    assert client.get(page, headers=tokens["user"]).status_code == 200
    assert client.put(user_path, headers=tokens["admin"], json={"role": "user"}).status_code == 200
    assert client.get(page, headers=tokens["user"]).status_code == 403


def test_page_access_config_permissions_persistence_and_revision(navigation_server):
    """真实认证、HTTP 与 PostgreSQL 验证角色页面配置。"""
    client, tokens, engine = navigation_server
    path = "/api/system/page-access"
    assert client.get(path, params={"path": "/chat"}).status_code == 401
    for role in ["user", "ducha", "admin"]:
        assert client.get(path + "/manage", headers=tokens[role]).status_code == 403
    config = client.get(path + "/manage", headers=tokens["superadmin"]).json()
    config.pop("catalog")
    for role in ["user", "ducha", "admin"]:
        assert client.put(path, headers=tokens[role], json=config).status_code == 403
    for target in ["/chat", "/agent", "/extensions", "/chat/knowledge/k"]:
        data = client.get(path, params={"path": target}, headers=tokens["ducha"]).json()
        assert data["allowed"] is False and data["home"] == "/chat/ducha"
    assert client.get(path, params={"path": "/chat/ducha/t"}, headers=tokens["ducha"]).json()["allowed"]
    invalid = copy.deepcopy(config)
    invalid["rules"]["user"]["pages"] = []
    assert client.put(path, headers=tokens["superadmin"], json=invalid).status_code == 422
    config["rules"]["admin"] = {"pages": ["/chat"], "home": "/chat"}
    saved = client.put(path, headers=tokens["superadmin"], json=config)
    assert saved.status_code == 200
    with engine.connect() as conn:
        stored = conn.execute(select(ConfigOption.value).where(ConfigOption.key == "role_page_access")).scalar_one()
        assert stored == saved.json()
    assert client.get(path, params={"path": "/agent"}, headers=tokens["admin"]).json()["allowed"] is False
    assert client.get("/api/system/chat/ducha", headers=tokens["admin"]).status_code == 403
    assert client.get(path, params={"path": "/agent"}, headers=tokens["superadmin"]).json()["allowed"]
    assert client.put(path, headers=tokens["superadmin"], json=config).status_code == 409
    options = client.get("/api/system/config/options", headers=tokens["admin"])
    assert options.status_code == 200
    assert "role_page_access" not in {item["key"] for item in options.json()["options"]}


def test_workspace_navigation_settings_http(navigation_server):
    """工作区筛选、父级限制及配置权限通过真实HTTP和数据库验证。"""
    client, tokens, engine = navigation_server
    path = "/api/system/skill-navigation"
    config = client.get(path + "/manage", headers=tokens["superadmin"]).json()
    root = config["nodes"][0]
    root.update(visibleRoles=["user", "ducha", "admin", "superadmin"], childrenWorkspaces=["ducha"])
    assert client.put(path, headers=tokens["user"], json=config).status_code == 403
    invalid = copy.deepcopy(config)
    invalid["nodes"][0]["visibleWorkspaces"] = ["typo"]
    assert client.put(path, headers=tokens["superadmin"], json=invalid).status_code == 422
    saved = client.put(path, headers=tokens["superadmin"], json=config)
    assert saved.status_code == 200, saved.text
    with engine.connect() as conn:
        stored = conn.scalar(select(ConfigOption.value).where(ConfigOption.key == "skill_navigation"))
    assert stored == saved.json()
    assert client.get(path, headers=tokens["user"]).json()["nodes"][0]["children"] == []
    assert (
        client.get(path, params={"workspace": "ducha"}, headers=tokens["ducha"]).json()["nodes"][0]["children"][0]["id"]
        == "child"
    )
    assert client.get(path, params={"workspace": "ducha"}, headers=tokens["user"]).status_code == 403
    assert client.get(path, params={"workspace": "inspection"}, headers=tokens["ducha"]).status_code == 403
    assert client.get(path, params={"workspace": "unknown"}, headers=tokens["superadmin"]).status_code == 422
    # 超管也不能在消费者菜单绕过显式工作区隐藏；管理页仍可编辑。
    saved = saved.json()
    saved["nodes"][0]["visibleWorkspaces"] = ["inspection"]
    assert client.put(path, headers=tokens["superadmin"], json=saved).status_code == 200
    assert client.get(path, params={"workspace": "ducha"}, headers=tokens["superadmin"]).json()["nodes"] == []
    assert len(client.get(path + "/manage", headers=tokens["superadmin"]).json()["nodes"]) == 1
