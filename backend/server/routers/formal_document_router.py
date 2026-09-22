"""正式文书 HTTP 身份及协议适配。"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_db, get_required_user
from yuxi.services.formal_document_service import (
    DocumentAction,
    DocumentCreate,
    DocumentWorkflowConfig,
    FormalDocumentService,
)
from yuxi.storage.postgres.models_business import User

formal_documents = APIRouter(prefix="/formal-documents", tags=["formal-documents"])


def service(db: AsyncSession = Depends(get_db), user: User = Depends(get_required_user)):
    """为请求装配服务。"""
    return FormalDocumentService(db, user)


@formal_documents.get("/workflows")
async def workflows(manage: bool = False, svc=Depends(service)):
    """读取可发起流程或管理配置。"""
    return await svc.configuration(manage)


@formal_documents.put("/workflows")
async def save_workflows(data: DocumentWorkflowConfig, svc=Depends(service)):
    """发布流程配置。"""
    return await svc.save_configuration(data)


@formal_documents.get("")
async def list_documents(
    category: str = Query("pending", pattern="^(pending|mine|archived|all)$"),
    search: str = Query("", max_length=200),
    offset: int = Query(0, ge=0),
    svc=Depends(service),
):
    """分页查询当前身份可见文书。"""
    return await svc.list_documents(category, search, offset)


@formal_documents.post("")
async def create_document(data: DocumentCreate, svc=Depends(service)):
    """保存可恢复的文书草稿。"""
    return await svc.create(data)


@formal_documents.get("/{document_id}")
async def detail(document_id: str, svc=Depends(service)):
    """读取正式版本及流转记录。"""
    return await svc.detail(document_id)


@formal_documents.post("/{document_id}/files")
async def upload(document_id: str, revision: int = Form(ge=0), file: UploadFile = File(), svc=Depends(service)):
    """新增文书文件。"""
    return await svc.upload(document_id, revision, file)


@formal_documents.post("/{document_id}/actions")
async def action(document_id: str, data: DocumentAction, svc=Depends(service)):
    """确认移交、退回或归档。"""
    return await svc.act(document_id, data)


@formal_documents.get("/{document_id}/files/{file_id}")
async def download(document_id: str, file_id: str, svc=Depends(service)):
    """仅通过鉴权接口提供附件下载。"""
    filename, data = await svc.download(document_id, file_id)
    return Response(
        data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename, safe=""),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
