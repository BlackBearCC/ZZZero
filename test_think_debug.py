"""
测试think模式的输出格式
"""
import asyncio
import os
import sys
sys.path.append('src')

from llm.doubao import DoubaoLLM
from core.types import Message, MessageRole, LLMConfig

async def test_think_mode():
    """测试think模式输出"""
    
    # 配置LLM
    config = LLMConfig(
        api_key=os.getenv('ARK_API_KEY'),
        model_name="doubao-pro-4k",
        api_base="https://ark.cn-beijing.volces.com/api/v3"
    )
    
    llm = DoubaoLLM(config)
    await llm.initialize()
    
    # 测试消息
    messages = [Message(role=MessageRole.USER, content="请简单介绍一下天文学")]
    
    print("=== 测试普通模式（return_dict=False）===")
    async for chunk in llm.stream_generate(messages, mode="think", return_dict=False):
        print(f"普通模式chunk类型: {type(chunk)}, 内容: {repr(chunk[:50])}")
    
    print("\n=== 测试工作流模式（return_dict=True）===")
    async for chunk in llm.stream_generate(messages, mode="think", return_dict=True):
        print(f"工作流模式chunk类型: {type(chunk)}, 结构: {chunk}")

if __name__ == "__main__":
    asyncio.run(test_think_mode()) 