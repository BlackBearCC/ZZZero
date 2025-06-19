#!/usr/bin/env python3
"""
测试应用流程
验证以下功能：
1. 启动时自动启动MCP服务器
2. 配置实时生效
3. 无MCP时也能正常对话
"""
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.types import LLMConfig
from agents.react_agent import ReactAgent
from llm.base import LLMFactory
from tools.mcp_tools import MCPToolManager


async def test_no_tools():
    """测试没有工具时的Agent"""
    print("=== 测试1: 无工具Agent ===")
    
    # 创建LLM
    llm_config = LLMConfig(
        provider="doubao",
        model_name="ep-20250221154410-vh78x",
        temperature=0.7
    )
    llm = LLMFactory.create(llm_config)
    await llm.initialize()
    
    # 创建无工具的Agent
    agent = ReactAgent(
        llm=llm,
        tool_manager=None,  # 没有工具管理器
        max_iterations=5
    )
    
    # 测试对话
    result = await agent.run("你好，请介绍一下你自己")
    print(f"回复: {result.result}")
    print(f"成功: {result.success}")
    print(f"执行轨迹: {len(result.execution_trace)} 个节点")
    
    await llm.cleanup()
    print()


async def test_empty_tools():
    """测试空工具列表的Agent"""
    print("=== 测试2: 空工具列表Agent ===")
    
    # 创建LLM
    llm_config = LLMConfig(
        provider="doubao",
        model_name="ep-20250221154410-vh78x",
        temperature=0.7
    )
    llm = LLMFactory.create(llm_config)
    await llm.initialize()
    
    # 创建空工具管理器
    tool_manager = MCPToolManager(enabled_servers=[])
    await tool_manager.initialize()
    
    # 创建Agent
    agent = ReactAgent(
        llm=llm,
        tool_manager=tool_manager,
        max_iterations=5
    )
    
    # 测试对话
    result = await agent.run("今天的天气怎么样？")
    print(f"回复: {result.result}")
    print(f"成功: {result.success}")
    print(f"可用工具数: {len(tool_manager.list_tools())}")
    
    await tool_manager.cleanup()
    await llm.cleanup()
    print()


async def test_with_mcp():
    """测试有MCP服务器的Agent"""
    print("=== 测试3: 带MCP服务器的Agent ===")
    
    # 创建LLM
    llm_config = LLMConfig(
        provider="doubao",
        model_name="ep-20250221154410-vh78x",
        temperature=0.7
    )
    llm = LLMFactory.create(llm_config)
    await llm.initialize()
    
    # 创建工具管理器，启用测试服务器
    tool_manager = MCPToolManager(enabled_servers=["test"])
    await tool_manager.initialize()
    
    # 创建Agent
    agent = ReactAgent(
        llm=llm,
        tool_manager=tool_manager,
        max_iterations=5
    )
    
    # 测试对话
    result = await agent.run("使用工具计算 15 + 27 的结果")
    print(f"回复: {result.result}")
    print(f"成功: {result.success}")
    print(f"可用工具数: {len(tool_manager.list_tools())}")
    print(f"工具调用次数: {result.metrics.get('tool_calls', 0)}")
    
    await tool_manager.cleanup()
    await llm.cleanup()
    print()


async def test_config_change():
    """测试配置变化"""
    print("=== 测试4: 配置动态变化 ===")
    
    # 初始配置
    config = {
        'llm_provider': 'doubao',
        'model_name': 'ep-20250221154410-vh78x',
        'temperature': 0.7,
        'enabled_mcp_servers': []
    }
    
    # 创建初始Agent
    llm_config = LLMConfig(**{k: v for k, v in config.items() if k != 'enabled_mcp_servers'})
    llm = LLMFactory.create(llm_config)
    await llm.initialize()
    
    tool_manager = MCPToolManager(enabled_servers=config['enabled_mcp_servers'])
    await tool_manager.initialize()
    
    agent = ReactAgent(llm=llm, tool_manager=tool_manager)
    
    print(f"初始工具数: {len(tool_manager.list_tools())}")
    
    # 模拟配置变化：添加MCP服务器
    print("添加test服务器...")
    config['enabled_mcp_servers'] = ['test']
    
    # 重新创建工具管理器
    await tool_manager.cleanup()
    tool_manager = MCPToolManager(enabled_servers=config['enabled_mcp_servers'])
    await tool_manager.initialize()
    
    # 更新Agent
    agent = ReactAgent(llm=llm, tool_manager=tool_manager)
    
    print(f"更新后工具数: {len(tool_manager.list_tools())}")
    
    await tool_manager.cleanup()
    await llm.cleanup()


async def main():
    """主测试函数"""
    print("开始测试应用流程...")
    print()
    
    try:
        # 测试各种场景
        await test_no_tools()
        await test_empty_tools()
        await test_with_mcp()
        await test_config_change()
        
        print("✅ 所有测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 