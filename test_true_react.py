# -*- coding: utf-8 -*-
"""
测试TrueReactAgent的脚本

@author leo
@description 测试标准ReactAgent和信息流功能
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from agents.react_agent import ReactAgent
from llm.base import LLMFactory, LLMConfig
from tools.mcp_tools import MCPToolManager
from core.base import NodeInfoStream

async def test_true_react():
    """测试TrueReactAgent"""
    print("=== 测试标准ReactAgent ===")
    
    # 创建LLM
    llm_config = LLMConfig(
        provider="doubao",
        model_name="ep-20250221154410-vh78x",
        api_key="f5cc906e-d85b-4cb2-afe7-79bd39d16b7d",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        temperature=0.7,
        max_tokens=2000
    )
    
    llm = LLMFactory.create(llm_config)
    
    # 创建工具管理器
    tool_manager = MCPToolManager()
    await tool_manager.initialize()
    
    # 创建ReactAgent
    agent = ReactAgent(
        llm=llm,
        tool_manager=tool_manager,
        max_iterations=5,
        name="测试ReactAgent"
    )
    
    # 设置信息流回调
    info_stream = NodeInfoStream()
    
    def print_info_event(event):
        print(f"[信息流] {event['type']} | {event['node_name']}: {event['content']}")
    
    info_stream.add_callback(print_info_event)
    
    # 测试查询
    test_query = "帮我计算 123 + 456，然后解释一下计算过程"
    
    print(f"\n用户问题: {test_query}")
    print("\n--- ReactAgent 执行过程 ---")
    
    # 执行Agent
    result = await agent.run(test_query)
    
    print(f"\n--- 执行结果 ---")
    print(f"成功: {result.success}")
    print(f"结果: {result.result}")
    
    # 显示信息流事件
    print(f"\n--- 信息流事件 ({len(info_stream.get_events())} 个) ---")
    for event in info_stream.get_events():
        print(f"[{event['timestamp']}] {event['type']} | {event['node_name']}: {event['content'][:100]}...")
    
    # 清理
    await agent.cleanup()

async def test_stream_react():
    """测试流式ReactAgent"""
    print("\n\n=== 测试流式ReactAgent ===")
    
    # 创建LLM
    llm_config = LLMConfig(
        provider="doubao",
        model_name="ep-20250221154410-vh78x",
        api_key="f5cc906e-d85b-4cb2-afe7-79bd39d16b7d",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        temperature=0.7,
        max_tokens=2000
    )
    
    llm = LLMFactory.create(llm_config)
    
    # 创建ReactAgent
    agent = ReactAgent(
        llm=llm,
        tool_manager=None,  # 不使用工具测试纯推理
        max_iterations=3,
        name="流式测试ReactAgent"
    )
    
    # 测试查询
    test_query = "请分析一下人工智能的发展趋势"
    
    print(f"\n用户问题: {test_query}")
    print("\n--- 流式ReactAgent 执行过程 ---")
    
    # 流式执行Agent
    async for chunk in agent.stream_run(test_query):
        if chunk.get("type") == "text_chunk":
            print(chunk.get("content", ""), end="", flush=True)
        elif chunk.get("type") == "info_stream":
            print(f"\n[信息流] {chunk.get('event_type')} | {chunk.get('node_name')}: {chunk.get('content')}")
    
    print("\n\n--- 流式执行完成 ---")
    
    # 清理
    await agent.cleanup()

if __name__ == "__main__":
    # 设置环境变量
    os.environ['ARK_API_KEY'] = 'f5cc906e-d85b-4cb2-afe7-79bd39d16b7d'
    
    try:
        # 测试标准ReactAgent
        asyncio.run(test_true_react())
        
        # 测试流式ReactAgent
        asyncio.run(test_stream_react())
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()