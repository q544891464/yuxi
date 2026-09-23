"""督查页面与角色切换的正反权限案例。"""

from types import SimpleNamespace

import pytest

from yuxi.services.ducha_service import change_business_role, get_ducha_page


@pytest.mark.parametrize("role", ["ducha", "admin", "superadmin"])
def test_authorized_role_gets_ducha_brand(role):
    """授权角色得到督查文案。"""
    assert get_ducha_page(SimpleNamespace(role=role))["title"] == "智能辅助督查数字人"


@pytest.mark.parametrize("role", ["user", "inspector", "reviewer", "unknown", None])
def test_other_roles_cannot_access_ducha(role):
    """普通用户和未知身份不得进入督查页。"""
    with pytest.raises(PermissionError):
        get_ducha_page(SimpleNamespace(role=role))


def test_admin_can_assign_and_revoke_ducha_role():
    """部门管理员仅切换本部门业务角色。"""
    actor = SimpleNamespace(role="admin", department_id=1)
    target = SimpleNamespace(role="user", department_id=1)
    change_business_role(actor, target, "ducha")
    assert target.role == "ducha"
    change_business_role(actor, target, "user")
    assert target.role == "user"


@pytest.mark.parametrize("new_role", ["inspector", "reviewer"])
def test_admin_can_assign_new_business_role(new_role):
    """部门管理员可在本部门业务角色间切换。"""
    actor = SimpleNamespace(role="admin", department_id=1)
    target = SimpleNamespace(role="ducha", department_id=1)
    change_business_role(actor, target, new_role)
    assert target.role == new_role


@pytest.mark.parametrize(
    "actor_role,department,target_role,new_role",
    [
        ("user", 1, "user", "ducha"),
        ("admin", 2, "user", "ducha"),
        ("admin", 1, "admin", "ducha"),
        ("superadmin", 1, "user", "admin"),
        ("admin", 2, "user", "reviewer"),
    ],
)
def test_role_assignment_rejects_privilege_and_department_bypass(actor_role, department, target_role, new_role):
    """拒绝自助、跨部门及管理角色转换。"""
    target = SimpleNamespace(role=target_role, department_id=department)
    with pytest.raises(PermissionError):
        change_business_role(SimpleNamespace(role=actor_role, department_id=1), target, new_role)
    assert target.role == target_role
