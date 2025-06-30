"""
LLM基类和工厂
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, AsyncIterator, Type, NamedTuple
import asyncio
from enum import Enum

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.base import BaseLLM
from core.types import Message, MessageRole, LLMConfig


class LLMProvider(str, Enum):
    """LLM提供商枚举"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DOUBAO = "doubao"
    CUSTOM = "custom"


class ThinkResult(NamedTuple):
    """推理结果数据结构 - 基础定义"""
    reasoning_content: str  # 推理过程内容
    content: str           # 最终答案内容
    metadata: Dict[str, Any]  # 元数据信息


class BaseLLMProvider(BaseLLM):
    """LLM提供商基类"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
        
    async def initialize(self):
        """初始化客户端"""
        pass
        
    async def cleanup(self):
        """清理资源"""
        if self._client:
            await self._client.close()
            
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """转换消息格式"""
        converted = []
        for msg in messages:
            converted.append({
                "role": msg.role,
                "content": msg.content
            })
        return converted
        
    async def generate_with_retry(self, 
                                 messages: List[Message],
                                 **kwargs) -> Message:
        """带重试的生成"""
        last_error = None
        for attempt in range(self.config.retry_times):
            try:
                return await self.generate(messages, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.config.retry_times - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                    
        raise last_error
        
    @abstractmethod
    async def generate(self, 
                      messages: List[Message],
                      mode: str = "normal",
                      **kwargs) -> Message:
        """生成回复 - 子类必须实现
        
        Args:
            messages: 消息列表
            mode: 生成模式，'normal' 或 'think'
            **kwargs: 其他参数
        """
        pass
        
    @abstractmethod
    async def stream_generate(self,
                            messages: List[Message],
                            mode: str = "normal",
                            **kwargs) -> AsyncIterator[str]:
        """流式生成 - 子类必须实现
        
        Args:
            messages: 消息列表
            mode: 生成模式，'normal' 或 'think'
            **kwargs: 其他参数
        """
        pass
    
    async def _think(self, 
                   messages: List[Message],
                   **kwargs) -> ThinkResult:
        """
        推理接口 - 默认实现，子类可以重写以支持专用推理模型
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            ThinkResult: 包含推理过程和最终答案的结果
        """
        # 默认实现：使用普通generate，没有推理过程
        response = await self.generate(messages, **kwargs)
        
        return ThinkResult(
            reasoning_content="",  # 默认没有推理过程
            content=response.content,
            metadata={
                "model": getattr(self.config, 'model_name', 'unknown'),
                "has_reasoning": False,
                "is_default_implementation": True,
                **response.metadata
            }
        )
    
    async def _stream_think(self,
                          messages: List[Message],
                          **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """
        流式推理接口 - 默认实现，子类可以重写
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Yields:
            Dict: 包含推理过程或最终答案的流式数据
        """
        # 默认实现：使用普通stream_generate
        accumulated_content = ""
        
        async for chunk in self.stream_generate(messages, **kwargs):
            accumulated_content += chunk
            yield {
                "type": "content_chunk",
                "content": chunk,
                "accumulated_content": accumulated_content
            }
        
        # 发送完成信号
        yield {
            "type": "think_complete",
            "reasoning_content": "",  # 默认没有推理过程
            "content": accumulated_content,
            "metadata": {
                "model": getattr(self.config, 'model_name', 'unknown'),
                "has_reasoning": False,
                "is_default_implementation": True,
                "content_length": len(accumulated_content)
            }
        }


class LLMFactory:
    """LLM工厂类"""
    
    _providers: Dict[str, Type[BaseLLMProvider]] = {}
    
    @classmethod
    def register(cls, provider: str, provider_class: Type[BaseLLMProvider]):
        """注册LLM提供商"""
        cls._providers[provider] = provider_class
        
    @classmethod
    def create(cls, config: LLMConfig) -> BaseLLMProvider:
        """创建LLM实例"""
        provider = config.provider
        if provider not in cls._providers:
            raise ValueError(f"未知的LLM提供商: {provider}")
            
        provider_class = cls._providers[provider]
        return provider_class(config)
        
    @classmethod
    def list_providers(cls) -> List[str]:
        """列出所有已注册的提供商"""
        return list(cls._providers.keys()) 