from pydantic import BaseModel
from typing import Optional

class CrawlRequest(BaseModel):
    url: Optional[str] = None
    prefix: Optional[str] = None
    if_llm: Optional[bool] = None
    base_url: Optional[str] = True
    api_key: Optional[str] = True
    provider: Optional[str] = True
    model_id: Optional[str] = True
    user_id: Optional[str] = None
    title: Optional[str] = None
    collection_id: Optional[str] = None

class CrawlStatusRequest(BaseModel):
    collection_id: Optional[str] = None

class UploadDocRequest(BaseModel):
    user_id: Optional[str] = None
    collection_id: Optional[str] = None
    document_name: Optional[str] = None


class OSSProcessRequest(BaseModel):
    """OSS 文档处理请求"""
    oss_url: str  # OSS 文件 URL
    collection_id: str  # 知识库集合 ID
    document_name: str  # 文档名称
    library_id: int  # 知识库 ID（用于添加文档记录）
