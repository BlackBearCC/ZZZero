#!/usr/bin/env python3
"""
调试DoubaoLLM的原始chunk响应
"""
import asyncio
import os
import sys
import json
import aiohttp
from typing import List

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.types import Message, MessageRole, LLMConfig
from llm.doubao import DoubaoLLM

async def test_raw_api_response():
    """测试原始API响应"""
    print("🔍 测试原始API响应...")
    
    # 检查环境变量
    api_key = os.getenv('ARK_API_KEY') or os.getenv('DOUBAO_API_KEY')
    if not api_key:
        print("❌ 未设置API密钥")
        return
    
    base_url = os.getenv('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
    deepseek_model = os.getenv('DOUBAO_MODEL_DEEPSEEKR1', 'deepseek-reasoner')
    
    print(f"✅ API密钥: {'*' * 10}...{api_key[-4:]}")
    print(f"✅ 基础URL: {base_url}")
    print(f"✅ 模型名称: {deepseek_model}")
    
    # 构建请求
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": deepseek_model,
        "messages": [
            {"role": "user", "content": "简单回答：1+1等于多少？"}
        ],
        "temperature": 0.6,
        "max_tokens": 1000,
        "stream": True,
        "stream_options": {
            "include_usage": True
        }
    }
    
    print(f"\n📤 发送请求数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                print(f"\n📥 响应状态: {response.status}")
                print(f"📥 响应头: {dict(response.headers)}")
                
                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ API调用失败: {error_text}")
                    return
                
                chunk_count = 0
                reasoning_chunks = 0
                content_chunks = 0
                
                print("\n📊 原始chunk数据:")
                print("-" * 80)
                
                # 处理流式响应
                async for line in response.content:
                    line_text = line.decode('utf-8').strip()
                    if not line_text:
                        continue
                    
                    chunk_count += 1
                    print(f"[Chunk {chunk_count}] 原始行: {repr(line_text)}")
                    
                    if line_text.startswith("data: "):
                        line_text = line_text[6:]
                        print(f"[Chunk {chunk_count}] 去除前缀后: {repr(line_text)}")
                        
                    if line_text == "[DONE]":
                        print(f"[Chunk {chunk_count}] 流结束标记")
                        break
                        
                    try:
                        chunk = json.loads(line_text)
                        print(f"[Chunk {chunk_count}] JSON解析成功:")
                        print(f"  完整chunk: {json.dumps(chunk, ensure_ascii=False, indent=2)}")
                        
                        if chunk.get("choices") and len(chunk["choices"]) > 0:
                            choice = chunk["choices"][0]
                            delta = choice.get("delta", {})
                            
                            print(f"  delta内容: {json.dumps(delta, ensure_ascii=False, indent=2)}")
                            
                            # 检查推理内容
                            if delta.get("reasoning_content"):
                                reasoning_chunks += 1
                                reasoning_chunk = delta["reasoning_content"]
                                print(f"  🧠 推理内容 ({len(reasoning_chunk)} 字符): {repr(reasoning_chunk[:100])}")
                            
                            # 检查最终答案内容
                            if delta.get("content"):
                                content_chunks += 1
                                content_chunk = delta["content"]
                                print(f"  💬 答案内容 ({len(content_chunk)} 字符): {repr(content_chunk[:100])}")
                            
                            # 检查其他字段
                            for key, value in delta.items():
                                if key not in ["reasoning_content", "content"]:
                                    print(f"  🔍 其他字段 {key}: {repr(value)}")
                                    
                    except json.JSONDecodeError as e:
                        print(f"[Chunk {chunk_count}] JSON解析失败: {e}")
                        print(f"  原始内容: {repr(line_text)}")
                    
                    print("-" * 40)
                
                print(f"\n📊 统计结果:")
                print(f"  总chunk数: {chunk_count}")
                print(f"  推理chunk数: {reasoning_chunks}")
                print(f"  内容chunk数: {content_chunks}")
                
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()

async def test_llm_stream_think():
    """测试LLM的stream_think方法"""
    print("\n🔍 测试LLM的stream_think方法...")
    
    try:
        # 创建LLM实例
        config = LLMConfig(
            provider="doubao",
            model_name="test",  # 这里不重要，stream_think会用环境变量
            api_key=os.getenv('ARK_API_KEY') or os.getenv('DOUBAO_API_KEY'),
            api_base=os.getenv('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
        )
        
        llm = DoubaoLLM(config)
        
        # 创建测试消息
        messages = [Message(role=MessageRole.USER, content="简单回答：1+1等于多少？")]
        
        chunk_count = 0
        reasoning_chunks = 0
        content_chunks = 0
        
        print("\n📊 stream_think输出:")
        print("-" * 80)
        
        async for chunk_data in llm.stream_think(messages):
            chunk_count += 1
            chunk_type = chunk_data.get("type")
            
            print(f"[输出 {chunk_count}] 类型: {chunk_type}")
            print(f"  完整数据: {json.dumps(chunk_data, ensure_ascii=False, indent=2)}")
            
            if chunk_type == "reasoning_chunk":
                reasoning_chunks += 1
                content = chunk_data.get("content", "")
                print(f"  🧠 推理内容 ({len(content)} 字符): {repr(content[:100])}")
                
            elif chunk_type == "content_chunk":
                content_chunks += 1
                content = chunk_data.get("content", "")
                print(f"  💬 答案内容 ({len(content)} 字符): {repr(content[:100])}")
                
            elif chunk_type == "think_complete":
                reasoning_content = chunk_data.get("reasoning_content", "")
                final_content = chunk_data.get("content", "")
                print(f"  ✅ 完整推理 ({len(reasoning_content)} 字符): {repr(reasoning_content[:100])}")
                print(f"  ✅ 完整答案 ({len(final_content)} 字符): {repr(final_content[:100])}")
            
            print("-" * 40)
        
        print(f"\n📊 统计结果:")
        print(f"  总输出数: {chunk_count}")
        print(f"  推理输出数: {reasoning_chunks}")
        print(f"  内容输出数: {content_chunks}")
        
    except Exception as e:
        print(f"❌ stream_think测试失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    print("🚀 DoubaoLLM chunk响应调试")
    print("=" * 80)
    
    # 检查环境变量
    api_key = os.getenv('ARK_API_KEY') or os.getenv('DOUBAO_API_KEY')
    if not api_key:
        print("❌ 未设置API密钥，请设置 ARK_API_KEY 或 DOUBAO_API_KEY 环境变量")
        return
    
    # 测试原始API响应
    await test_raw_api_response()
    
    # 测试LLM的stream_think方法
    await test_llm_stream_think()
    
    print("\n🎉 调试完成！")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc() 