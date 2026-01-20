"""
MCP 客户端测试脚本
"""
import asyncio
import sys
sys.path.insert(0, '.')

from backend.mcp.manager import MCPManager


async def test_mcp():
    print("=" * 50)
    print("MCP 客户端测试")
    print("=" * 50)
    
    # 1. 创建管理器
    manager = MCPManager()
    print(f"\n[1] 加载配置完成")
    
    # 2. 连接所有 Server
    print(f"\n[2] 正在连接 MCP Server...")
    results = await manager.connect_all()
    print(f"连接结果: {results}")
    
    # 3. 列出所有工具
    tools = manager.list_all_tools()
    print(f"\n[3] 可用工具 ({len(tools)} 个):")
    for tool in tools:
        print(f"  - {tool['server']}/{tool['name']}: {tool['description'][:50]}...")
    
    # 4. 测试调用 fetch 工具
    if tools:
        print(f"\n[4] 测试调用 fetch 工具...")
        result = await manager.call_tool("fetch", {
            "url": "https://example.com"
        })
        
        if result.get("success"):
            content = result.get("content", "")
            print(f"抓取成功！内容长度: {len(content)} 字符")
            print(f"内容预览: {content[:200]}...")
        else:
            print(f"抓取失败: {result.get('error')}")
    
    # 5. 断开连接
    print(f"\n[5] 断开连接...")
    await manager.disconnect_all()
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_mcp())
