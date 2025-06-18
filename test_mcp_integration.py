#!/usr/bin/env python3
"""
测试MCP集成功能
"""
import asyncio
import logging
import sys
from pathlib import Path

# 添加src路径
sys.path.append(str(Path(__file__).parent / "src"))

from tools.mcp_manager import mcp_manager
from tools.mcp_tools import MCPToolManager

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_mcp_manager():
    """测试MCP管理器"""
    print("=== 测试MCP管理器 ===")
    
    # 列出服务器
    servers = mcp_manager.list_servers()
    print(f"发现 {len(servers)} 个MCP服务器:")
    for server in servers:
        print(f"  - {server['name']} ({server['id']})")
    
    # 测试连接CSV服务器
    print("\n--- 测试连接CSV服务器 ---")
    try:
        success = await mcp_manager.connect_server("csv")
        print(f"CSV服务器连接: {'成功' if success else '失败'}")
        
        if success:
            # 获取服务器信息
            csv_info = next((s for s in mcp_manager.list_servers() if s['id'] == 'csv'), None)
            if csv_info:
                print(f"CSV服务器工具: {csv_info.get('tools', [])}")
                print(f"CSV服务器资源: {csv_info.get('resources', [])}")
    except Exception as e:
        print(f"CSV服务器连接失败: {e}")
    
    # 测试连接ChromaDB服务器
    print("\n--- 测试连接ChromaDB服务器 ---")
    try:
        success = await mcp_manager.connect_server("chromadb")
        print(f"ChromaDB服务器连接: {'成功' if success else '失败'}")
        
        if success:
            # 获取服务器信息
            chromadb_info = next((s for s in mcp_manager.list_servers() if s['id'] == 'chromadb'), None)
            if chromadb_info:
                print(f"ChromaDB服务器工具: {chromadb_info.get('tools', [])}")
                print(f"ChromaDB服务器资源: {chromadb_info.get('resources', [])}")
    except Exception as e:
        print(f"ChromaDB服务器连接失败: {e}")
    
    # 添加远程服务器示例
    print("\n--- 测试添加远程服务器 ---")
    try:
        mcp_manager.add_remote_server(
            "test_remote",
            "测试远程服务器",
            "http://localhost:3000",
            "这是一个测试用的远程MCP服务器"
        )
        print("成功添加远程服务器")
    except Exception as e:
        print(f"添加远程服务器失败: {e}")


async def test_mcp_tool_manager():
    """测试MCP工具管理器"""
    print("\n=== 测试MCP工具管理器 ===")
    
    # 创建工具管理器
    tool_manager = MCPToolManager(enabled_servers=["csv"])
    
    try:
        # 初始化
        await tool_manager.initialize()
        
        # 列出工具
        tools = tool_manager.list_tools()
        print(f"启用的工具: {tools}")
        
        # 获取工具描述
        description = tool_manager.get_tools_description()
        print(f"\n工具描述:\n{description}")
        
        # 获取MCP服务器状态
        status = tool_manager.get_mcp_servers_status()
        print(f"\nMCP服务器状态:")
        for server in status:
            print(f"  {server['name']}: {'已连接' if server['connected'] else '未连接'}")
    
    except Exception as e:
        print(f"工具管理器测试失败: {e}")
    
    finally:
        await tool_manager.cleanup()


async def main():
    """主函数"""
    print("开始测试MCP集成功能...\n")
    
    try:
        # 测试MCP管理器
        await test_mcp_manager()
        
        # 测试MCP工具管理器
        await test_mcp_tool_manager()
        
        print("\n✅ 测试完成!")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理
        await mcp_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main()) 