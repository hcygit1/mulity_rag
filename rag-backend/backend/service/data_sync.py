#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据同步服务
负责 MySQL、Milvus、LightRAG 之间的数据一致性
"""
from typing import Dict, Any, Optional
from backend.config.database import DatabaseFactory
from backend.config.models import get_embedding_model
from backend.config.log import get_logger
from backend.model.knowledge_library import KnowledgeLibrary, KnowledgeDocument
from backend.rag.storage.milvus_storage import MilvusStorage
from backend.rag.storage.lightrag_storage import LightRAGStorage
from backend.service.document_processor import DocumentProcessor

logger = get_logger(__name__)


class DataSyncService:
    """跨存储数据同步服务
    
    负责协调 MySQL、Milvus、LightRAG 之间的数据操作，
    确保数据一致性。
    """
    
    def __init__(self, collection_id: str, enable_graph: bool = False):
        """初始化同步服务
        
        Args:
            collection_id: 知识库集合ID
            enable_graph: 是否启用知识图谱
        """
        self.collection_id = collection_id
        self.enable_graph = enable_graph
        self._milvus = None
        self._lightrag = None
    
    @property
    def milvus(self) -> MilvusStorage:
        """延迟初始化 Milvus 存储"""
        if not self._milvus:
            self._milvus = MilvusStorage(
                embedding_function=get_embedding_model(),
                collection_name=self.collection_id
            )
        return self._milvus
    
    @property
    def lightrag(self) -> LightRAGStorage:
        """延迟初始化 LightRAG 存储"""
        if not self._lightrag:
            self._lightrag = LightRAGStorage(workspace=self.collection_id)
        return self._lightrag

    async def add_document(
        self,
        library_id: int,
        user_id: str,
        document_name: str,
        document_type: str,
        content: str,
        chunk_strategy: str = "markdown",
        url: str = None,
        file_path: str = None,
        file_size: int = None
    ) -> Dict[str, Any]:
        """
        添加文档（MySQL + Milvus + 可选 LightRAG）
        
        流程：
        1. MySQL 添加文档记录 (is_processed=False)
        2. DocumentProcessor 存储到 Milvus + 可选 LightRAG
        3. MySQL 更新 is_processed=True
        4. 失败则删除 MySQL 记录
        
        Args:
            library_id: 知识库ID
            user_id: 用户ID
            document_name: 文档名称
            document_type: 文档类型 (link/file)
            content: 文档内容
            chunk_strategy: 切块策略
            url: 文档URL（可选）
            file_path: 文件路径（可选）
            file_size: 文件大小（可选）
            
        Returns:
            处理结果
        """
        db = None
        document = None
        
        try:
            db = DatabaseFactory.create_session()
            
            # 1. MySQL: 添加文档记录
            document = KnowledgeDocument(
                library_id=library_id,
                name=document_name,
                type=document_type,
                url=url,
                file_path=file_path,
                file_size=file_size,
                is_processed=False
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            
            logger.info(f"MySQL 添加文档记录: {document_name}, ID: {document.id}")
            
            # 2. 处理文档（Milvus + 可选 LightRAG）
            processor = DocumentProcessor(
                collection_id=self.collection_id,
                enable_graph=self.enable_graph
            )
            
            try:
                result = await processor.process(
                    content=content,
                    document_name=document_name,
                    chunk_strategy=chunk_strategy
                )
            finally:
                await processor.finalize()
            
            if not result.get("success"):
                raise Exception(result.get("error", "文档处理失败"))
            
            # 3. MySQL: 更新处理状态
            document.is_processed = True
            db.commit()
            
            logger.info(f"文档同步完成: {document_name}, 切块数: {result.get('total_chunks', 0)}")
            
            return {
                "success": True,
                "document_id": document.id,
                "document_name": document_name,
                **result
            }
            
        except Exception as e:
            logger.error(f"添加文档失败: {str(e)}")
            
            # 回滚：删除 MySQL 记录
            if document and document.id and db:
                try:
                    db.delete(document)
                    db.commit()
                    logger.info(f"回滚：已删除 MySQL 文档记录 {document.id}")
                except Exception as rollback_error:
                    logger.error(f"回滚失败: {str(rollback_error)}")
            
            return {"success": False, "error": str(e)}
        
        finally:
            if db:
                db.close()

    async def delete_document(
        self,
        document_id: int,
        user_id: str
    ) -> Dict[str, Any]:
        """
        删除文档（MySQL + Milvus）
        
        注：启用图谱的知识库不允许删除单个文档
        
        Args:
            document_id: 文档ID
            user_id: 用户ID
            
        Returns:
            删除结果
        """
        db = None
        
        try:
            db = DatabaseFactory.create_session()
            
            # 1. 查询文档和知识库
            document = db.query(KnowledgeDocument).join(KnowledgeLibrary).filter(
                KnowledgeDocument.id == document_id,
                KnowledgeLibrary.user_id == user_id,
                KnowledgeLibrary.is_active == True
            ).first()
            
            if not document:
                return {"success": False, "error": "文档不存在或无权限"}
            
            library = document.library
            
            # 2. 检查是否启用图谱
            if library.enable_graph:
                return {
                    "success": False,
                    "error": "该知识库已启用知识图谱，不支持删除单个文档。如需清理，请删除整个知识库。"
                }
            
            document_name = document.name
            
            # 3. Milvus: 按文档名删除
            milvus_result = self.milvus.delete_by_document_name(document_name)
            logger.info(f"Milvus 删除结果: {milvus_result}")
            
            # 4. MySQL: 删除记录
            db.delete(document)
            db.commit()
            
            logger.info(f"文档删除完成: {document_name}")
            
            return {
                "success": True,
                "document_id": document_id,
                "document_name": document_name,
                "milvus_result": milvus_result
            }
            
        except Exception as e:
            logger.error(f"删除文档失败: {str(e)}")
            return {"success": False, "error": str(e)}
        
        finally:
            if db:
                db.close()

    async def delete_library(
        self,
        library_id: int,
        user_id: str
    ) -> Dict[str, Any]:
        """
        删除知识库（MySQL + Milvus + LightRAG）
        
        Args:
            library_id: 知识库ID
            user_id: 用户ID
            
        Returns:
            删除结果
        """
        db = None
        
        try:
            db = DatabaseFactory.create_session()
            
            # 1. 查询知识库
            library = db.query(KnowledgeLibrary).filter(
                KnowledgeLibrary.id == library_id,
                KnowledgeLibrary.user_id == user_id,
                KnowledgeLibrary.is_active == True
            ).first()
            
            if not library:
                return {"success": False, "error": "知识库不存在或无权限"}
            
            collection_id = library.collection_id
            enable_graph = library.enable_graph
            library_title = library.title
            
            # 2. Milvus: 删除集合
            milvus_result = self.milvus.drop_collection()
            logger.info(f"Milvus 删除集合结果: {milvus_result}")
            
            # 3. LightRAG: 删除 workspace（如果启用了图谱）
            lightrag_result = None
            if enable_graph:
                try:
                    await self.lightrag.drop_workspace()
                    lightrag_result = {"success": True, "workspace": collection_id}
                    logger.info(f"LightRAG 删除 workspace: {collection_id}")
                except Exception as e:
                    lightrag_result = {"success": False, "error": str(e)}
                    logger.error(f"LightRAG 删除失败: {str(e)}")
            
            # 4. MySQL: 物理删除知识库（级联删除关联文档）
            db.delete(library)
            db.commit()
            
            logger.info(f"知识库物理删除完成: {library_title}")
            
            return {
                "success": True,
                "library_id": library_id,
                "library_title": library_title,
                "milvus_result": milvus_result,
                "lightrag_result": lightrag_result
            }
            
        except Exception as e:
            logger.error(f"删除知识库失败: {str(e)}")
            return {"success": False, "error": str(e)}
        
        finally:
            if db:
                db.close()


# 便捷函数
async def sync_add_document(
    collection_id: str,
    enable_graph: bool,
    library_id: int,
    user_id: str,
    document_name: str,
    document_type: str,
    content: str,
    chunk_strategy: str = "markdown",
    **kwargs
) -> Dict[str, Any]:
    """便捷函数：添加文档"""
    service = DataSyncService(collection_id, enable_graph)
    return await service.add_document(
        library_id=library_id,
        user_id=user_id,
        document_name=document_name,
        document_type=document_type,
        content=content,
        chunk_strategy=chunk_strategy,
        **kwargs
    )
