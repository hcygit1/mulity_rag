"""
统一配置管理模块

所有环境变量在此集中定义，其他模块从这里导入使用。
使用 pydantic-settings 自动加载 .env 文件和环境变量。

使用方式:
    from backend.config.settings import settings
    
    # 直接访问配置
    api_key = settings.LLM_DASHSCOPE_API_KEY
    db_url = settings.DB_URL
"""
import os
from typing import Optional
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类
    
    所有配置项都可以通过环境变量或 .env 文件设置。
    环境变量名与属性名相同（大写）。
    """
    
    # ==================== 数据库配置 ====================
    DB_URL: str = ""
    
    # ==================== Redis 配置 ====================
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # ==================== JWT 配置 ====================
    JWT_SECRET_KEY: str = "secretsecretsecretsecretsecretsecret"
    JWT_ALGORITHM: str = "HS256"
    JWT_TOKEN_EXPIRES: int = 86400  # 秒，默认 24 小时
    
    # ==================== LLM 配置 (通义千问) ====================
    LLM_DASHSCOPE_API_KEY: Optional[str] = None
    LLM_DASHSCOPE_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_DASHSCOPE_CHAT_MODEL: str = "qwen-plus"
    
    # ==================== 向量模型配置 ====================
    VECTOR_DASHSCOPE_API_KEY: Optional[str] = None
    VECTOR_DASHSCOPE_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    VECTOR_DASHSCOPE_EMBEDDING_MODEL: str = "text-embedding-v4"
    EMBEDDING_DIM: int = 1024
    
    # ==================== Milvus 向量数据库配置 ====================
    MILVUS_URI: str = "http://localhost:19530"
    MILVUS_DB_NAME: str = "rag"
    MILVUS_TOKEN: Optional[str] = None
    MILVUS_COLLECTION_NAME: str = "chunks"
    
    # ==================== LightRAG 配置 ====================
    LIGHTRAG_GRAPH_STORAGE: str = "Neo4JStorage"
    LIGHTRAG_KV_STORAGE: str = "PGKVStorage"
    LIGHTRAG_DOC_STATUS_STORAGE: str = "PGDocStatusStorage"
    LIGHTRAG_VECTOR_STORAGE: str = "MilvusVectorDBStorage"
    
    # ==================== PostgreSQL 配置 (LangGraph checkpoint) ====================
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DATABASE: str = "rag_checkpoint"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "123456"
    
    # ==================== COS 对象存储配置 ====================
    COS_SECRET_ID: Optional[str] = None
    COS_SECRET_KEY: Optional[str] = None
    COS_REGION: str = "ap-shanghai"
    COS_BUCKET_NAME: Optional[str] = None
    
    # ==================== Tavily 联网搜索配置 ====================
    TAVILY_API_KEY: Optional[str] = None
    
    # ==================== MinerU 文档解析配置 ====================
    MINERU_API_URL: Optional[str] = None
    MINERU_API_KEY: Optional[str] = None
    
    # ==================== 日志配置 ====================
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    
    # ==================== Pydantic Settings 配置 ====================
    model_config = SettingsConfigDict(
        # 从 backend/.env 文件加载
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        # 忽略未定义的环境变量
        extra="ignore",
        # 环境变量优先级高于 .env 文件
        env_nested_delimiter="__",
    )
    
    # ==================== 便捷属性 ====================
    @property
    def jwt_token_expire_hours(self) -> int:
        """JWT token 过期时间（小时）"""
        return self.JWT_TOKEN_EXPIRES // 3600
    
    @property
    def postgres_config(self) -> dict:
        """PostgreSQL 连接配置字典"""
        return {
            "host": self.POSTGRES_HOST,
            "port": self.POSTGRES_PORT,
            "database": self.POSTGRES_DATABASE,
            "user": self.POSTGRES_USER,
            "password": self.POSTGRES_PASSWORD,
        }


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（带缓存）
    
    使用 lru_cache 确保配置只加载一次。
    """
    return Settings()


# 全局配置实例，便于直接导入使用
settings = get_settings()
