"""
MCP 管理器 - 管理多个 MCP Server 连接
"""
import os
import json
import re
from typing import Any, Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv

from backend.config.log import get_logger
from .client import MCPClient

logger = get_logger(__name__)

# 加载环境变量
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class MCPManager:
    """MCP Server 管理器，统一管理多个 MCP Server"""
    
    def __init__(self, config_path: str = None):
        """
        初始化管理器
        
        Args:
            config_path: 配置文件路径，默认为项目根目录的 mcp_config.json
        """
        self.clients: Dict[str, MCPClient] = {}
        self.config: Dict = {}
        self._tool_to_server: Dict[str, str] = {}  # 工具名 -> Server 名映射
        
        # 默认配置路径
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "mcp_config.json"
        
        self.config_path = Path(config_path)
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        if not self.config_path.exists():
            logger.warning(f"MCP 配置文件不存在: {self.config_path}")
            self.config = {"mcpServers": {}}
            return
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            
            # 替换环境变量
            self._replace_env_vars()
            
            server_count = len(self.config.get("mcpServers", {}))
            logger.info(f"加载 MCP 配置成功，共 {server_count} 个 Server")
            
        except Exception as e:
            logger.error(f"加载 MCP 配置失败: {e}")
            self.config = {"mcpServers": {}}
    
    def _replace_env_vars(self):
        """替换配置中的环境变量 ${VAR_NAME}"""
        def replace_in_value(value):
            if isinstance(value, str):
                # 匹配 ${VAR_NAME} 格式
                pattern = r'\$\{([^}]+)\}'
                matches = re.findall(pattern, value)
                for var_name in matches:
                    env_value = os.getenv(var_name, "")
                    value = value.replace(f"${{{var_name}}}", env_value)
                return value
            elif isinstance(value, dict):
                return {k: replace_in_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [replace_in_value(item) for item in value]
            return value
        
        self.config = replace_in_value(self.config)
    
    async def connect_all(self) -> Dict[str, bool]:
        """
        连接所有启用的 MCP Server
        
        Returns:
            各 Server 的连接状态
        """
        results = {}
        servers = self.config.get("mcpServers", {})
        
        for name, cfg in servers.items():
            if not cfg.get("enabled", True):
                logger.info(f"MCP Server {name} 已禁用，跳过")
                results[name] = False
                continue
            
            client = MCPClient(name, cfg)
            success = await client.connect()
            results[name] = success
            
            if success:
                self.clients[name] = client
                # 建立工具到 Server 的映射
                for tool in client.list_tools():
                    self._tool_to_server[tool["name"]] = name
        
        connected = sum(1 for v in results.values() if v)
        logger.info(f"MCP Server 连接完成: {connected}/{len(servers)} 成功")
        
        return results
    
    async def connect_server(self, name: str) -> bool:
        """
        连接单个 MCP Server
        
        Args:
            name: Server 名称
            
        Returns:
            是否连接成功
        """
        servers = self.config.get("mcpServers", {})
        if name not in servers:
            logger.error(f"MCP Server {name} 不存在")
            return False
        
        cfg = servers[name]
        client = MCPClient(name, cfg)
        success = await client.connect()
        
        if success:
            self.clients[name] = client
            for tool in client.list_tools():
                self._tool_to_server[tool["name"]] = name
        
        return success
    
    async def disconnect_all(self):
        """断开所有连接"""
        for name, client in self.clients.items():
            await client.disconnect()
        self.clients.clear()
        self._tool_to_server.clear()
        logger.info("所有 MCP Server 已断开")
    
    async def disconnect_server(self, name: str):
        """断开单个 Server"""
        if name in self.clients:
            await self.clients[name].disconnect()
            # 移除工具映射
            self._tool_to_server = {
                k: v for k, v in self._tool_to_server.items() if v != name
            }
            del self.clients[name]
    
    def list_all_tools(self) -> List[Dict]:
        """
        列出所有可用工具
        
        Returns:
            工具列表，每个工具包含 server, name, description, input_schema
        """
        all_tools = []
        for name, client in self.clients.items():
            for tool in client.list_tools():
                all_tools.append({
                    "server": name,
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool.get("input_schema", {})
                })
        return all_tools
    
    def get_tools_description(self) -> str:
        """
        获取工具描述文本，用于 LLM prompt
        
        Returns:
            格式化的工具描述
        """
        tools = self.list_all_tools()
        if not tools:
            return "当前没有可用的外部工具。"
        
        lines = ["可用的外部工具："]
        for tool in tools:
            lines.append(f"- {tool['name']}: {tool['description']}")
        return "\n".join(lines)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        调用工具（自动路由到对应 Server）
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        # 查找工具所属的 Server
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            return {
                "success": False,
                "error": f"工具 {tool_name} 不存在"
            }
        
        client = self.clients.get(server_name)
        if not client:
            return {
                "success": False,
                "error": f"Server {server_name} 未连接"
            }
        
        return await client.call_tool(tool_name, arguments)
    
    async def call_tool_on_server(
        self, 
        server_name: str, 
        tool_name: str, 
        arguments: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        在指定 Server 上调用工具
        
        Args:
            server_name: Server 名称
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        client = self.clients.get(server_name)
        if not client:
            return {
                "success": False,
                "error": f"Server {server_name} 未连接"
            }
        
        return await client.call_tool(tool_name, arguments)
    
    def get_connected_servers(self) -> List[str]:
        """获取已连接的 Server 列表"""
        return list(self.clients.keys())
    
    def get_server_info(self, name: str) -> Optional[Dict]:
        """获取 Server 信息"""
        if name not in self.clients:
            return None
        
        client = self.clients[name]
        return {
            "name": name,
            "connected": client.is_connected,
            "tools": client.list_tools(),
            "description": self.config.get("mcpServers", {}).get(name, {}).get("description", "")
        }
    
    def __repr__(self):
        return f"MCPManager(servers={len(self.clients)}, tools={len(self._tool_to_server)})"
