"""正式文书配置、不可变文件与逐环节办理用例。"""

import hashlib
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from yuxi.repositories.formal_document_repository import FormalDocumentRepository
from yuxi.storage.minio.client import get_minio_client
from yuxi.storage.postgres.models_business import FormalDocument, FormalDocumentEvent, FormalDocumentFile
from yuxi.utils.datetime_utils import utc_now_naive

DOCUMENT_BUCKET = "formal-documents"
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


class DocumentScope(BaseModel):
    """空范围代表无人；角色和部门同时指定时取交集。"""

    model_config = ConfigDict(extra="forbid")
    user_uids: list[str] = Field(default_factory=list, max_length=500)
    roles: list[Literal["user", "admin", "ducha", "superadmin"]] = Field(default_factory=list, max_length=4)
    department_ids: list[int] = Field(default_factory=list, max_length=500)


class DocumentStep(BaseModel):
    """一个有序接收环节。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    recipients: DocumentScope


class DocumentWorkflow(BaseModel):
    """创建文书时固定的管理员流程定义。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    starters: DocumentScope
    steps: list[DocumentStep] = Field(default_factory=list, max_length=20)
    archive_readers: DocumentScope = Field(default_factory=DocumentScope)


class DocumentWorkflowConfig(BaseModel):
    """流程列表整体版本防止配置互相覆盖。"""

    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    workflows: list[DocumentWorkflow] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_ids(self):
        """拒绝重复流程标识。"""
        if len({w.id for w in self.workflows}) != len(self.workflows):
            raise ValueError("流程标识重复")
        return self


class DocumentCreate(BaseModel):
    """先保存草稿，再明确确认文件和提交。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    title: str = Field(min_length=1, max_length=200)
    case_number: str = Field(default="", max_length=128)
    workflow_id: str | None = Field(default=None, max_length=64)


class DocumentAction(BaseModel):
    """用户显式确认的移交文件清单。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    revision: int = Field(ge=0, strict=True)
    action: Literal["submit", "return"]
    confirmed: bool = False
    comment: str = Field(default="", max_length=2000)
    file_ids: list[UUID] = Field(default_factory=list, max_length=100)


class FormalDocumentService:
    """事务与对象存储副作用由文书服务统一管理。"""

    def __init__(self, db, user):
        """绑定请求的身份与事务。"""
        self.db, self.user = db, user
        self.repo = FormalDocumentRepository(db)

    async def configuration(self, manage=False):
        """普通用户只获得可发起流程的名称，不泄露人员目录。"""
        if manage and self.user.role != "superadmin":
            raise HTTPException(403, "需要超级管理员权限")
        row = await self.repo.config()
        config = row.value if row else {"revision": 0, "workflows": []}
        if manage:
            return {**config, "directory": await self.repo.directory()}
        workflows = []
        for workflow in config["workflows"]:
            if workflow["enabled"] and str(self.user.uid) in await self.repo.recipients(workflow["starters"]):
                workflows.append(
                    {"id": workflow["id"], "name": workflow["name"], "steps": [s["name"] for s in workflow["steps"]]}
                )
        return {"workflows": workflows}

    async def save_configuration(self, config):
        """校验范围存在后原子替换流程配置。"""
        if self.user.role != "superadmin":
            raise HTTPException(403, "需要超级管理员权限")
        directory = await self.repo.directory()
        valid_users = {u["uid"] for u in directory["users"]}
        valid_departments = {d["id"] for d in directory["departments"]}
        for workflow in config.workflows:
            scopes = [workflow.starters, workflow.archive_readers, *[s.recipients for s in workflow.steps]]
            for scope in scopes:
                if not set(scope.user_uids) <= valid_users or not set(scope.department_ids) <= valid_departments:
                    raise HTTPException(400, "接收人员或部门不存在")
            for scope in [workflow.starters, *[s.recipients for s in workflow.steps]]:
                if not await self.repo.recipients(scope.model_dump()):
                    raise HTTPException(400, "发起或接收范围没有有效人员")
        row = await self.repo.config(lock=True, uid=str(self.user.uid))
        if row.value["revision"] != config.revision:
            raise HTTPException(409, "配置已更新")
        row.value = {"revision": config.revision + 1, "workflows": [w.model_dump() for w in config.workflows]}
        row.updated_by = str(self.user.uid)
        await self.db.commit()
        return await self.configuration(manage=True)

    async def create(self, data):
        """请求标识重放不重复创建草稿。"""
        owner = await self.repo.lock_creation(str(data.request_id))
        if owner is not None and owner != str(self.user.uid):
            raise HTTPException(409, "请求标识已使用")
        existing = await self.repo.get(str(data.request_id), self.user)
        if existing:
            if (
                existing.creator_uid != str(self.user.uid)
                or existing.title != data.title
                or existing.case_number != data.case_number
                or existing.workflow.get("id") != data.workflow_id
            ):
                raise HTTPException(409, "请求标识已使用")
            return await self.detail(existing.id)
        workflow = {"id": None, "name": "直接归档", "steps": [], "archive_readers": {}}
        if data.workflow_id:
            row = await self.repo.config()
            workflow = next(
                (w for w in (row.value["workflows"] if row else []) if w["id"] == data.workflow_id and w["enabled"]),
                None,
            )
            if not workflow or str(self.user.uid) not in await self.repo.recipients(workflow["starters"]):
                raise HTTPException(403, "流程不可发起")
        document = FormalDocument(
            id=str(data.request_id),
            title=data.title,
            case_number=data.case_number,
            creator_uid=str(self.user.uid),
            workflow=workflow,
            readers=[str(self.user.uid)],
            assignees=[str(self.user.uid)],
            previous_assignees={"-1": [str(self.user.uid)]},
            revision=0,
            status="draft",
            step_index=-1,
        )
        self.db.add(document)
        self.record(document, "create", {})
        await self.db.commit()
        return await self.detail(document.id)

    async def detail(self, document_id):
        """只返回鉴权后的业务元数据，隐藏对象地址。"""
        document = await self.require_document(document_id)
        files = await self.repo.files(document.id)
        events = await self.repo.events(document.id)
        return {
            **self.summary(document),
            "assignee_names": await self.repo.recipient_names(document.assignees),
            "files": [
                {
                    "id": f.id,
                    "sequence": f.sequence,
                    "filename": f.filename,
                    "size": f.size,
                    "sha256": f.sha256,
                    "uploaded_by": f.uploaded_by,
                    "created_at": f.created_at,
                }
                for f in files
            ],
            "events": [
                {"action": e.action, "actor": e.actor_name, "detail": e.detail, "created_at": e.created_at}
                for e in events
            ],
        }

    async def list_documents(self, category, search, offset):
        """统一分页查询与可见状态投影。"""
        rows = await self.repo.list(self.user, category, search, offset)
        return {"items": [self.summary(row) for row in rows[:50]], "has_more": len(rows) > 50}

    async def upload(self, document_id, revision, upload):
        """新增独立文件对象并保留旧版本，提交失败清理新增对象。"""
        document = await self.require_document(document_id, revision)
        filename = upload.filename or ""
        if len(filename) > 255 or not filename or any(c in filename for c in "/\\\r\n\x00"):
            raise HTTPException(400, "文件名不合法")
        if PurePosixPath(filename).suffix.lower() not in {
            ".pdf",
            ".doc",
            ".docx",
            ".wps",
            ".xls",
            ".xlsx",
            ".csv",
            ".txt",
            ".png",
            ".jpg",
            ".jpeg",
        }:
            raise HTTPException(400, "不支持该正式文书格式")
        data = await upload.read(MAX_DOCUMENT_BYTES + 1)
        if not data or len(data) > MAX_DOCUMENT_BYTES:
            raise HTTPException(413, "文件为空或超过10MB")
        files = await self.repo.files(document.id)
        if len(files) >= 100:
            raise HTTPException(400, "每份文书最多保留100个文件")
        file_id = str(uuid4())
        key = f"{document.id}/{file_id}"
        storage = get_minio_client()
        try:
            await storage.aupload_file(DOCUMENT_BUCKET, key, data, "application/octet-stream")
            self.db.add(
                FormalDocumentFile(
                    id=file_id,
                    document_id=document.id,
                    sequence=len(files) + 1,
                    filename=filename,
                    size=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    object_key=key,
                    uploaded_by=str(self.user.uid),
                )
            )
            document.revision += 1
            self.record(document, "upload", {"filename": filename, "file_id": file_id})
            await self.db.flush()
        except Exception:
            await self.db.rollback()
            await storage.adelete_file(DOCUMENT_BUCKET, key)
            raise
        # commit 连接中断时结果可能已落库，保留对象以免破坏成功提交的文件。
        await self.db.commit()
        return await self.detail(document_id)

    async def act(self, document_id, data):
        """只允许当前办理人推进一步或退回上一步。"""
        document = await self.require_document(document_id, data.revision)
        source = document.step_index
        details = {"from_step": self.step_name(document), "comment": data.comment}
        if data.action == "return":
            if source < 0 or not data.comment:
                raise HTTPException(400, "退回须存在上一步并填写原因")
            document.step_index -= 1
            document.assignees = await self.repo.recipients(
                {"user_uids": document.previous_assignees[str(document.step_index)]}
            )
            if not document.assignees:
                raise HTTPException(409, "上一环节没有有效接收人员")
            document.status = "returned"
        else:
            files = await self.repo.files(document.id)
            selected = {str(f) for f in data.file_ids}
            if not data.confirmed or not selected or not selected <= {f.id for f in files}:
                raise HTTPException(400, "请确认并选择正式文件")
            details["file_ids"] = sorted(selected)
            target = source + 1
            if target == len(document.workflow["steps"]):
                readers = await self.repo.recipients(document.workflow["archive_readers"])
                document.status, document.assignees = "archived", []
            else:
                readers = await self.repo.recipients(document.workflow["steps"][target]["recipients"])
                if not readers:
                    raise HTTPException(409, "下一环节没有有效接收人员，请联系管理员")
                document.step_index, document.status, document.assignees = target, "in_progress", readers
                document.previous_assignees = {**document.previous_assignees, str(target): readers}
            document.readers = sorted(set(document.readers + readers))
        details.update(to_step=self.step_name(document), recipients=document.assignees)
        details["recipient_names"] = await self.repo.recipient_names(document.assignees)
        document.revision += 1
        self.record(document, "archive" if document.status == "archived" else data.action, details)
        await self.db.commit()
        return await self.detail(document_id)

    async def download(self, document_id, file_id):
        """通过文书读取权限再读取私有对象。"""
        await self.require_document(document_id)
        file = next((f for f in await self.repo.files(document_id) if f.id == file_id), None)
        if not file:
            raise HTTPException(404, "文件不存在")
        data = await get_minio_client().adownload_file(DOCUMENT_BUCKET, file.object_key)
        return file.filename, data

    async def require_document(self, document_id, revision=None):
        """写操作在行锁内校验版本、当前办理人和终态。"""
        document = await self.repo.get(document_id, self.user, lock=revision is not None)
        if not document:
            raise HTTPException(404, "文书不存在")
        if revision is not None:
            if document.status == "archived" or str(self.user.uid) not in document.assignees:
                raise HTTPException(403, "当前用户不可办理")
            if document.revision != revision:
                raise HTTPException(409, "文书已更新，请刷新")
        return document

    def record(self, document, action, detail):
        """业务更新与操作记录在相同事务中保存。"""
        document.updated_at = utc_now_naive()
        self.db.add(
            FormalDocumentEvent(
                id=str(uuid4()),
                document_id=document.id,
                revision=document.revision,
                action=action,
                actor_uid=str(self.user.uid),
                actor_name=self.user.username,
                detail=detail,
            )
        )

    def summary(self, document):
        """供列表和详情共同使用的状态投影。"""
        return {
            "id": document.id,
            "title": document.title,
            "case_number": document.case_number,
            "status": document.status,
            "revision": document.revision,
            "step": self.step_name(document),
            "workflow_name": document.workflow["name"],
            "created_at": document.created_at,
            "updated_at": document.updated_at,
            "can_edit": document.status != "archived" and str(self.user.uid) in document.assignees,
            "can_return": document.step_index >= 0
            and document.status != "archived"
            and str(self.user.uid) in document.assignees,
            "next_step": document.workflow["steps"][document.step_index + 1]["name"]
            if document.step_index + 1 < len(document.workflow["steps"])
            else "归档",
        }

    @staticmethod
    def step_name(document):
        """将内部步骤投影为可读名称。"""
        if document.status == "archived":
            return "已归档"
        return document.workflow["steps"][document.step_index]["name"] if document.step_index >= 0 else "提交人准备"
