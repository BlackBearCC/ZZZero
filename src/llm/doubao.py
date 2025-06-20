"""
豆包(Doubao) LLM 实现
"""
import json
import aiohttp
from typing import List, Dict, Any, AsyncIterator, Optional
from datetime import datetime

from .base import BaseLLMProvider, LLMFactory
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.types import Message, MessageRole


class DoubaoLLM(BaseLLMProvider):
    """豆包LLM实现"""
    
    async def initialize(self):
        """初始化客户端"""
        # 如果没有传入api_key，尝试从环境变量获取
        if not self.config.api_key:
            # 按优先级尝试不同的环境变量名
            env_keys = ['ARK_API_KEY', 'DOUBAO_API_KEY', 'ARK_API_KEY_ME']
            for env_key in env_keys:
                api_key = os.getenv(env_key)
                if api_key:
                    self.config.api_key = api_key
                    break
        
        # 再次检查是否有API密钥
        if not self.config.api_key:
            raise ValueError("豆包API密钥未设置，请在环境变量中设置 ARK_API_KEY 或 DOUBAO_API_KEY")
            
        # 设置默认API基础URL
        if not self.config.api_base:
            # 优先使用环境变量中的URL
            self.config.api_base = os.getenv('DOUBAO_BASE_URL', "https://ark.cn-beijing.volces.com/api/v3")
            
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
        
        # 构建请求数据
        data = {
            "model": self.config.model_name,
            "messages": formatted_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        
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
                    raise Exception(f"豆包API调用失败: {error_text}")
                    
                result = await response.json()
                
                # 提取回复内容
                content = result["choices"][0]["message"]["content"]
                
                # 创建响应消息
                return Message(
                    role=MessageRole.ASSISTANT,
                    content=content,
                    metadata={
                        "model": self.config.model_name,
                        "usage": result.get("usage", {}),
                        "finish_reason": result["choices"][0].get("finish_reason")
                    }
                )
                
    async def stream_generate(self,
                                           messages: List[Message],
                                           interrupt_checker=None,
                                           **kwargs) -> AsyncIterator[str]:
        """支持中断检查的流式生成"""
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
            "stream": True,
            "stream_options": {
                "include_usage": True
            }
        }
        
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
                    raise Exception(f"豆包API调用失败: {error_text}")
                    
                # 累积内容用于中断检查
                accumulated_content = ""
                
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
                            choice = chunk["choices"][0]
                            if choice.get("delta") and choice["delta"].get("content"):
                                content_chunk = choice["delta"]["content"]
                                accumulated_content += content_chunk
                                
                                # 如果提供了中断检查器，检查是否需要中断
                                if interrupt_checker and interrupt_checker(accumulated_content):
                                    # 发送当前chunk后中断
                                    yield content_chunk
                                    break
                                
                                yield content_chunk
                                
                    except json.JSONDecodeError:
                        continue
                        
    async def call_llm(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> tuple[bool, str]:
        """统一LLM调用接口，用于批处理器"""
        try:
            # 将prompt转换为Message格式
            messages = [Message(role=MessageRole.USER, content=prompt)]
            
            # 调用generate方法
            response = await self.generate(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return True, response.content
            
        except Exception as e:
            return False, str(e)
    
    def count_tokens(self, text: str) -> int:
        """估算token数量"""
        # 中文大约1.5个字符一个token，英文大约4个字符一个token
        # 这里使用简单的估算
        chinese_count = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        english_count = len(text) - chinese_count
        
        return int(chinese_count / 1.5 + english_count / 4)


# 注册到工厂
LLMFactory.register("doubao", DoubaoLLM) 