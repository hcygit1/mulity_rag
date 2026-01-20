import asyncio
import json
from datetime import datetime
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig, DefaultMarkdownGenerator, BrowserConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter
from crawl4ai.content_filter_strategy import LLMContentFilter, PruningContentFilter, RelevantContentFilter
from backend.param.crawl import CrawlRequest
from backend.service.document_processor import process_document
from backend.config.log import get_logger
from backend.config.redis import get_redis_client
from backend.config.database import DatabaseFactory
from backend.model.knowledge_library import KnowledgeLibrary


# 获取logger实例
logger = get_logger("crawl_service")

# 定义爬虫状态常量
CRAWL_STATUS_PROCESSING = "processing"
CRAWL_STATUS_COMPLETED = "completed"
CRAWL_STATUS_ERROR = "error"

async def initialize_collection_and_store(request: CrawlRequest):
    """初始化爬虫任务并开始爬取
    
    使用统一的 DocumentProcessor 处理文档，不再单独创建存储实例
    """
    # 初始化爬虫状态
    await init_crawl_status(request.collection_id)
    
    db = None
    library_id = None
    user_id = None
    enable_graph = False
    
    try:
        # 根据collection_id查找知识库，获取 enable_graph 设置
        db = DatabaseFactory.create_session()
        library = db.query(KnowledgeLibrary).filter(
            KnowledgeLibrary.collection_id == request.collection_id,
            KnowledgeLibrary.is_active == True
        ).first()
        
        if library:
            library_id = library.id
            user_id = library.user_id
            enable_graph = library.enable_graph
            logger.info(f"找到知识库: {library.title}, enable_graph: {enable_graph}")
        else:
            logger.warning(f"未找到collection_id为 {request.collection_id} 的知识库")
            
    except Exception as e:
        logger.error(f"查询知识库失败: {str(e)}")
    finally:
        if db:
            db.close()
    
    try:
        # 调用爬虫，使用统一的 DocumentProcessor 处理
        await crawl_doc(
            site=request.url,
            prefix=request.prefix,
            if_llm=request.if_llm,
            model_id=request.model_id,
            provider=request.provider,
            base_url=request.base_url,
            api_token=request.api_key,
            collection_id=request.collection_id,
            document_name=request.title or "爬虫文档",
            library_id=library_id,
            user_id=user_id,
            enable_graph=enable_graph
        )
        # 爬虫完成，更新状态为已完成
        await update_crawl_status(request.collection_id, CRAWL_STATUS_COMPLETED)
    except Exception as e:
        # 爬虫异常，更新状态为错误
        await update_crawl_status(request.collection_id, CRAWL_STATUS_ERROR, str(e))
        raise


async def init_crawl_status(collection_id: str):
    """初始化爬虫状态"""
    try:
        redis_client = await get_redis_client()
        status_data = {
            "status": CRAWL_STATUS_PROCESSING,
            "count": 0,
            "message": "爬虫任务开始",
            "start_time": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat()
        }
        await redis_client.set(f"crawl_status:{collection_id}", json.dumps(status_data))
        logger.info(f"初始化爬虫状态: {collection_id}")
    except Exception as e:
        logger.warning(f"Redis不可用，无法初始化爬虫状态: {str(e)}")


async def update_crawl_status(collection_id: str, status: str, message: str = None, count: int = None):
    """更新爬虫状态"""
    redis_client = await get_redis_client()
    
    # 获取当前状态
    current_status = await redis_client.get(f"crawl_status:{collection_id}")
    if current_status:
        status_data = json.loads(current_status)
    else:
        status_data = {
            "status": status,
            "count": 0,
            "message": message or "",
            "start_time": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat()
        }
    
    # 更新状态数据
    status_data["status"] = status
    status_data["last_update"] = datetime.now().isoformat()
    
    if message:
        status_data["message"] = message
    
    if count is not None:
        status_data["count"] = count
    
    await redis_client.set(f"crawl_status:{collection_id}", json.dumps(status_data))
    logger.info(f"更新爬虫状态: {collection_id} - {status}")


async def increment_crawl_count(collection_id: str):
    """增加爬虫计数"""
    redis_client = await get_redis_client()
    
    current_status = await redis_client.get(f"crawl_status:{collection_id}")
    if current_status:
        status_data = json.loads(current_status)
        status_data["count"] = status_data.get("count", 0) + 1
        status_data["last_update"] = datetime.now().isoformat()
        await redis_client.set(f"crawl_status:{collection_id}", json.dumps(status_data))


async def get_crawl_status(collection_id: str) -> dict:
    """
    获取爬虫状态
    
    Args:
        collection_id: 集合ID
        
    Returns:
        dict: 爬虫状态信息，包含status, count, message, start_time, last_update字段
              如果不存在该集合的状态，返回空字典
    """
    redis_client = await get_redis_client()
    
    status_data = await redis_client.get(f"crawl_status:{collection_id}")
    if status_data:
        return json.loads(status_data)
    else:
        return {}


async def get_all_crawl_status() -> dict:
    """
    获取所有爬虫状态
    
    Returns:
        dict: 所有爬虫状态，key为集合ID，value为状态信息
    """
    redis_client = await get_redis_client()
    
    # 获取所有以crawl_status:开头的key
    keys = await redis_client.keys("crawl_status:*")
    
    status_dict = {}
    for key in keys:
        # 提取集合ID
        collection_id = key.replace("crawl_status:", "")
        status_data = await redis_client.get(key)
        if status_data:
            status_dict[collection_id] = json.loads(status_data)
    
    return status_dict

async def process_crawl_result(
    result,
    collection_id: str,
    document_name: str,
    library_id: int,
    user_id: str,
    enable_graph: bool
):
    """处理单个爬虫结果"""
    try:
        logger.info(f"处理 URL: {result.url}")
        
        # 获取内容，优先使用 fit_markdown，其次 raw_markdown，最后 html/text
        content = None
        
        if result.markdown is not None:
            # 优先使用 fit_markdown（经过过滤的内容）
            if hasattr(result.markdown, 'fit_markdown') and result.markdown.fit_markdown:
                content = result.markdown.fit_markdown.strip()
                logger.info(f"使用 fit_markdown 内容，长度: {len(content)}")
            # 其次使用 raw_markdown（原始 markdown）
            elif hasattr(result.markdown, 'raw_markdown') and result.markdown.raw_markdown:
                content = result.markdown.raw_markdown.strip()
                logger.info(f"使用 raw_markdown 内容，长度: {len(content)}")
        
        # 如果 markdown 为空，尝试使用 html 内容
        if not content and hasattr(result, 'html') and result.html:
            content = result.html.strip()
            logger.info(f"使用 html 内容，长度: {len(content)}")
        
        # 如果还是为空，尝试使用 text 内容（纯文本）
        if not content and hasattr(result, 'text') and result.text:
            content = result.text.strip()
            logger.info(f"使用 text 内容，长度: {len(content)}")
        
        if not content:
            logger.warning(f"URL {result.url} 的所有内容都为空，跳过处理")
            return False
        
        # 使用同步服务或直接处理
        if library_id and user_id:
            # 使用同步服务（MySQL + Milvus + 可选 LightRAG）
            from backend.service.data_sync import DataSyncService
            sync_service = DataSyncService(collection_id, enable_graph)
            process_result = await sync_service.add_document(
                library_id=library_id,
                user_id=user_id,
                document_name=f"{document_name}_{result.url}",
                document_type="link",
                content=content,
                chunk_strategy="markdown",
                url=result.url
            )
        else:
            # 直接使用 DocumentProcessor（仅 Milvus + 可选 LightRAG）
            process_result = await process_document(
                content=content,
                document_name=f"{document_name}_{result.url}",
                collection_id=collection_id,
                chunk_strategy="markdown",
                enable_graph=enable_graph
            )
        
        if process_result.get("success"):
            logger.info(f"成功处理: {result.url}, 共 {process_result.get('total_chunks', 0)} 个分块")
            await increment_crawl_count(collection_id)
            return True
        else:
            error_msg = f"处理URL {result.url} 失败: {process_result.get('error')}"
            logger.error(error_msg)
            await update_crawl_status(collection_id, CRAWL_STATUS_ERROR, error_msg)
            return False
            
    except Exception as e:
        error_msg = f"处理URL {result.url} 时发生错误: {str(e)}"
        logger.error(error_msg)
        await update_crawl_status(collection_id, CRAWL_STATUS_ERROR, error_msg)
        return False


async def crawl_doc(
    site: str,
    prefix: str,
    if_llm: bool,
    model_id: str,
    provider: str,
    base_url: str,
    api_token: str,
    collection_id: str,
    document_name: str = "爬虫文档",
    library_id: int = None,
    user_id: str = None,
    enable_graph: bool = False
):
    """爬取网页并使用统一的 DocumentProcessor 处理
    
    Args:
        site: 爬取的网站URL
        prefix: URL前缀过滤
        if_llm: 是否使用LLM过滤内容
        model_id: LLM模型ID
        provider: LLM提供商
        base_url: LLM API地址
        api_token: LLM API密钥
        collection_id: 知识库集合ID
        document_name: 文档名称
        library_id: 知识库ID（用于同步服务）
        user_id: 用户ID（用于同步服务）
        enable_graph: 是否启用知识图谱
    """
    content_filter: RelevantContentFilter
    if if_llm:
        content_filter = LLMContentFilter(
            llm_config=LLMConfig(
                provider=f"{provider}/{model_id}",
                api_token=api_token,
                base_url=base_url
            ),
            instruction="""
            Focus on extracting the core educational content.
            Include:
            - Key concepts and explanations
            - Important code examples
            - Essential technical details
            Exclude:
            - Navigation elements
            - Sidebars
            - Footer content
            Format the output as clean markdown with proper code blocks and headers.
            """,
            chunk_token_threshold=4096,
            verbose=True
        )
    else:
        content_filter = PruningContentFilter(
            threshold=0.4,
            threshold_type="fixed"
        )
    
    md_generator = DefaultMarkdownGenerator(
        content_filter=content_filter,
        options={"ignore_links": True, "ignore_images": True}
    )

    browser_conf = BrowserConfig(
        browser_type="chromium",
        headless=True,
        text_mode=True
    )

    prefix_filter = URLPatternFilter(patterns=[f"{prefix}*"])
    filter_chain = FilterChain([prefix_filter])

    bfsstrategy = BFSDeepCrawlStrategy(
        max_depth=1,
        include_external=False,
        max_pages=1,
        filter_chain=filter_chain
    )

    config = CrawlerRunConfig(
        deep_crawl_strategy=bfsstrategy,
        scraping_strategy=LXMLWebScrapingStrategy(),
        verbose=True,
        stream=False,  # 关闭流式模式，直接返回结果
        markdown_generator=md_generator,
    )

    async with AsyncWebCrawler(config=browser_conf) as crawler:
        try:
            results = await crawler.arun(site, config=config)
            logger.info(f"爬虫返回结果类型: {type(results)}")
            
            # 检查是否是可迭代对象
            if results is None:
                logger.warning("爬虫返回 None")
                return
            
            # 处理不同类型的返回结果
            if hasattr(results, '__aiter__'):
                # 异步迭代器
                async for result in results:
                    await process_crawl_result(
                        result, collection_id, document_name,
                        library_id, user_id, enable_graph
                    )
            elif hasattr(results, '__iter__'):
                # 普通可迭代对象
                for result in results:
                    await process_crawl_result(
                        result, collection_id, document_name, 
                        library_id, user_id, enable_graph
                    )
            else:
                # 单个结果
                await process_crawl_result(
                    results, collection_id, document_name,
                    library_id, user_id, enable_graph
                )
                    
        except Exception as e:
            error_msg = f"爬虫运行时发生错误: {str(e)}"
            logger.error(error_msg)
            await update_crawl_status(collection_id, CRAWL_STATUS_ERROR, error_msg)
        
        logger.info("爬虫运行完成")



