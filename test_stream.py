#!/usr/bin/env python3
"""
测试流式输出功能
"""
import asyncio
import os
import sys

# 添加src路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from llm.base import LLMFactory
from core.types import LLMConfig
from tools.mcp_tools import MCPToolManager
from agents.react_agent import ReactAgent


async def test_stream_output():
    """测试流式输出功能"""
    print("🔥 开始测试流式输出功能")
    
    # 创建LLM配置
    llm_config = LLMConfig(
        provider="doubao",
        model_name="ep-20250221154410-vh78x",
        temperature=0.7
    )
    
    # 创建LLM实例
    llm = LLMFactory.create(llm_config)
    await llm.initialize()
    
    # 创建工具管理器
    tool_manager = MCPToolManager()
    await tool_manager.initialize()
    
    # 创建ReAct Agent
    agent = ReactAgent(
        llm=llm,
        tool_manager=tool_manager,
        max_iterations=5
    )
    
    # 测试查询
    query = "帮我查询一下CSV表格中的数据"
    
    print(f"\n📝 查询: {query}")
    print("\n🚀 开始流式输出:")
    print("-" * 50)
    
    try:
        async for chunk in agent.stream_run(query):
            chunk_type = chunk.get("type", "")
            content = chunk.get("content", "")
            
            if chunk_type == "text_chunk":
                print(content, end="", flush=True)
            elif chunk_type == "tool_result":
                print(f"\n🔧 [工具调用完成]", flush=True)
                print(content, end="", flush=True)
            elif chunk_type == "tool_error":
                print(f"\n❌ [工具错误]: {content}", flush=True)
            elif chunk_type == "stream_error":
                print(f"\n💥 [流式错误]: {content}", flush=True)
    
    except Exception as e:
        print(f"\n💥 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "-" * 50)
    print("✅ 流式输出测试完成")
    
    # 清理资源
    await agent.cleanup()


async def test_simple_stream():
    """测试简单流式输出（不带工具）"""
    print("\n🔥 开始测试简单流式输出")
    
    # 创建LLM配置
    llm_config = LLMConfig(
        provider="doubao",
        model_name="ep-20250221154410-vh78x",
        temperature=0.7
    )
    
    # 创建LLM实例
    llm = LLMFactory.create(llm_config)
    await llm.initialize()
    
    # 创建ReAct Agent（不使用工具）
    agent = ReactAgent(
        llm=llm,
        tool_manager=None,
        max_iterations=5
    )
    
    # 测试查询
    query = "请介绍一下Python的装饰器"
    
    print(f"\n📝 查询: {query}")
    print("\n🚀 开始流式输出:")
    print("-" * 50)
    
    try:
        async for chunk in agent.stream_run(query):
            chunk_type = chunk.get("type", "")
            content = chunk.get("content", "")
            
            if chunk_type == "text_chunk":
                print(content, end="", flush=True)
            elif chunk_type == "final_result":
                print(content, end="", flush=True)
    
    except Exception as e:
        print(f"\n💥 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "-" * 50)
    print("✅ 简单流式输出测试完成")
    
    # 清理资源
    await agent.cleanup()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_simple_stream())
    print("\n" + "=" * 60)
    asyncio.run(test_stream_output()) 