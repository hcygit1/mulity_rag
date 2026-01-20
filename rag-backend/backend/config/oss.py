"""
腾讯云 COS 对象存储配置
"""
from datetime import datetime, timedelta
from qcloud_cos import CosConfig, CosS3Client
from threading import Lock

from backend.config.settings import settings


class CosClientFactory:
    _instance = None
    _lock = Lock()

    @classmethod
    def get_client(cls) -> CosS3Client:
        """
        获取 COS Client 的单例实例
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    config = CosConfig(
                        Region=settings.COS_REGION,
                        SecretId=settings.COS_SECRET_ID,
                        SecretKey=settings.COS_SECRET_KEY,
                    )
                    cls._instance = CosS3Client(config)
        
        return cls._instance


def get_presigned_url_for_upload(bucket: str, key: str, expire_seconds: int = 3600):
    """
    生成预签名上传 URL
    
    Args:
        bucket: 存储桶名称 (格式: bucket-appid, 如 ragagent-file-1234567890)
        key: 对象键（文件路径）
        expire_seconds: 过期时间（秒）
    """
    client = CosClientFactory.get_client()
    
    url = client.get_presigned_url(
        Method='PUT',
        Bucket=bucket,
        Key=key,
        Expired=expire_seconds
    )
    
    expiration = datetime.utcnow() + timedelta(seconds=expire_seconds)
    
    return {
        "method": "PUT",
        "expiration": expiration.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "url": url,
        "signed_headers": {}
    }


def get_presigned_url_for_download(bucket: str, key: str, expire_seconds: int = 3600):
    """
    生成预签名下载 URL
    
    Args:
        bucket: 存储桶名称 (格式: bucket-appid, 如 ragagent-file-1234567890)
        key: 对象键（文件路径）
        expire_seconds: 过期时间（秒）
    """
    client = CosClientFactory.get_client()
    
    url = client.get_presigned_url(
        Method='GET',
        Bucket=bucket,
        Key=key,
        Expired=expire_seconds
    )
    
    expiration = datetime.utcnow() + timedelta(seconds=expire_seconds)
    
    return {
        'method': 'GET',
        'expiration': expiration.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        'url': url
    }


if __name__ == "__main__":
    # 使用示例
    # bucket 格式: 存储桶名-APPID，如 ragagent-file-1234567890
    result = get_presigned_url_for_upload(bucket="your-bucket-1234567890", key="test.md")
    print(result)
