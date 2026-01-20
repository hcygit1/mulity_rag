"""
MCP (Model Context Protocol) 客户端模块

用于连接和管理 MCP Server，为 RAG Agent 提供外部工具能力。
"""

from .client import MCPClient
from .manager import MCPManager

__all__ = ["MCPClient", "MCPManager"]
