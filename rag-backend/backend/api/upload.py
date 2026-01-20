"""
本地文件上传API（不依赖OSS）
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from backend.param.common import Response
from backend.config.log import get_logger
from backend.config.dependencies import get_current_user
from backend.config.database import DatabaseFactory
from backend.model.knowledge_library import KnowledgeLibrary
from backend.rag.chunks.document_extraction import DocumentExtractor
from backend.service.data_sync import DataSyncService
import os
import shutil
import uuid
from pathlib import Path

logger = get_logger(__name__)

router = APIRouter(
    prefix="/upload",
    tags=["UPLOAD"]
)

# 本地文件存储目录
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# 支持的文件格式
SUPPORTED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.md', '.txt'}


@router.post("/process")
async def upload_and_process(
    file: UploadFile = File(...),
    collection_id: str = Form(...),
    library_id: int = Form(...),
    chunk_strategy: str = Form("markdown"),
    current_user: int = Depends(get_current_user)
):
    """
    上传文件并处理（解析 + 切块 + 存储到 Milvus + 可选 LightRAG）
    
    Args:
        file: 上传的文件（支持 PDF/DOCX/MD/TXT）
        collection_id: 知识库集合ID
        library_id: 知识库ID
        chunk_strategy: 切块策略 (markdown/recursive/semantic/character)
        current_user: 当前登录用户ID
        
    Returns:
        Response: 处理结果
    """
    file_path = None
    db = None
    try:
        logger.info(f"用户 {current_user} 上传并处理文件: {file.filename}, 知识库: {collection_id}")
        
        # 1. 验证文件格式
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in SUPPORTED_EXTENSIONS:
            return Response.error(f"不支持的文件格式: {file_ext}，支持: {', '.join(SUPPORTED_EXTENSIONS)}")
        
        # 2. 获取知识库的 enable_graph 设置
        db = DatabaseFactory.create_session()
        library = db.query(KnowledgeLibrary).filter(
            KnowledgeLibrary.id == library_id,
            KnowledgeLibrary.user_id == str(current_user),
            KnowledgeLibrary.is_active == True
        ).first()
        
        if not library:
            return Response.error("知识库不存在或无权限")
        
        enable_graph = library.enable_graph
        db.close()
        db = None
        
        # 3. 保存文件到本地
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = UPLOAD_DIR / unique_filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"文件保存成功: {file_path}")
        
        # 4. 解析文件内容
        extractor = DocumentExtractor()
        try:
            doc_content = extractor.read_document(str(file_path))
            content = doc_content.content
            document_name = file.filename  # 使用原始文件名
        except Exception as extract_error:
            logger.error(f"文件解析失败: {extract_error}")
            return Response.error(f"文件解析失败: {str(extract_error)}")
        
        if not content or not content.strip():
            return Response.error("文件内容为空")
        
        logger.info(f"文件解析成功，内容长度: {len(content)}")
        
        # 5. 使用同步服务处理文档（MySQL + Milvus + 可选 LightRAG）
        sync_service = DataSyncService(collection_id, enable_graph)
        result = await sync_service.add_document(
            library_id=library_id,
            user_id=str(current_user),
            document_name=document_name,
            document_type="file",
            content=content,
            chunk_strategy=chunk_strategy,
            file_path=str(file_path),
            file_size=os.path.getsize(file_path)
        )
        
        if result.get("success"):
            logger.info(f"文档处理成功: {document_name}, 切块数: {result.get('total_chunks', 0)}")
            return Response.success(result)
        else:
            logger.error(f"文档处理失败: {result.get('error')}")
            return Response.error(result.get("error", "文档处理失败"))
        
    except Exception as e:
        logger.error(f"上传处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传处理失败: {str(e)}")
    
    finally:
        if db:
            db.close()
        # 可选：处理完成后删除临时文件
        # if file_path and file_path.exists():
        #     os.remove(file_path)



