"""
JWT 认证配置模块

提供 JWT token 的创建和验证功能。
密码哈希功能已移至 service/auth.py，使用 bcrypt 实现。
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt

from backend.config.settings import settings


def create_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建token（单token机制）"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_token_expire_hours)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    """验证token"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None