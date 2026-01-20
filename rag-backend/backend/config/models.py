#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型初始化配置模块
包含大模型和向量模型的初始化逻辑
"""

import os
from typing import Tuple

from backend.agent.models import (
    load_chat_model,
    load_embeddings,
    register_embeddings_provider,
    register_model_provider
)
from backend.config.log import get_logger
from backend.config.settings import settings
from langchain_qwq import ChatQwen

# 初始化日志
logger = get_logger(__name__)


def initialize_chat_model():
    """
    初始化大模型 (通义千问)

    Returns:
        chat_model: 初始化后的聊天模型实例
    """
    logger.info("注册大模型提供商...")
    register_model_provider(
        provider_name="qwen",
        chat_model=ChatQwen
    )

    logger.info("加载大模型...")
    api_key = settings.LLM_DASHSCOPE_API_KEY
    api_base = settings.LLM_DASHSCOPE_API_BASE
    model_name = settings.LLM_DASHSCOPE_CHAT_MODEL

    if not api_key:
        raise ValueError("LLM_DASHSCOPE_API_KEY 环境变量未设置")

    # 设置环境变量以供模型加载使用
    os.environ["DASHSCOPE_API_KEY"] = api_key
    os.environ["DASHSCOPE_API_BASE"] = api_base

    chat_model = load_chat_model(f"qwen:{model_name}")
    logger.info(f"大模型加载成功: {type(chat_model)}")

    return chat_model


def initialize_embeddings_model():
    """
    初始化向量模型 (阿里云)

    Returns:
        embeddings_model: 初始化后的向量模型实例

    Raises:
        ValueError: 当VECTOR_DASHSCOPE_API_KEY环境变量未设置时
    """
    logger.info("注册向量模型提供商...")
    api_base = settings.VECTOR_DASHSCOPE_API_BASE
    embedding_model = settings.VECTOR_DASHSCOPE_EMBEDDING_MODEL

    register_embeddings_provider(
        provider_name="ali",
        embeddings_model="openai",
        base_url=api_base
    )

    logger.info("加载向量模型...")
    api_key = settings.VECTOR_DASHSCOPE_API_KEY
    if not api_key:
        raise ValueError("VECTOR_DASHSCOPE_API_KEY 环境变量未设置")

    embeddings_model = load_embeddings(
        f"ali:{embedding_model}",
        api_key=api_key,
        check_embedding_ctx_length=False,
        dimensions=1536
    )
    logger.info(f"向量模型加载成功: {type(embeddings_model)}")

    return embeddings_model


def initialize_models() -> Tuple:
    """
    初始化所有模型
    
    Returns:
        Tuple: (chat_model, embeddings_model) 包含聊天模型和向量模型的元组
    """
    logger.info("开始初始化所有模型...")
    
    # 初始化大模型
    chat_model = initialize_chat_model()
    
    # 初始化向量模型
    embeddings_model = initialize_embeddings_model()
    
    logger.info("所有模型初始化完成")
    return chat_model, embeddings_model


# 别名函数，保持向后兼容（原 config/embedding.py 中的函数）
def get_embedding_model():
    """
    获取向量模型实例
    
    这是 initialize_embeddings_model() 的别名，保持向后兼容。
    
    Returns:
        embeddings_model: 向量模型实例
    """
    return initialize_embeddings_model()