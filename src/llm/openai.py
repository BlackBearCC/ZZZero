"""
OpenAI LLM 实现
"""
import json
import aiohttp
from typing import List, Dict, Any, AsyncIterator, Optional

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from llm.base import BaseLLMProvider, LLMFactory
from core.types import Message, MessageRole


class OpenAILLM(BaseLLMProvider):
    """OpenAI LLM实现"""
    
    async def initialize(self):
        """初始化客户端"""
        # 如果没有传入api_key，尝试从环境变量获取
        if not self.config.api_key:
            self.config.api_key = os.getenv('OPENAI_API_KEY')
            
        if not self.config.api_key:
            raise ValueError("OpenAI API密钥未设置，请在环境变量中设置 OPENAI_API_KEY")
            
        # 设置默认API基础URL
        if not self.config.api_base:
            # 优先使用环境变量中的URL
            self.config.api_base = os.getenv('OPENAI_BASE_URL', "https://api.openai.com/v1")
            
    async def generate(self, 
                      messages: List[Message],
                      **kwargs) -> Message:
        """生成回复"""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        # 转换消息格式
        formatted_messages = self._convert_messages(messages)
        
        # 处理工具调用
        tool_calls = []
        for msg in messages:
            if msg.tool_calls:
                tool_calls.extend(msg.tool_calls)
                
        # 构建请求数据
        data = {
            "model": self.config.model_name,
            "messages": formatted_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        
        # 如果有工具定义，添加到请求中
        if "tools" in kwargs:
            data["tools"] = kwargs["tools"]
            data["tool_choice"] = kwargs.get("tool_choice", "auto")
            
        # 添加额外参数
        if self.config.extra_params:
            data.update(self.config.extra_params)
            
        # 发送请求
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.config.api_base}/chat/completions",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API调用失败: {error_text}")
                    
                result = await response.json()
                
                # 提取回复内容
                choice = result["choices"][0]
                message = choice["message"]
                
                # 处理工具调用
                tool_calls = None
                if "tool_calls" in message:
                    from core.types import ToolCall
                    tool_calls = []
                    for tc in message["tool_calls"]:
                        tool_calls.append(ToolCall(
                            id=tc["id"],
                            name=tc["function"]["name"],
                            arguments=json.loads(tc["function"]["arguments"])
                        ))
                
                # 创建响应消息
                return Message(
                    role=MessageRole.ASSISTANT,
                    content=message.get("content", ""),
                    tool_calls=tool_calls,
                    metadata={
                        "model": self.config.model_name,
                        "usage": result.get("usage", {}),
                        "finish_reason": choice.get("finish_reason")
                    }
                )
                
    async def stream_generate(self,
                            messages: List[Message],
                            **kwargs) -> AsyncIterator[str]:
        """流式生成回复"""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        # 转换消息格式
        formatted_messages = self._convert_messages(messages)
        
        # 构建请求数据
        data = {
            "model": self.config.model_name,
            "messages": formatted_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "stream": True
        }
        
        # 如果有工具定义，添加到请求中
        if "tools" in kwargs:
            data["tools"] = kwargs["tools"]
            data["tool_choice"] = kwargs.get("tool_choice", "auto")
            
        # 添加额外参数
        if self.config.extra_params:
            data.update(self.config.extra_params)
            
        # 发送流式请求
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.config.api_base}/chat/completions",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API调用失败: {error_text}")
                    
                # 处理流式响应
                async for line in response.content:
                    line_text = line.decode('utf-8').strip()
                    if not line_text:
                        continue
                        
                    if line_text.startswith("data: "):
                        line_text = line_text[6:]
                        
                    if line_text == "[DONE]":
                        break
                        
                    try:
                        chunk = json.loads(line_text)
                        
                        # 提取增量内容
                        if chunk.get("choices") and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                                
                    except json.JSONDecodeError:
                        continue
                        
    def count_tokens(self, text: str) -> int:
        """估算token数量"""
        # 使用tiktoken库进行更准确的计算
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.config.model_name)
            return len(encoding.encode(text))
        except:
            # 如果没有安装tiktoken，使用简单估算
            return len(text) // 4


# 注册到工厂
LLMFactory.register("openai", OpenAILLM) 