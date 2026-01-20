from fastapi import APIRouter, Depends, Query
from backend.config.log import get_logger
from backend.config.dependencies import get_current_user
from backend.config.database import DatabaseFactory
from backend.model.knowledge_library import KnowledgeLibrary
from backend.service.visual_graph import VisualGraphService
from backend.param.visual_graph import KnowledgeGraph

logger = get_logger(__name__)

router = APIRouter(
    prefix="/visual",
    tags=["VISUAL_GRAPH"]
)

@router.get("/graph/{collection_id}")
async def get_visual_graph(
    collection_id: str,
    label: str = Query(..., description="Label to get knowledge graph for"),
    current_user: int = Depends(get_current_user),
):
    """获取知识库的可视化图"""
    logger.info(f"用户 {current_user} 请求获取知识库 {collection_id} 的可视化图，label={label}")
    
    # 检查知识库是否启用了知识图谱
    db = DatabaseFactory.create_session()
    try:
        library = db.query(KnowledgeLibrary).filter(
            KnowledgeLibrary.collection_id == collection_id,
            KnowledgeLibrary.is_active == True
        ).first()
        
        if not library:
            logger.warning(f"知识库不存在: {collection_id}")
            return KnowledgeGraph(nodes=[], edges=[], is_truncated=False)
        
        if not library.enable_graph:
            logger.info(f"知识库 {collection_id} 未启用知识图谱，返回空数据")
            return KnowledgeGraph(nodes=[], edges=[], is_truncated=False)
    finally:
        db.close()
    
    # 启用了知识图谱，正常查询
    visualgraph = VisualGraphService(collection_id)
    return await visualgraph.get_knowledge_graph(node_label=label)
