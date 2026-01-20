from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.param.knowledge_library import (
    CreateLibraryRequest, UpdateLibraryRequest, AddDocumentRequest, UpdateDocumentRequest
)
from backend.param.crawl import UploadDocRequest
from backend.param.common import Response
from backend.service import knowledge_library as library_service
from backend.config.oss import get_presigned_url_for_upload
from backend.config.log import get_logger
from backend.config.dependencies import get_current_user
from backend.config.settings import settings

logger = get_logger(__name__)

router = APIRouter(
    prefix="/knowledge",
    tags=["KNOWLEDGE_LIBRARY"]
)


@router.get("/libraries")
async def get_libraries(current_user: int = Depends(get_current_user)):
    """获取用户的知识库列表"""
    logger.info(f"用户 {current_user} 请求获取知识库列表")
    return await library_service.get_user_libraries(current_user)


@router.get("/libraries/{library_id}")
async def get_library(library_id: int, current_user: int = Depends(get_current_user)):
    """获取知识库详情"""
    logger.info(f"用户 {current_user} 请求获取知识库详情: {library_id}")
    return await library_service.get_library_detail(library_id, current_user)


@router.post("/libraries")
async def create_library(request: CreateLibraryRequest, current_user: int = Depends(get_current_user)):
    """创建知识库"""
    logger.info(f"用户 {current_user} 请求创建知识库: {request.title}")
    return await library_service.create_library(request, current_user)


@router.put("/libraries/{library_id}")
async def update_library(
    library_id: int,
    request: UpdateLibraryRequest,
    current_user: int = Depends(get_current_user)
):
    """更新知识库"""
    logger.info(f"用户 {current_user} 请求更新知识库: {library_id}")
    return await library_service.update_library(library_id, request, current_user)


@router.delete("/libraries/{library_id}")
async def delete_library(library_id: int, current_user: int = Depends(get_current_user)):
    """删除知识库"""
    logger.info(f"用户 {current_user} 请求删除知识库: {library_id}")
    return await library_service.delete_library(library_id, current_user)


@router.post("/documents")
async def add_document(
    request: AddDocumentRequest,
    current_user: int = Depends(get_current_user)
):
    """添加文档到知识库"""
    logger.info(f"用户 {current_user} 请求添加文档到知识库: {request.library_id}")
    return await library_service.add_document(request, current_user)


@router.put("/documents/{document_id}")
async def update_document(
    document_id: int,
    request: UpdateDocumentRequest,
    current_user: int = Depends(get_current_user)
):
    """更新文档"""
    logger.info(f"用户 {current_user} 请求更新文档: {document_id}")
    return await library_service.update_document(document_id, request, current_user)


@router.delete("/documents/{document_id}")
async def delete_document(document_id: int, current_user: int = Depends(get_current_user)):
    """删除文档"""
    logger.info(f"用户 {current_user} 请求删除文档: {document_id}")
    return await library_service.delete_document(document_id, current_user)


@router.post("/upload-url")
async def get_upload_url(request: UploadDocRequest, current_user: int = Depends(get_current_user)):
    """
    获取COS上传签名URL
    
    Args:
        request: 包含document_name的请求
        current_user: 当前登录用户ID
        
    Returns:
        Response: 包含上传签名URL的响应
    """
    try:
        logger.info(f"用户 {current_user} 请求获取COS上传签名URL: {request.document_name}")
        
        # 检查是否配置了腾讯云COS
        if not settings.COS_SECRET_ID:
            logger.warning("COS未配置，返回本地上传提示")
            return Response.error("COS未配置，请使用本地上传功能或配置腾讯云COS")
        
        # 获取存储桶名称
        bucket = settings.COS_BUCKET_NAME or "ragagent-file-1234567890"
        
        # 调用COS服务获取上传签名URL
        upload_url = get_presigned_url_for_upload(
            bucket=bucket, 
            key=request.document_name
        )
        
        if upload_url:
            logger.info(f"成功获取COS上传签名URL")
            return Response.success(upload_url["url"])
        else:
            logger.warning(f"获取COS上传签名URL失败")
            return Response.error("获取COS上传签名URL失败")
            
    except Exception as e:
        logger.error(f"获取COS上传签名URL异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取COS上传签名URL失败: {str(e)}")