"""角色页面规则的有效范围和负向配置验证。"""

import pytest
from pydantic import ValidationError
from yuxi.services.page_access_service import PageAccessConfig, resolve_page_access


def config():
    """构造业务角色默认配置。"""
    return {
        "revision": 0,
        "rules": {
            "user": {"pages": None, "home": "/chat"},
            "inspector": {"pages": None, "home": "/chat"},
            "reviewer": {"pages": None, "home": "/chat"},
            "ducha": {"pages": ["/chat/ducha"], "home": "/chat/ducha"},
            "admin": {"pages": None, "home": "/agent"},
        },
    }


@pytest.mark.parametrize(
    "path", ["/chat", "/chat/duchax", "/agent", "/workspace", "/chat/knowledge/k", "/chat/dashboard", "/extensions"]
)
def test_ducha_denied_other_pages(path):
    """督查前缀不能误放行邻近页面。"""
    assert not resolve_page_access(config(), "ducha", path)["allowed"]


def test_ducha_thread_and_superadmin():
    """督查对话可达，超级管理员不受限制。"""
    assert resolve_page_access(config(), "ducha", "/chat/ducha/t")["allowed"]
    assert resolve_page_access(config(), "superadmin", "/workspace")["allowed"]
    assert resolve_page_access(config(), "admin", "/auth/cli/authorize")["allowed"]


@pytest.mark.parametrize("role", ["inspector", "reviewer"])
def test_new_business_roles_use_inspection_without_ducha_or_admin(role):
    """新业务角色仅继承普通用户的页面，不越过督查和管理边界。"""
    rules = PageAccessConfig.model_validate(config()).model_dump()
    assert resolve_page_access(rules, role, "/chat/thread")["allowed"]
    for path in ["/chat/ducha", "/agent", "/dashboard"]:
        assert not resolve_page_access(rules, role, path)["allowed"]


@pytest.mark.parametrize(
    "pages,home",
    [
        ([], "/chat"),
        (["/chat"], "/agent"),
        (["https://bad"], "https://bad"),
        (["/chat/ducha"], "/chat/ducha"),
        (["/chat", "/chat"], "/chat"),
    ],
)
def test_invalid_user_rules(pages, home):
    """空范围、外链、越权与重复入口拒绝写入。"""
    value = config()
    value["rules"]["user"] = {"pages": pages, "home": home}
    with pytest.raises(ValidationError):
        PageAccessConfig.model_validate(value)
