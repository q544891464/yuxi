"""按角色限制页面入口，不替代资源与 API 授权。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from yuxi.repositories.page_access_repository import PageAccessRepository

PAGES = [
    {"path": "/chat", "label": "稽查工作区", "roles": ["user", "inspector", "reviewer", "ducha", "admin"]},
    {"path": "/chat/ducha", "label": "督查工作区", "roles": ["ducha", "admin"]},
    {"path": "/agent", "label": "智能体工作台", "roles": ["admin"]},
    {"path": "/workspace", "label": "个人空间", "roles": ["user", "inspector", "reviewer", "ducha", "admin"]},
    {"path": "/extensions", "label": "知识库与技能", "roles": ["user", "inspector", "reviewer", "ducha", "admin"]},
    {"path": "/agent-manage", "label": "智能体管理", "roles": ["user", "inspector", "reviewer", "ducha", "admin"]},
    {"path": "/dashboard", "label": "数据总览", "roles": ["admin"]},
]


class PageRule(BaseModel):
    """空范围代表沿用角色原有页面权限。"""

    model_config = ConfigDict(extra="forbid")
    pages: list[str] | None = Field(default=None, max_length=7)
    home: str


class PageAccessConfig(BaseModel):
    """只接受内置角色与页面，且默认入口必须可访问。"""

    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    rules: dict[Literal["user", "inspector", "reviewer", "ducha", "admin"], PageRule]

    @model_validator(mode="after")
    def validate_rules(self):
        """拒绝空范围、越权页面和不能到达的默认入口。"""
        if set(self.rules) != {"user", "inspector", "reviewer", "ducha", "admin"}:
            raise ValueError("必须配置全部业务角色")
        for role, rule in self.rules.items():
            available = {page["path"] for page in PAGES if role in page["roles"]}
            selected = available if rule.pages is None else set(rule.pages)
            if not selected or not selected <= available or rule.home not in selected:
                raise ValueError("允许页面不能为空，默认首页必须位于该角色允许页面中")
            if rule.pages is not None and len(selected) != len(rule.pages):
                raise ValueError("页面不得重复")
        return self


class PageAccessConflict(ValueError):
    """其他管理员已修改页面配置。"""


async def get_page_config(db):
    """读取当前持久化规则，未配置时限制督查角色。"""
    stored = await PageAccessRepository(db).read()
    if stored is None:
        stored = {
            "revision": 0,
            "rules": {
                "user": {"pages": None, "home": "/chat"},
                "inspector": {"pages": None, "home": "/chat"},
                "reviewer": {"pages": None, "home": "/chat"},
                "ducha": {"pages": ["/chat/ducha"], "home": "/chat/ducha"},
                "admin": {"pages": None, "home": "/agent"},
            },
        }
    else:
        stored = {**stored, "rules": {**stored["rules"]}}
        for role in ("inspector", "reviewer"):
            stored["rules"].setdefault(role, {"pages": None, "home": "/chat"})
    return PageAccessConfig.model_validate(stored).model_dump()


def page_root(path):
    """先区分业务子页面，避免稽查前缀包含督查或数据页。"""
    if path.startswith("/chat/knowledge/"):
        return "/extensions"
    if path == "/chat/dashboard":
        return "/dashboard"
    for page in sorted(PAGES, key=lambda p: len(p["path"]), reverse=True):
        root = page["path"]
        if path == root or path.startswith(root + "/"):
            return root
    return None


def resolve_page_access(config, role, path):
    """返回服务端页面决策及供菜单使用的有效范围。"""
    if role == "superadmin":
        return {"allowed": True, "home": "/agent", "pages": None}
    rule = config["rules"][role]
    pages = rule["pages"]
    if pages is None:
        pages = [page["path"] for page in PAGES if role in page["roles"]]
    root = page_root(path)
    allowed = root in pages
    if rule["pages"] is None and root is None and path not in {"/", "/login"}:
        allowed = True
    return {"allowed": allowed, "home": rule["home"], "pages": pages}


async def save_page_config(db, config, user):
    """仅超级管理员可提交配置；版本检查与写入使用同一事务。"""
    if user.role != "superadmin":
        raise PermissionError("需要超级管理员权限")
    rules = {role: rule.model_dump() for role, rule in config.rules.items()}
    result = await PageAccessRepository(db).save(rules, config.revision, str(user.uid))
    if result is None:
        await db.rollback()
        raise PageAccessConflict("配置已更新，请重新加载后编辑")
    await db.commit()
    return result
