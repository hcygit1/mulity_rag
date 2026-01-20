#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对话记忆服务
提供多轮对话的上下文管理，包括滑动窗口和摘要生成
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from backend.config.database import DatabaseFactory
from backend.model.conversation import Conversation
from backend.service.chat_history import get_chat_messages, get_message_count
from backend.config.log import get_logger

logger = get_logger(__name__)


class ConversationMemory:
    """对话记忆管理器
    
    采用滑动窗口 + 摘要缓存策略：
    - 消息数量 ≤ WINDOW_SIZE：返回全部历史消息
    - 消息数量 > WINDOW_SIZE：返回 [摘要] + [最近N条消息]
    """
    
    WINDOW_SIZE = 10  # 滑动窗口大小
    SUMMARY_EXPIRE_MINUTES = 30  # 摘要过期时间（分钟）
    
    def __init__(self, llm=None):
        """初始化对话记忆管理器
        
        Args:
            llm: LangChain LLM 实例，用于生成摘要
        """
        self.llm = llm
    
    async def get_context(self, conversation_id: str) -> Dict[str, Any]:
        """获取对话上下文
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            {
                "history_messages": [...],  # 历史消息列表
                "summary": "...",           # 摘要（如果有）
                "total_count": 25,          # 总消息数
                "has_summary": True/False   # 是否使用了摘要
            }
        """
        try:
            # 1. 获取消息总数（只统计 user 和 assistant 的 messages 类型）
            all_messages = get_chat_messages(conversation_id)
            chat_messages = [
                msg for msg in all_messages 
                if msg.get('type') == 'messages' and msg.get('role') in ('user', 'assistant')
            ]
            total_count = len(chat_messages)
            
            logger.info(f"对话 {conversation_id} 共有 {total_count} 条有效消息")
            
            if total_count <= self.WINDOW_SIZE:
                # 消息少，返回全部
                logger.info(f"消息数量 ≤ {self.WINDOW_SIZE}，返回全部历史")
                return {
                    "history_messages": chat_messages,
                    "summary": None,
                    "total_count": total_count,
                    "has_summary": False
                }
            
            # 2. 消息多，需要摘要 + 最近消息
            logger.info(f"消息数量 > {self.WINDOW_SIZE}，检查摘要状态")
            
            # 获取对话信息
            conversation = self._get_conversation(conversation_id)
            if not conversation:
                logger.warning(f"对话 {conversation_id} 不存在")
                return {
                    "history_messages": chat_messages[-self.WINDOW_SIZE:],
                    "summary": None,
                    "total_count": total_count,
                    "has_summary": False
                }
            
            summary = conversation.summary
            summary_updated_at = conversation.summary_updated_at
            
            # 3. 检查摘要是否需要更新
            need_update = self._should_update_summary(summary, summary_updated_at)
            
            if need_update:
                logger.info("摘要需要更新，开始生成新摘要")
                # 获取需要摘要的旧消息（排除最近 WINDOW_SIZE 条）
                old_messages = chat_messages[:-self.WINDOW_SIZE]
                summary = await self._generate_summary(old_messages)
                # 更新数据库
                await self._update_conversation_summary(conversation_id, summary)
            else:
                logger.info("使用缓存的摘要")
            
            # 4. 获取最近消息
            recent_messages = chat_messages[-self.WINDOW_SIZE:]
            
            return {
                "history_messages": recent_messages,
                "summary": summary,
                "total_count": total_count,
                "has_summary": True
            }
            
        except Exception as e:
            logger.error(f"获取对话上下文失败: {e}")
            return {
                "history_messages": [],
                "summary": None,
                "total_count": 0,
                "has_summary": False
            }
    
    def _get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取对话实体"""
        db = None
        try:
            db = DatabaseFactory.create_session()
            conversation = db.query(Conversation).filter(
                Conversation.conversation_id == conversation_id
            ).first()
            return conversation
        except Exception as e:
            logger.error(f"获取对话失败: {e}")
            return None
        finally:
            if db:
                db.close()
    
    def _should_update_summary(self, summary: Optional[str], summary_updated_at: Optional[datetime]) -> bool:
        """判断是否需要更新摘要
        
        更新条件：
        1. 摘要不存在
        2. 摘要过期（超过 SUMMARY_EXPIRE_MINUTES 分钟）
        """
        if not summary:
            return True
        
        if not summary_updated_at:
            return True
        
        # 检查是否过期
        expire_time = datetime.now() - timedelta(minutes=self.SUMMARY_EXPIRE_MINUTES)
        if summary_updated_at < expire_time:
            logger.info(f"摘要已过期，上次更新: {summary_updated_at}")
            return True
        
        return False
    
    async def _generate_summary(self, messages: List[Dict[str, Any]]) -> str:
        """调用 LLM 生成对话摘要
        
        Args:
            messages: 需要摘要的消息列表
            
        Returns:
            生成的摘要文本
        """
        if not messages:
            return ""
        
        if not self.llm:
            logger.warning("LLM 未初始化，无法生成摘要")
            return self._generate_simple_summary(messages)
        
        try:
            # 格式化对话历史
            conversation_text = self._format_messages_for_summary(messages)
            
            # 构建摘要 prompt
            prompt = f"""请对以下对话历史进行简洁摘要，保留关键信息：
1. 用户讨论的主要话题
2. 重要的结论或决定
3. 用户的偏好或需求

对话历史：
{conversation_text}

请用2-3句话概括以上对话的核心内容，使用中文回答："""
            
            # 调用 LLM
            result = await self.llm.ainvoke(prompt)
            summary = result.content if hasattr(result, 'content') else str(result)
            
            logger.info(f"摘要生成成功，长度: {len(summary)}")
            return summary.strip()
            
        except Exception as e:
            logger.error(f"LLM 生成摘要失败: {e}")
            return self._generate_simple_summary(messages)
    
    def _generate_simple_summary(self, messages: List[Dict[str, Any]]) -> str:
        """生成简单摘要（LLM 不可用时的降级方案）"""
        if not messages:
            return ""
        
        # 提取用户消息的前几条作为简单摘要
        user_messages = [msg['content'] for msg in messages if msg.get('role') == 'user']
        if not user_messages:
            return ""
        
        # 取前3条用户消息的摘要
        summary_parts = []
        for msg in user_messages[:3]:
            # 截取前50个字符
            short_msg = msg[:50] + "..." if len(msg) > 50 else msg
            summary_parts.append(short_msg)
        
        return f"历史话题: {'; '.join(summary_parts)}"
    
    def _format_messages_for_summary(self, messages: List[Dict[str, Any]]) -> str:
        """格式化消息用于摘要生成"""
        formatted = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            # 限制每条消息长度
            if len(content) > 200:
                content = content[:200] + "..."
            role_name = "用户" if role == "user" else "助手"
            formatted.append(f"{role_name}: {content}")
        
        return "\n".join(formatted)
    
    async def _update_conversation_summary(self, conversation_id: str, summary: str) -> bool:
        """更新对话摘要到数据库"""
        db = None
        try:
            db = DatabaseFactory.create_session()
            conversation = db.query(Conversation).filter(
                Conversation.conversation_id == conversation_id
            ).first()
            
            if conversation:
                conversation.summary = summary
                conversation.summary_updated_at = datetime.now()
                db.commit()
                logger.info(f"对话 {conversation_id} 摘要已更新")
                return True
            return False
            
        except Exception as e:
            logger.error(f"更新摘要失败: {e}")
            if db:
                db.rollback()
            return False
        finally:
            if db:
                db.close()


def format_history_context(context_data: Dict[str, Any]) -> str:
    """将上下文数据格式化为可用于 prompt 的字符串
    
    Args:
        context_data: get_context() 返回的数据
        
    Returns:
        格式化后的历史上下文字符串
    """
    parts = []
    
    # 添加摘要
    if context_data.get("has_summary") and context_data.get("summary"):
        parts.append(f"[历史对话摘要]\n{context_data['summary']}\n")
    
    # 添加最近消息
    history_messages = context_data.get("history_messages", [])
    if history_messages:
        parts.append("[最近对话记录]")
        for msg in history_messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            role_name = "用户" if role == "user" else "助手"
            parts.append(f"{role_name}: {content}")
    
    return "\n".join(parts) if parts else ""
