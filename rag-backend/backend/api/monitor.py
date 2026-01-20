"""
系统监控API
提供数据库连接池等系统状态监控
"""
from fastapi import APIRouter, Depends
from backend.param.common import Response
from backend.config.database import DatabaseFactory
from backend.config.dependencies import get_current_user
from backend.config.log import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/monitor",
    tags=["MONITOR"]
)


@router.get("/db-pool")
async def get_db_pool_status(current_user: int = Depends(get_current_user)):
    """
    获取数据库连接池状态
    
    Returns:
        Response: 包含连接池状态信息
    """
    try:
        engine = DatabaseFactory.get_engine()
        pool = engine.pool
        
        status = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total_connections": pool.size() + pool.overflow()
        }
        
        logger.info(f"数据库连接池状态: {status}")
        return Response.success(status)
        
    except Exception as e:
        logger.error(f"获取数据库连接池状态失败: {str(e)}")
        return Response.error(f"获取连接池状态失败: {str(e)}")
