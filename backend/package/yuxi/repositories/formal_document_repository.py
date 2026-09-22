"""正式文书查询、可见性与并发锁边界。"""

from sqlalchemy import and_, false, or_, select, text
from sqlalchemy.dialects.postgresql import insert

from yuxi.storage.postgres.models_business import (
    ConfigOption,
    Department,
    FormalDocument,
    FormalDocumentEvent,
    FormalDocumentFile,
    User,
)


class FormalDocumentRepository:
    """复用请求事务，查询不越过当前文书的接收范围。"""

    def __init__(self, db):
        """保存当前请求事务。"""
        self.db = db

    async def config(self, lock=False, uid=None):
        """配置写入通过唯一记录行锁串行化。"""
        if lock:
            await self.db.execute(
                insert(ConfigOption)
                .values(
                    key="document_workflows",
                    name="文书流程",
                    description="正式文书接收配置",
                    params={"internal": True, "fields": []},
                    value={"revision": 0, "workflows": []},
                    created_by=uid,
                )
                .on_conflict_do_nothing(index_elements=[ConfigOption.key])
            )
        query = select(ConfigOption).where(ConfigOption.key == "document_workflows")
        return await self.db.scalar(query.with_for_update() if lock else query)

    async def lock_creation(self, document_id):
        """同一创建标识串行重放，禁止重复草稿和重复记录。"""
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": "formal-document:" + document_id}
        )
        return await self.db.scalar(select(FormalDocument.creator_uid).where(FormalDocument.id == document_id))

    async def recipients(self, scope):
        """指定人员或同时满足已填写角色与部门条件的有效用户。"""
        filters = []
        if scope.get("roles"):
            filters.append(User.role.in_(scope["roles"]))
        if scope.get("department_ids"):
            filters.append(User.department_id.in_(scope["department_ids"]))
        condition = or_(User.uid.in_(scope.get("user_uids", [])), and_(*filters) if filters else false())
        return list((await self.db.scalars(select(User.uid).where(User.is_deleted == 0, condition))).all())

    async def directory(self):
        """仅管理配置用的人员与部门目录。"""
        users = (await self.db.scalars(select(User).where(User.is_deleted == 0).order_by(User.username))).all()
        departments = (await self.db.scalars(select(Department).order_by(Department.name))).all()
        return {
            "users": [
                {"uid": u.uid, "name": u.username, "role": u.role, "department_id": u.department_id} for u in users
            ],
            "departments": [{"id": d.id, "name": d.name} for d in departments],
        }

    async def recipient_names(self, uids):
        """只解析当前文书已授权接收人姓名。"""
        return list(
            (await self.db.scalars(select(User.username).where(User.uid.in_(uids)).order_by(User.username))).all()
        )

    def visible(self, user):
        """后端资源授权谓词。"""
        return True if user.role == "superadmin" else FormalDocument.readers.contains([str(user.uid)])

    async def list(self, user, category, search, offset):
        """分页返回可见文书，筛选不会扩大读取权限。"""
        query = select(FormalDocument).where(self.visible(user))
        if category == "pending":
            query = query.where(FormalDocument.assignees.contains([str(user.uid)]), FormalDocument.status != "archived")
        elif category == "mine":
            query = query.where(FormalDocument.creator_uid == str(user.uid))
        elif category == "archived":
            query = query.where(FormalDocument.status == "archived")
        if search:
            query = query.where(
                or_(
                    FormalDocument.title.icontains(search, autoescape=True),
                    FormalDocument.case_number.icontains(search, autoescape=True),
                )
            )
        return list(
            (
                await self.db.scalars(
                    query.order_by(FormalDocument.updated_at.desc(), FormalDocument.id).offset(offset).limit(51)
                )
            ).all()
        )

    async def get(self, document_id, user, lock=False):
        """不可见文书与不存在文书使用同一结果。"""
        query = select(FormalDocument).where(FormalDocument.id == document_id, self.visible(user))
        return await self.db.scalar(query.with_for_update() if lock else query)

    async def files(self, document_id):
        """按版本顺序读取不可覆盖文件。"""
        return list(
            (
                await self.db.scalars(
                    select(FormalDocumentFile)
                    .where(FormalDocumentFile.document_id == document_id)
                    .order_by(FormalDocumentFile.sequence)
                )
            ).all()
        )

    async def events(self, document_id):
        """按事务版本读取追加记录。"""
        return list(
            (
                await self.db.scalars(
                    select(FormalDocumentEvent)
                    .where(FormalDocumentEvent.document_id == document_id)
                    .order_by(FormalDocumentEvent.revision)
                )
            ).all()
        )
