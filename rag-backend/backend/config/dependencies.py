"""
依赖注入函数
提供FastAPI路由的依赖项
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.config.jwt import verify_token
from backend.config.log import get_logger

logger = get_logger(__name__)

# HTTP Bearer认证方案
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> int:
    """
    获取当前登录用户ID
    
    从JWT token中解析用户ID，用于路由的依赖注入
    
    Args:
        credentials: HTTP Bearer认证凭证
        
    Returns:
        int: 用户ID
        
    Raises:
        HTTPException: token无效或过期时抛出401错误
    """
    token = credentials.credentials
    
    try:
        # 验证token并获取payload
        payload = verify_token(token)
        
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭证",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # JWT标准使用"sub"字段存储subject（用户ID）
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭证",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return int(user_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"token验证失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
            headers={"WWW-Authenticate": "Bearer"},
        )
