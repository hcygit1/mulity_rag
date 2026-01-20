"""
联网搜索服务 - 直接调用 Tavily API
"""
import os
import httpx
from typing import Dict, Any, List
from dotenv import load_dotenv

from backend.config.log import get_logger

# 加载环境变量
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

logger = get_logger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"

# 相关性过滤配置
DEFAULT_SCORE_THRESHOLD = 0.7  # 默认相关性阈值
DEFAULT_MAX_CONTENT_LENGTH = 500  # 单条结果最大长度
DEFAULT_TOTAL_MAX_LENGTH = 3000  # 总结果最大长度


async def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    score_threshold: float = DEFAULT_SCORE_THRESHOLD
) -> Dict[str, Any]:
    """
    调用 Tavily API 进行联网搜索
    
    Args:
        query: 搜索查询
        max_results: 最大结果数
        search_depth: 搜索深度 ("basic" 或 "advanced")
        score_threshold: 相关性分数阈值（0-1），低于此值的结果会被过滤
        
    Returns:
        搜索结果
    """
    api_key = os.getenv("TAVILY_API_KEY")
    
    if not api_key:
        logger.warning("TAVILY_API_KEY 未配置")
        return {"success": False, "error": "Tavily API Key 未配置", "content": ""}
    
    try:
        logger.info(f"调用 Tavily API: {query[:50]}...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                TAVILY_API_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": search_depth,
                    "include_answer": True,
                    "include_raw_content": False
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # 按相关性分数过滤结果
                original_count = len(data.get("results", []))
                data = _filter_by_relevance(data, score_threshold)
                filtered_count = len(data.get("results", []))
                
                logger.info(f"相关性过滤: {original_count} -> {filtered_count} 条 (阈值: {score_threshold})")
                
                content = _format_results(data)
                logger.info(f"Tavily 搜索成功，结果长度: {len(content)} 字符")
                return {"success": True, "content": content}
            else:
                logger.error(f"Tavily API 请求失败: {response.status_code}")
                return {"success": False, "error": f"API 请求失败: {response.status_code}", "content": ""}
                
    except httpx.TimeoutException:
        logger.error("Tavily API 请求超时")
        return {"success": False, "error": "请求超时", "content": ""}
    except Exception as e:
        logger.error(f"Tavily 搜索异常: {e}")
        return {"success": False, "error": str(e), "content": ""}


def _filter_by_relevance(data: Dict[str, Any], threshold: float) -> Dict[str, Any]:
    """
    按 Tavily 返回的相关性分数过滤结果
    
    Args:
        data: Tavily API 返回的原始数据
        threshold: 相关性阈值（0-1）
        
    Returns:
        过滤后的数据
    """
    results = data.get("results", [])
    
    # 过滤低相关性结果
    filtered_results = [
        r for r in results 
        if r.get("score", 0) >= threshold
    ]
    
    # 按分数降序排序
    filtered_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    data["results"] = filtered_results
    return data


def _format_results(data: Dict[str, Any]) -> str:
    """格式化搜索结果"""
    lines = []
    
    # AI 生成的答案摘要
    if data.get("answer"):
        lines.append(f"【搜索摘要】\n{data['answer']}\n")
    
    # 搜索结果
    results = data.get("results", [])
    if results:
        lines.append("【搜索结果】")
        for i, result in enumerate(results, 1):
            title = result.get("title", "无标题")
            url = result.get("url", "")
            content = result.get("content", "")
            score = result.get("score", 0)
            
            lines.append(f"\n[{i}] {title} (相关度: {score:.2f})")
            if url:
                lines.append(f"    链接: {url}")
            if content:
                if len(content) > DEFAULT_MAX_CONTENT_LENGTH:
                    content = content[:DEFAULT_MAX_CONTENT_LENGTH] + "..."
                lines.append(f"    内容: {content}")
    else:
        lines.append("【搜索结果】\n未找到高相关性的搜索结果")
    
    return "\n".join(lines)


async def web_search(
    query: str, 
    max_results: int = 5,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD
) -> str:
    """
    执行联网搜索
    
    Args:
        query: 搜索查询
        max_results: 最大结果数
        score_threshold: 相关性分数阈值（0-1），默认0.5
        
    Returns:
        搜索结果文本，失败返回空字符串
    """
    result = await tavily_search(query, max_results, score_threshold=score_threshold)
    
    if result.get("success"):
        content = result.get("content", "")
        # 截断过长内容
        if len(content) > DEFAULT_TOTAL_MAX_LENGTH:
            content = content[:DEFAULT_TOTAL_MAX_LENGTH] + "\n...(内容已截断)"
        return content
    else:
        logger.warning(f"联网搜索失败: {result.get('error')}")
        return ""
