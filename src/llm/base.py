"""
LLM基类和工厂
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, AsyncIterator, Type
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
                      **kwargs) -> Message:
        """生成回复 - 子类必须实现"""
        pass
        
    @abstractmethod
    async def stream_generate(self,
                            messages: List[Message],
                            **kwargs) -> AsyncIterator[str]:
        """流式生成 - 子类必须实现"""
        pass


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