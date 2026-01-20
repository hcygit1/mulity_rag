#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAGGraph 动态创建和管理
基于 collection_id 动态创建 RAGGraph 实例，支持实例池化复用
"""

import os
import time
import threading
from typing import Optional, Dict
from dotenv import load_dotenv

from backend.agent.graph import RAGGraph
from backend.config.log import setup_default_logging, get_logger
from backend.config.models import initialize_models

# 初始化日志
logger = get_logger(__name__)

# 特殊标识：无知识库模式
NO_COLLECTION_ID = "__no_collection__"


class RAGGraphPool:
    """RAGGraph 实例池
    
    基于 collection_id 缓存 RAGGraph 实例，避免每次请求都重新创建连接。
    支持：
    - 线程安全的实例获取和移除
    - 空闲超时自动清理
    - 手动移除（删除知识库时）
    """
    
    _instances: Dict[str, RAGGraph] = {}
    _last_access: Dict[str, float] = {}
    _lock: threading.Lock = threading.Lock()
    _max_idle_time: int = 3600  # 最大空闲时间（秒），默认1小时
    _cleanup_interval: int = 600  # 清理检查间隔（秒），默认10分钟
    _last_cleanup: float = 0
    
    @classmethod
    def get(cls, collection_id: str) -> RAGGraph:
        """获取或创建 RAGGraph 实例
        
        Args:
            collection_id: 知识库集合ID
            
        Returns:
            RAGGraph: 缓存的或新创建的实例
        """
        with cls._lock:
            current_time = time.time()
            
            # 定期清理空闲实例
            if current_time - cls._last_cleanup > cls._cleanup_interval:
                cls._cleanup_idle_instances(current_time)
                cls._last_cleanup = current_time
            
            # 缓存命中
            if collection_id in cls._instances:
                cls._last_access[collection_id] = current_time
                logger.debug(f"RAGGraph 实例池命中: collection_id={collection_id}")
                return cls._instances[collection_id]
            
            # 缓存未命中，创建新实例
            logger.info(f"RAGGraph 实例池未命中，创建新实例: collection_id={collection_id}")
            instance = _create_rag_graph(collection_id)
            cls._instances[collection_id] = instance
            cls._last_access[collection_id] = current_time
            
            logger.info(f"RAGGraph 实例池当前大小: {len(cls._instances)}")
            return instance
    
    @classmethod
    def remove(cls, collection_id: str) -> bool:
        """移除指定的 RAGGraph 实例
        
        在删除知识库时调用，释放相关资源。
        
        Args:
            collection_id: 知识库集合ID
            
        Returns:
            bool: 是否成功移除
        """
        with cls._lock:
            if collection_id in cls._instances:
                try:
                    # 触发实例的清理（__del__ 会关闭连接池）
                    instance = cls._instances.pop(collection_id)
                    cls._last_access.pop(collection_id, None)
                    
                    # 显式关闭连接池
                    if hasattr(instance, 'conn_pool') and instance.conn_pool:
                        instance.conn_pool.close()
                    
                    logger.info(f"RAGGraph 实例已从池中移除: collection_id={collection_id}")
                    return True
                except Exception as e:
                    logger.error(f"移除 RAGGraph 实例失败: collection_id={collection_id}, error={e}")
                    return False
            else:
                logger.debug(f"RAGGraph 实例不在池中: collection_id={collection_id}")
                return False
    
    @classmethod
    def _cleanup_idle_instances(cls, current_time: float) -> None:
        """清理空闲超时的实例（内部方法，需在锁内调用）"""
        expired_ids = [
            cid for cid, last_time in cls._last_access.items()
            if current_time - last_time > cls._max_idle_time
        ]
        
        for collection_id in expired_ids:
            try:
                instance = cls._instances.pop(collection_id, None)
                cls._last_access.pop(collection_id, None)
                
                if instance and hasattr(instance, 'conn_pool') and instance.conn_pool:
                    instance.conn_pool.close()
                
                logger.info(f"清理空闲 RAGGraph 实例: collection_id={collection_id}")
            except Exception as e:
                logger.error(f"清理空闲实例失败: collection_id={collection_id}, error={e}")
        
        if expired_ids:
            logger.info(f"空闲实例清理完成，清理数量: {len(expired_ids)}，剩余: {len(cls._instances)}")
    
    @classmethod
    def clear_all(cls) -> None:
        """清空所有实例（应用关闭时调用）"""
        with cls._lock:
            for collection_id, instance in cls._instances.items():
                try:
                    if hasattr(instance, 'conn_pool') and instance.conn_pool:
                        instance.conn_pool.close()
                except Exception as e:
                    logger.error(f"关闭实例连接池失败: collection_id={collection_id}, error={e}")
            
            count = len(cls._instances)
            cls._instances.clear()
            cls._last_access.clear()
            logger.info(f"RAGGraph 实例池已清空，共清理 {count} 个实例")
    
    @classmethod
    def get_stats(cls) -> Dict:
        """获取实例池统计信息"""
        with cls._lock:
            return {
                "pool_size": len(cls._instances),
                "collection_ids": list(cls._instances.keys()),
                "max_idle_time": cls._max_idle_time,
                "cleanup_interval": cls._cleanup_interval
            }


def _create_rag_graph(collection_id: str) -> RAGGraph:
    """
    基于 collection_id 创建 RAGGraph 实例（内部方法）
    
    Args:
        collection_id: 知识库集合ID，如果是 NO_COLLECTION_ID 则创建无知识库实例
        
    Returns:
        RAGGraph: 新创建的 RAGGraph 实例
        
    Raises:
        RuntimeError: 如果初始化失败
    """
    try:
        is_no_collection = (collection_id == NO_COLLECTION_ID)
        
        if is_no_collection:
            logger.info("创建无知识库 RAGGraph 实例（仅支持直接对话和联网搜索）...")
        else:
            logger.info(f"为 collection_id={collection_id} 创建 RAGGraph 实例...")
        
        # 初始化所有模型
        chat_model, embeddings_model = initialize_models()
        
        # 创建 RAGGraph 实例
        # 无知识库模式：不传 embedding_model，RAGGraph 内部会跳过 Milvus 初始化
        rag_graph = RAGGraph(
            llm=chat_model,
            embedding_model=None if is_no_collection else embeddings_model,
            enable_checkpointer=False,
            workspace=collection_id  # 使用collection_id作为workspace
        )
        
        if is_no_collection:
            logger.info("无知识库 RAGGraph 实例创建成功")
        else:
            logger.info(f"RAGGraph 实例创建成功，collection_id={collection_id}")
        return rag_graph
        
    except Exception as e:
        logger.error(f"RAGGraph 创建失败，collection_id={collection_id}: {str(e)}")
        logger.exception("详细错误信息:")
        raise RuntimeError(f"RAGGraph 创建失败: {str(e)}")


def get_rag_graph_for_collection(collection_id: str) -> RAGGraph:
    """
    为指定的 collection_id 获取 RAGGraph 实例
    
    使用实例池管理，相同 collection_id 会复用已有实例。
    
    Args:
        collection_id: 知识库集合ID
        
    Returns:
        RAGGraph: RAGGraph 实例
    """
    return RAGGraphPool.get(collection_id)


def remove_rag_graph_for_collection(collection_id: str) -> bool:
    """
    移除指定 collection_id 的 RAGGraph 实例
    
    在删除知识库时调用，释放相关资源。
    
    Args:
        collection_id: 知识库集合ID
        
    Returns:
        bool: 是否成功移除
    """
    return RAGGraphPool.remove(collection_id)