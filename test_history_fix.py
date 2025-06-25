"""
测试历史记录和记忆功能修复
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.append('src')

from core.types import Message, MessageRole
from agents.react_agent import ReactAgent
from llm.doubao import DoubaoLLMProvider
from core.memory import SQLiteMemoryStore
from tools.mcp_tools import MCPToolManager

async def test_history_and_memory():
    """测试历史记录和记忆功能"""
    print("🧪 开始测试历史记录和记忆功能...")
    
    # 创建LLM
    llm = DoubaoLLMProvider(
        model_name="ep-20250221154410-vh78x",
        temperature=0.7
    )
    await llm.initialize()
    
    # 创建工具管理器
    tool_manager = MCPToolManager()
    await tool_manager.initialize()
    
    # 创建记忆存储
    memory_store = SQLiteMemoryStore("workspace/test_memory.db")
    
    # 创建Agent（启用记忆）
    agent = ReactAgent(
        llm=llm,
        tool_manager=tool_manager,
        max_iterations=3,
        memory_enabled=True,
        memory_store=memory_store,
        session_id="test_session_001"
    )
    
    print(f"✅ Agent创建成功，会话ID: {agent.memory_manager.session_id}")
    
    # 测试第一轮对话
    print("\n📝 第一轮对话...")
    query1 = "我的名字是张三，我喜欢编程"
    result1 = await agent.run(query1)
    print(f"用户: {query1}")
    print(f"助手: {result1.result}")
    
    # 测试第二轮对话（应该能记住第一轮）
    print("\n📝 第二轮对话...")
    query2 = "你还记得我的名字吗？"
    
    # 模拟完整的对话历史（这是修复的关键）
    conversation_history = [
        Message(role=MessageRole.USER, content=query1),
        Message(role=MessageRole.ASSISTANT, content=result1.result),
        Message(role=MessageRole.USER, content=query2)
    ]
    
    context_with_history = {
        "conversation_history": conversation_history,
        "preserve_history": True
    }
    
    result2 = await agent.run(query2, context_with_history)
    print(f"用户: {query2}")
    print(f"助手: {result2.result}")
    
    # 测试记忆状态
    print("\n🧠 记忆统计...")
    memory_stats = await agent.get_memory_stats()
    if memory_stats:
        print(f"短期记忆: {memory_stats.get('short_term', {}).get('item_count', 0)} 条")
        print(f"长期记忆: {memory_stats.get('long_term', {}).get('total_memories', 0)} 条")
    
    # 测试流式对话
    print("\n🌊 测试流式对话...")
    query3 = "我刚才说了什么爱好？"
    
    # 更新对话历史
    updated_history = conversation_history + [
        Message(role=MessageRole.ASSISTANT, content=result2.result),
        Message(role=MessageRole.USER, content=query3)
    ]
    
    context_stream = {
        "conversation_history": updated_history,
        "preserve_history": True
    }
    
    print(f"用户: {query3}")
    print("助手流式回复: ", end="")
    
    async for chunk in agent.stream_run(query3, context_stream):
        if chunk.get("type") == "text_chunk":
            print(chunk.get("content", ""), end="", flush=True)
    
    print("\n")
    
    # 清理
    await agent.cleanup()
    print("\n✅ 测试完成！")

if __name__ == "__main__":
    asyncio.run(test_history_and_memory()) 