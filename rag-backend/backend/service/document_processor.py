#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一文档处理服务
负责文档的切块和存储（Milvus + LightRAG）
"""
from typing import Dict, Any, Optional, List
from backend.rag.storage.milvus_storage import MilvusStorage
from backend.rag.storage.lightrag_storage import LightRAGStorage
from backend.rag.chunks.chunks import TextChunker
from backend.rag.chunks.models import ChunkConfig, ChunkStrategy, DocumentContent
from backend.config.models import get_embedding_model
from backend.config.log import get_logger

logger = get_logger(__name__)

# 单个分块的最大字符数（约 1000-1500 token，留足够余量给 embedding 模型）
MAX_CHUNK_SIZE = 4000


class DocumentProcessor:
    """统一文档处理器
    
    负责将文档内容切块并存储到 Milvus 和 LightRAG
    支持多种切块策略：markdown、recursive、semantic、character
    """
    
    # 切块策略映射
    STRATEGY_MAP = {
        "markdown": ChunkStrategy.MARKDOWN_HEADER,
        "recursive": ChunkStrategy.RECURSIVE,
        "semantic": ChunkStrategy.SEMANTIC,
        "character": ChunkStrategy.CHARACTER,
    }
    
    def __init__(self, collection_id: str, embedding_model=None, enable_graph: bool = False):
        """初始化文档处理器
        
        Args:
            collection_id: 知识库集合ID
            embedding_model: 嵌入模型（可选，默认从配置获取）
            enable_graph: 是否启用知识图谱（存储到 LightRAG）
        """
        self.collection_id = collection_id
        self.embedding_model = embedding_model or get_embedding_model()
        self.enable_graph = enable_graph
        
        # 初始化 Milvus 存储（始终需要）
        self.milvus_storage = MilvusStorage(
            embedding_function=self.embedding_model,
            collection_name=collection_id,
        )
        
        # 初始化 LightRAG 存储（仅当启用图谱时）
        self.lightrag_storage = LightRAGStorage(workspace=collection_id) if enable_graph else None
        
        # 初始化切块器
        self.chunker = TextChunker(embeddings_model=self.embedding_model)
        
        logger.info(f"DocumentProcessor 初始化完成，collection_id: {collection_id}, enable_graph: {enable_graph}")
    
    async def process(
        self,
        content: str,
        document_name: str,
        chunk_strategy: str = "markdown",
        chunk_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """处理文档：切块并存储
        
        Args:
            content: 文档文本内容
            document_name: 文档名称
            chunk_strategy: 切块策略 (markdown/recursive/semantic/character)
            chunk_config: 切块配置参数（可选）
            
        Returns:
            处理结果，包含切块数量、存储状态等
        """
        if not content or not content.strip():
            logger.warning(f"文档内容为空: {document_name}")
            return {
                "success": False,
                "error": "文档内容为空",
                "document_name": document_name
            }
        
        try:
            logger.info(f"开始处理文档: {document_name}, 策略: {chunk_strategy}")
            
            # 1. 切块
            chunk_result = await self._chunk_document(
                content, document_name, chunk_strategy, chunk_config
            )
            
            if not chunk_result.chunks:
                logger.warning(f"文档切块结果为空: {document_name}")
                return {
                    "success": False,
                    "error": "文档切块结果为空",
                    "document_name": document_name
                }
            
            logger.info(f"文档切块完成: {document_name}, 共 {len(chunk_result.chunks)} 个分块")
            
            # 2. 存储到 Milvus（自定义切块，用于向量+BM25检索）
            milvus_result = await self._store_to_milvus(chunk_result)
            
            # 3. 存储到 LightRAG（仅当启用图谱时）
            lightrag_result = None
            if self.enable_graph:
                lightrag_result = await self._store_to_lightrag(content, document_name)
            
            return {
                "success": True,
                "document_name": document_name,
                "collection_id": self.collection_id,
                "chunk_strategy": chunk_strategy,
                "total_chunks": len(chunk_result.chunks),
                "enable_graph": self.enable_graph,
                "milvus_result": milvus_result,
                "lightrag_result": lightrag_result
            }
            
        except Exception as e:
            logger.error(f"文档处理失败: {document_name}, 错误: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "document_name": document_name
            }
    
    async def _chunk_document(
        self,
        content: str,
        document_name: str,
        chunk_strategy: str,
        chunk_config: Optional[Dict[str, Any]] = None
    ):
        """切块文档
        
        Args:
            content: 文档内容
            document_name: 文档名称
            chunk_strategy: 切块策略
            chunk_config: 切块配置
            
        Returns:
            ChunkResult 对象
        """
        # 获取切块策略
        strategy = self.STRATEGY_MAP.get(chunk_strategy, ChunkStrategy.MARKDOWN_HEADER)
        
        # 构建切块配置
        config_params = {"strategy": strategy}
        
        # 根据策略设置默认参数
        if strategy == ChunkStrategy.RECURSIVE:
            config_params.update({
                "chunk_size": 500,
                "chunk_overlap": 50,
            })
        elif strategy == ChunkStrategy.CHARACTER:
            config_params.update({
                "chunk_size": 500,
                "chunk_overlap": 50,
                "separator": "\n\n",
            })
        elif strategy == ChunkStrategy.SEMANTIC:
            config_params.update({
                "breakpoint_threshold_type": "percentile",
                "breakpoint_threshold_amount": 90,
            })
        # MARKDOWN_HEADER 使用默认配置
        
        # 合并用户自定义配置
        if chunk_config:
            config_params.update(chunk_config)
        
        config = ChunkConfig(**config_params)
        document = DocumentContent(content=content, document_name=document_name)
        
        # 执行切块
        chunk_result = self.chunker.chunk_document(document, config)
        
        # Fallback 逻辑：检查是否有超大分块需要再次分割
        if chunk_result.chunks:
            chunk_result = self._ensure_chunk_size_limit(chunk_result, document_name)
        
        return chunk_result
    
    def _ensure_chunk_size_limit(self, chunk_result, document_name: str):
        """确保所有分块不超过最大限制
        
        如果存在超大分块，使用 recursive 策略再次分割
        
        Args:
            chunk_result: 原始切块结果
            document_name: 文档名称
            
        Returns:
            处理后的 ChunkResult
        """
        # 检查是否有超大分块（注意：LangChain Document 使用 page_content 属性）
        for i, c in enumerate(chunk_result.chunks):
            logger.info(f"分块 {i}: 长度 {len(c.page_content)} 字符")
        
        oversized_chunks = [c for c in chunk_result.chunks if len(c.page_content) > MAX_CHUNK_SIZE]
        
        if not oversized_chunks:
            logger.info(f"没有超大分块，无需二次分割")
            return chunk_result
        
        logger.info(f"检测到 {len(oversized_chunks)} 个超大分块（>{MAX_CHUNK_SIZE}字符），进行二次分割")
        
        # 构建 recursive 切块配置
        recursive_config = ChunkConfig(
            strategy=ChunkStrategy.RECURSIVE,
            chunk_size=500,
            chunk_overlap=50,
        )
        
        # 处理所有分块
        new_chunks = []
        for chunk in chunk_result.chunks:
            if len(chunk.page_content) > MAX_CHUNK_SIZE:
                # 超大分块：使用 recursive 再次分割
                logger.info(f"正在分割超大分块，长度: {len(chunk.page_content)} 字符")
                sub_document = DocumentContent(content=chunk.page_content, document_name=document_name)
                sub_result = self.chunker.chunk_document(sub_document, recursive_config)
                
                logger.info(f"超大分块({len(chunk.page_content)}字符) 被分割为 {len(sub_result.chunks)} 个子分块")
                new_chunks.extend(sub_result.chunks)
            else:
                # 正常分块：保留
                new_chunks.append(chunk)
        
        # 更新 chunk_result
        chunk_result.chunks = new_chunks
        logger.info(f"二次分割完成，最终分块数: {len(new_chunks)}")
        
        return chunk_result
    
    async def _store_to_milvus(self, chunk_result) -> Dict[str, Any]:
        """存储切块到 Milvus
        
        Args:
            chunk_result: 切块结果
            
        Returns:
            存储结果
        """
        try:
            result = self.milvus_storage.store_chunks_batch([chunk_result])
            logger.info(f"Milvus 存储成功: {result.get('total_chunks', 0)} 个分块")
            return {
                "success": True,
                "total_chunks": result.get("total_chunks", 0),
                "collection_name": self.collection_id
            }
        except Exception as e:
            logger.error(f"Milvus 存储失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _store_to_lightrag(self, content: str, document_name: str) -> Dict[str, Any]:
        """存储原文到 LightRAG（让 LightRAG 自己处理实体抽取和图构建）
        
        LightRAG 会自动完成：
        1. 文本切块
        2. 实体抽取 → Neo4j
        3. 关系抽取 → Neo4j
        4. 向量存储 → Milvus (workspace_entities/relationships/chunks)
        
        Args:
            content: 文档原文内容
            document_name: 文档名称
            
        Returns:
            存储结果
        """
        try:
            # 存储原文到 LightRAG，让它自己处理实体抽取
            await self.lightrag_storage.insert_text(content)
            
            logger.info(f"LightRAG 存储成功: {document_name}, 内容长度: {len(content)}")
            return {
                "success": True,
                "document_name": document_name,
                "content_length": len(content),
                "workspace": self.collection_id
            }
        except Exception as e:
            logger.error(f"LightRAG 存储失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def finalize(self):
        """清理资源"""
        if self.lightrag_storage:
            try:
                await self.lightrag_storage.finalize()
            except Exception as e:
                logger.warning(f"清理 LightRAG 资源失败: {str(e)}")


async def process_document(
    content: str,
    document_name: str,
    collection_id: str,
    chunk_strategy: str = "markdown",
    chunk_config: Optional[Dict[str, Any]] = None,
    enable_graph: bool = False
) -> Dict[str, Any]:
    """便捷函数：处理单个文档
    
    Args:
        content: 文档文本内容
        document_name: 文档名称
        collection_id: 知识库集合ID
        chunk_strategy: 切块策略
        chunk_config: 切块配置
        enable_graph: 是否启用知识图谱
        
    Returns:
        处理结果
    """
    processor = DocumentProcessor(collection_id, enable_graph=enable_graph)
    try:
        result = await processor.process(
            content=content,
            document_name=document_name,
            chunk_strategy=chunk_strategy,
            chunk_config=chunk_config
        )
        return result
    finally:
        await processor.finalize()
