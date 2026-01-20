"""
MCP 客户端 - 单个 MCP Server 的连接和调用
"""
import asyncio
from typing import Any, Dict, List, Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from backend.config.log import get_logger

logger = get_logger(__name__)


class MCPClient:
    """单个 MCP Server 的客户端"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        初始化 MCP 客户端
        
        Args:
            name: Server 名称
            config: Server 配置，包含 command, args, env 等
        """
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self.tools: List[Dict] = []
        self._exit_stack: Optional[AsyncExitStack] = None
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def connect(self) -> bool:
        """
        连接到 MCP Server
        
        Returns:
            是否连接成功
        """
        try:
            logger.info(f"正在连接 MCP Server: {self.name}")
            
            server_type = self.config.get("type", "stdio")
            
            if server_type == "stdio":
                # 本地进程方式
                server_params = StdioServerParameters(
                    command=self.config["command"],
                    args=self.config.get("args", []),
                    env=self.config.get("env", None)
                )
                
                self._exit_stack = AsyncExitStack()
                stdio_transport = await self._exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                read_stream, write_stream = stdio_transport
                self.session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
            else:
                raise ValueError(f"不支持的连接类型: {server_type}")
            
            # 初始化会话
            await self.session.initialize()
            
            # 获取可用工具列表
            await self._load_tools()
            
            self._connected = True
            logger.info(f"MCP Server {self.name} 连接成功，可用工具: {len(self.tools)} 个")
            return True
            
        except Exception as e:
            logger.error(f"连接 MCP Server {self.name} 失败: {e}")
            self._connected = False
            return False
    
    async def _load_tools(self):
        """加载 Server 提供的工具列表"""
        if not self.session:
            return
        
        try:
            tools_result = await self.session.list_tools()
            self.tools = []
            for tool in tools_result.tools:
                self.tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                })
                logger.debug(f"  - 工具: {tool.name}")
        except Exception as e:
            logger.error(f"获取工具列表失败: {e}")
            self.tools = []
    
    def list_tools(self) -> List[Dict]:
        """
        获取可用工具列表
        
        Returns:
            工具列表，每个工具包含 name, description, input_schema
        """
        return self.tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        if not self.session or not self._connected:
            return {"error": f"MCP Server {self.name} 未连接"}
        
        try:
            logger.info(f"调用 MCP 工具: {self.name}/{tool_name}")
            logger.debug(f"参数: {arguments}")
            
            result = await self.session.call_tool(tool_name, arguments or {})
            
            # 解析结果
            content = []
            for item in result.content:
                if hasattr(item, 'text'):
                    content.append(item.text)
                elif hasattr(item, 'data'):
                    content.append(str(item.data))
                else:
                    content.append(str(item))
            
            response = {
                "success": True,
                "tool": tool_name,
                "content": "\n".join(content) if content else "",
                "is_error": result.isError if hasattr(result, 'isError') else False
            }
            
            logger.info(f"工具 {tool_name} 执行成功")
            return response
            
        except Exception as e:
            logger.error(f"调用工具 {tool_name} 失败: {e}")
            return {
                "success": False,
                "tool": tool_name,
                "error": str(e)
            }
    
    async def disconnect(self):
        """断开连接"""
        try:
            if self._exit_stack:
                await self._exit_stack.aclose()
            self._connected = False
            self.session = None
            logger.info(f"MCP Server {self.name} 已断开")
        except Exception as e:
            logger.error(f"断开 MCP Server {self.name} 失败: {e}")
    
    def __repr__(self):
        status = "已连接" if self._connected else "未连接"
        return f"MCPClient(name={self.name}, status={status}, tools={len(self.tools)})"
