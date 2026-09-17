"""普通用户知识库读取与管理员写入边界。"""

from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from server.utils import knowledge_permissions
from server.utils.auth_middleware import get_required_user


@pytest.mark.parametrize("shared,expected", [(True, 200), (False, 403)])
def test_user_read_checks_resource_scope_and_never_allows_write(monkeypatch, shared, expected):
    """真实权限依赖保留资源可见性，普通用户即使可读也不能写入。"""

    async def database(_kb_id):
        return {
            "created_by": "owner",
            "share_config": {
                "version": 2,
                "read_scope": {"access_level": "global"}
                if shared
                else {"access_level": "user", "user_uids": ["owner"]},
                "manage_scope": None,
            },
        }

    async def user():
        return SimpleNamespace(uid="reader", role="user", department_id=1)

    monkeypatch.setattr(knowledge_permissions.knowledge_base, "get_database_info", database)
    app = FastAPI()
    app.dependency_overrides[get_required_user] = user

    @app.get("/kb/{kb_id}")
    async def read(_user=Depends(knowledge_permissions.require_knowledge_base_user_read)):
        return {"document": "readable"}

    @app.post("/kb/{kb_id}")
    async def write(_user=Depends(knowledge_permissions.require_knowledge_base_manage)):
        raise AssertionError("普通用户不能执行写入")

    client = TestClient(app)
    response = client.get("/kb/example")
    assert response.status_code == expected
    if shared:
        assert response.json() == {"document": "readable"}
    assert client.post("/kb/example").status_code == 403
