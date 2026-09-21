"""督查工作区的页面访问与普通业务角色切换。"""


def get_ducha_page(user):
    """仅向督查人员及管理员提供督查页面配置。"""
    if user.role not in {"ducha", "admin", "superadmin"}:
        raise PermissionError("仅督查人员和管理员可访问督查工作区")
    return {
        "title": "智能辅助督查数字人",
        "subtitle": "税务督查智能助手",
        "specialist": "辅助督查专员",
    }


def change_business_role(actor, target, role):
    """在现有用户编辑事务内切换普通用户与督查人员。"""
    if actor.role not in {"admin", "superadmin"}:
        raise PermissionError("仅管理员可分配督查角色")
    if actor.role == "admin" and (actor.department_id is None or actor.department_id != target.department_id):
        raise PermissionError("只能管理本部门用户")
    if role not in {"user", "ducha"} or target.role not in {"user", "ducha"}:
        raise PermissionError("仅支持普通用户与督查人员之间切换")
    target.role = role
