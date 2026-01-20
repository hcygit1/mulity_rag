from fastapi import APIRouter, HTTPException
from backend.param.common import Response
from backend.service.crawl import get_crawl_status, initialize_collection_and_store
from backend.config.log import get_logger
from backend.config.database import DatabaseFactory
from backend.config.settings import settings
from backend.model.knowledge_library import KnowledgeLibrary
from backend.param.crawl import CrawlRequest, UploadDocRequest, OSSProcessRequest
from backend.config.oss import get_presigned_url_for_upload, get_presigned_url_for_download
from backend.rag.chunks.document_extraction import DocumentExtractor
from backend.service.data_sync import DataSyncService
import asyncio


logger = get_logger(__name__)

router = APIRouter(
    prefix="/crawl",
    tags=["CRAWL"]
)

def run_task(request: CrawlRequest):
    asyncio.run(initialize_collection_and_store(request))

@router.post('/site')
async def crawl_site_and_store(request: CrawlRequest) -> Response:
    """
    触发指定URL的网站爬取并存储到数据库
    
    Args:
        request: 包含爬取参数的请求体
        
    Returns:
        Response: 包含操作结果的响应
    """
    try:
        logger.info(f"触发爬取任务: {request.url}")
        
        # 初始化集合并存储数据,走异步调用非等待，直接返回
        asyncio.create_task(initialize_collection_and_store(request))
        
        return Response.success_with_msg({
            "collection_id": request.collection_id,
        }, f"接收到爬取任务: {request.url}")
        
    except Exception as e:
        logger.error(f"触发爬取任务异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"触发爬取任务失败: {str(e)}")

@router.post('/get-upload-url')
async def get_oss_upload_url(request: UploadDocRequest) -> Response:
    """
    获取OSS上传签名URL
    
    Args:
        document_name: 文档名称
        
    Returns:
        Response: 包含上传签名URL的响应
    """
    try:
        logger.info(f"获取OSS上传签名URL")
        
        # 调用服务层获取上传签名URL
        upload_url = get_presigned_url_for_upload(bucket="ragagent-file", key=request.document_name)
        
        if upload_url:
            logger.info(f"成功获取OSS上传签名URL")
            #logger.info(f"上传URL: {upload_url}")
            return Response.success(upload_url["url"])
        else:
            logger.warning(f"获取OSS上传签名URL失败")
            return Response.success({
                "message": "获取OSS上传签名URL失败"
            })
            
    except Exception as e:
        logger.error(f"获取OSS上传签名URL异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取OSS上传签名URL失败: {str(e)}")

@router.get('/status/{collection_name}')
async def get_crawl_status_api(collection_name: str) -> Response:
    """
    获取指定集合的爬虫状态
    
    Args:
        collection_name: 集合名称
        
    Returns:
        Response: 包含爬虫状态信息的响应
    """
    try:
        logger.info(f"查询集合 {collection_name} 的爬虫状态")
        
        # 验证参数
        if not collection_name or not collection_name.strip():
            raise HTTPException(status_code=400, detail="集合名称不能为空")
        
        # 调用服务层获取状态
        status_data = await get_crawl_status(collection_name.strip())
        
        if status_data:
            logger.info(f"成功获取集合 {collection_name} 的爬虫状态")
            return Response.success({
                "collection_name": collection_name,
                "status": status_data
            })
        else:
            logger.warning(f"集合 {collection_name} 的爬虫状态不存在")
            return Response.success({
                "collection_name": collection_name,
                "status": {},
                "message": "该集合的爬虫状态不存在"
            })
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取爬虫状态接口异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post('/process-oss-document')
async def process_oss_document(request: OSSProcessRequest) -> Response:
    """
    处理 OSS 上传的文档：使用 MinerU 解析 PDF 后存储到 Milvus + 可选 LightRAG
    
    Args:
        request: OSS 文档处理请求
        
    Returns:
        Response: 处理结果
    """
    db = None
    try:
        logger.info(f"开始处理 OSS 文档: {request.document_name}, URL: {request.oss_url}")
        
        # 1. 获取知识库的 enable_graph 设置
        db = DatabaseFactory.create_session()
        library = db.query(KnowledgeLibrary).filter(
            KnowledgeLibrary.id == request.library_id,
            KnowledgeLibrary.is_active == True
        ).first()
        
        if not library:
            return Response.error("知识库不存在")
        
        enable_graph = library.enable_graph
        user_id = library.user_id
        db.close()
        db = None
        
        # 2. 生成带签名的下载 URL（MinerU 需要能访问文件）
        from backend.config.oss import get_presigned_url_for_download
        # 从 oss_url 提取 key（文件路径）
        # URL 格式: https://bucket.cos.region.myqcloud.com/key
        from urllib.parse import urlparse, unquote
        parsed_url = urlparse(request.oss_url)
        file_key = unquote(parsed_url.path.lstrip('/'))  # 去掉开头的 /
        
        bucket = settings.COS_BUCKET_NAME
        signed_url_result = get_presigned_url_for_download(bucket, file_key, expire_seconds=3600)
        signed_url = signed_url_result['url']
        
        logger.info(f"生成签名下载 URL: {signed_url[:100]}...")
        
        # 3. 使用 MinerU 解析 PDF（使用签名 URL）
        extractor = DocumentExtractor()
        try:
            doc_content = extractor.read_document(signed_url, pdf_extract_method="mineru")
            content = doc_content.content
        except Exception as extract_error:
            logger.error(f"MinerU 解析失败: {extract_error}")
            return Response.error(f"文档解析失败: {str(extract_error)}")
        
        if not content or not content.strip():
            return Response.error("文档内容为空")
        
        logger.info(f"MinerU 解析成功，内容长度: {len(content)}")
        
        # 4. 使用同步服务处理文档（MySQL + Milvus + 可选 LightRAG）
        sync_service = DataSyncService(request.collection_id, enable_graph)
        result = await sync_service.add_document(
            library_id=request.library_id,
            user_id=user_id,
            document_name=request.document_name,
            document_type="file",
            content=content,
            chunk_strategy="markdown",  # OSS 上传固定使用 markdown 策略
            url=request.oss_url
        )
        
        if result.get("success"):
            logger.info(f"OSS 文档处理成功: {request.document_name}, 切块数: {result.get('total_chunks', 0)}")
            return Response.success(result)
        else:
            logger.error(f"OSS 文档处理失败: {result.get('error')}")
            return Response.error(result.get("error", "文档处理失败"))
        
    except Exception as e:
        logger.error(f"处理 OSS 文档异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理 OSS 文档失败: {str(e)}")
    
    finally:
        if db:
            db.close()
