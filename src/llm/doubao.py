"""
豆包(Doubao) LLM 实现
"""
import json
import aiohttp
from typing import List, Dict, Any, AsyncIterator, Optional, NamedTuple
from datetime import datetime
import logging
import asyncio

from .base import BaseLLMProvider, LLMFactory, ThinkResult
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
    
    async def _think(self, 
                   messages: List[Message],
                   **kwargs) -> ThinkResult:
        """
        思考接口 - 支持DeepSeek R1的推理思考输出
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            ThinkResult: 包含推理过程和最终答案的结构
        """
        # 获取DeepSeek R1模型名称
        deepseek_model = os.getenv('DOUBAO_MODEL_DEEPSEEKR1', 'ep-20250221154107-c4qc7')
        
        # 确保API基础URL存在
        if not self.config.api_base:
            self.config.api_base = os.getenv('DOUBAO_BASE_URL', "https://ark.cn-beijing.volces.com/api/v3")
            if not self.config.api_base:
                raise ValueError("豆包API基础URL未设置，请在环境变量中设置DOUBAO_BASE_URL或在配置中提供api_base")
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        # 转换消息格式
        formatted_messages = self._convert_messages(messages)
        
        # 构建请求数据
        data = {
            "model": deepseek_model,
            "messages": formatted_messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 16384),  # DeepSeek R1最大支持16384 tokens
        }
        
        # 过滤不支持的参数
        if self.config.extra_params:
            unsupported_params = ['top_p', 'presence_penalty', 'frequency_penalty']
            filtered_params = {k: v for k, v in self.config.extra_params.items() 
                             if k not in unsupported_params}
            data.update(filtered_params)
            
        # 设置较长的超时时间
        timeout_config = aiohttp.ClientTimeout(total=1800)
            
        # 发送请求
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.post(
                f"{self.config.api_base}/chat/completions",
                headers=headers,
                json=data,
                timeout=timeout_config
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"豆包API调用失败: {error_text}")
                    
                result = await response.json()
                
                # 提取推理内容和最终答案
                message = result["choices"][0]["message"]
                
                # 创建ThinkResult对象
                return ThinkResult(
                    content=message.get("content", ""),  # 实际结果内容
                    reasoning_content=message.get("reasoning_content", ""),  # 推理过程
                    metadata={
                        "model": deepseek_model,
                        "usage": result.get("usage", {}),
                        "finish_reason": result["choices"][0].get("finish_reason")
                    }
                )
    
    async def _stream_think(self,
                          messages: List[Message],
                          **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """
        流式推理接口 - 支持DeepSeek R1的流式推理输出
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Yields:
            Dict: 包含推理过程或最终答案的增量数据
        """
        # 获取DeepSeek R1模型名称
        deepseek_model = os.getenv('DOUBAO_MODEL_DEEPSEEKR1', 'ep-20250221154107-c4qc7')
        
        # 确保API基础URL存在
        if not self.config.api_base:
            self.config.api_base = os.getenv('DOUBAO_BASE_URL', "https://ark.cn-beijing.volces.com/api/v3")
            if not self.config.api_base:
                raise ValueError("豆包API基础URL未设置，请在环境变量中设置DOUBAO_BASE_URL或在配置中提供api_base")
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        # 转换消息格式
        formatted_messages = self._convert_messages(messages)
        
        # 构建流式请求数据
        data = {
            "model": deepseek_model,
            "messages": formatted_messages,
            "temperature": kwargs.get("temperature", 0.6),
            "max_tokens": kwargs.get("max_tokens", 16384),  # DeepSeek R1最大支持16384 tokens
            "stream": True,
            "stream_options": {
                "include_usage": True
            }
        }
        
        # 过滤不支持的参数
        if self.config.extra_params:
            unsupported_params = ['top_p', 'presence_penalty', 'frequency_penalty']
            filtered_params = {k: v for k, v in self.config.extra_params.items() 
                             if k not in unsupported_params}
            data.update(filtered_params)
            
        # 发送流式请求 - 使用较长的超时时间
        timeout = aiohttp.ClientTimeout(total=1800)  # 30分钟超时
        logging.info(f"[DoubaoLLM] 开始流式LLM请求，设置超时时间为{timeout.total}秒")
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.config.api_base}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=timeout  # 使用同样的超时设置
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logging.error(f"[DoubaoLLM] API调用失败: HTTP {response.status}, {error_text}")
                        raise Exception(f"豆包API调用失败: {error_text}")
                    
                    logging.info(f"[DoubaoLLM] 成功建立流式连接，开始接收数据")
                    chunk_count = 0
                    
                    # 处理流式响应
                    async for line in response.content:
                        chunk_count += 1
                            
                        line_text = line.decode('utf-8').strip()
                        if not line_text:
                            continue
                            
                        if line_text.startswith("data: "):
                            line_text = line_text[6:]
                            
                        if line_text == "[DONE]":
                            logging.info(f"[DoubaoLLM] 流式请求完成，总共接收 {chunk_count} 个数据块")
                            # 发送完成信号
                            yield {
                                "type": "think_complete",
                                "metadata": {
                                    "model": deepseek_model,
                                    "total_chunks": chunk_count
                                }
                            }
                            break
                            
                        try:
                            chunk = json.loads(line_text)
                            
                            if chunk.get("choices") and len(chunk["choices"]) > 0:
                                choice = chunk["choices"][0]
                                delta = choice.get("delta", {})
                                
                                # 处理推理内容 - 只返回增量
                                if delta.get("reasoning_content"):
                                    reasoning_chunk = delta["reasoning_content"]
                                    print(reasoning_chunk, end='', flush=True)
                                    yield {
                                        "type": "reasoning_chunk",
                                        "content": reasoning_chunk
                                    }
                                
                                # 处理最终答案内容 - 只返回增量
                                if delta.get("content"):
                                    content_chunk = delta["content"]
                                    print(content_chunk, end='', flush=True)
                                    yield {
                                        "type": "content_chunk",
                                        "content": content_chunk
                                    }
                                    
                        except json.JSONDecodeError as e:
                            # 跳过JSON解析错误，但输出调试信息
                            logging.warning(f"[DoubaoLLM] JSON解析失败: {line_text[:100]}")
                            continue
                        except Exception as e:
                            logging.error(f"[DoubaoLLM] 处理chunk时出错: {e}")
                            continue
        except asyncio.TimeoutError:
            logging.error(f"[DoubaoLLM] 流式请求超时，已配置的超时时间为 {timeout.total} 秒")
            raise Exception(f"豆包API请求超时，已等待 {timeout.total} 秒")
        except Exception as e:
            logging.error(f"[DoubaoLLM] 流式请求异常: {type(e).__name__}: {e}")
            raise
    
    async def generate(self, 
                      messages: List[Message],
                      mode: str = "normal",
                      **kwargs) -> Message:
        """生成回复
        
        Args:
            messages: 消息列表
            mode: 生成模式，'normal' 或 'think'
            **kwargs: 其他参数
        """
        # 如果是think模式，调用think方法并返回Message格式
        if mode == "think":
            think_result = await self._think(messages, **kwargs)
            
            # 只返回最终内容，推理过程通过metadata传递
            return Message(
                role=MessageRole.ASSISTANT,
                content=think_result.content,
                metadata={
                    **think_result.metadata,
                    "mode": "think",
                    "has_reasoning": bool(think_result.reasoning_content),
                    "reasoning_content": think_result.reasoning_content
                }
            )
            
        # 确保API基础URL存在
        if not self.config.api_base:
            self.config.api_base = os.getenv('DOUBAO_BASE_URL', "https://ark.cn-beijing.volces.com/api/v3")
            if not self.config.api_base:
                raise ValueError("豆包API基础URL未设置，请在环境变量中设置DOUBAO_BASE_URL或在配置中提供api_base")
                
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
            
        # 设置较长的超时时间
        timeout_config = aiohttp.ClientTimeout(total=1800)  # 30分钟超时
            
        # 发送请求
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.post(
                f"{self.config.api_base}/chat/completions",
                headers=headers,
                json=data,
                timeout=timeout_config
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
                             mode: str = "normal",
                             interrupt_checker=None,
                             timeout: int = None,
                             return_dict: bool = False,
                             **kwargs):
        """支持中断检查的流式生成
        
        Args:
            messages: 消息列表
            mode: 生成模式，'normal' 或 'think'
            interrupt_checker: 中断检查器（可选）
            timeout: 超时时间（秒），不设置则无超时限制
            return_dict: 是否返回字典格式（工作流使用）
            **kwargs: 其他参数
        """
        # 确保API基础URL存在
        if not self.config.api_base:
            self.config.api_base = os.getenv('DOUBAO_BASE_URL', "https://ark.cn-beijing.volces.com/api/v3")
            if not self.config.api_base:
                raise ValueError("豆包API基础URL未设置，请在环境变量中设置DOUBAO_BASE_URL或在配置中提供api_base")
        
        # 设置较长的超时时间，如果未指定则使用默认值
        if timeout is None:
            actual_timeout = 1800  # 30分钟默认超时
        else:
            actual_timeout = timeout
            
        # 创建aiohttp超时对象
        timeout_config = aiohttp.ClientTimeout(total=actual_timeout)
        
        # 如果是think模式，使用流式think
        if mode == "think":
            async for result in self._stream_think(messages, **kwargs):
                if result.get("type") == "reasoning_chunk":
                    reasoning_chunk = result.get("content", "")
                    
                    if return_dict:
                        # 为工作流返回字典格式，区分think和content
                        yield {
                            "think": reasoning_chunk,
                            "content": "",
                            "type": "reasoning_chunk"
                        }
                    else:
                        # 为普通聊天返回字符串格式
                        yield reasoning_chunk
                
                elif result.get("type") == "content_chunk":
                    content_chunk = result.get("content", "")
                    
                    if return_dict:
                        # 为工作流返回字典格式
                        yield {
                            "think": "",
                            "content": content_chunk,
                            "type": "content_chunk"
                        }
                    else:
                        # 为普通聊天返回字符串格式
                        yield content_chunk
                
                elif result.get("type") == "think_complete":
                    if return_dict:
                        # think完成信号
                        yield {
                            "think": "",
                            "content": "",
                            "type": "think_complete"
                        }
                    break
                
                # 中断检查 - 这里需要调用方自己维护累加内容进行检查
                if interrupt_checker and interrupt_checker(""):  # 传空字符串，让调用方处理
                    break
            return
            
        # Normal模式的流式生成
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
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.post(
                f"{self.config.api_base}/chat/completions",
                headers=headers,
                json=data,
                timeout=timeout_config
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"豆包API调用失败: {error_text}")
                    
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
                                    break
                                
                                if return_dict:
                                    yield {
                                        "think": "",
                                        "content": content_chunk,
                                        "type": "content_chunk"
                                    }
                                else:
                                    yield content_chunk
                                    
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logging.error(f"处理流式响应时出错: {e}")
                        continue
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """转换消息格式为豆包API所需格式，支持多模态（图片）内容"""
        converted = []
        for msg in messages:
            role = "user" if msg.role == MessageRole.USER else "assistant"
            if msg.role == MessageRole.SYSTEM:
                role = "system"
            
            # 检查是否有图片内容（存储在metadata中）
            if msg.metadata and msg.metadata.get("has_image", False):
                # 多模态消息格式
                image_data = msg.metadata.get("image_data", "")
                image_mime = msg.metadata.get("image_mime", "image/jpeg")
                
                if image_data:
                    # 构建多模态内容
                    converted.append({
                        "role": role,
                        "content": [
                            {"type": "text", "text": msg.content},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_mime};base64,{image_data}"
                                }
                            }
                        ]
                    })
                    continue
            
            # 普通文本消息
            converted.append({
                "role": role,
                "content": msg.content
            })
        
        return converted
    
    def estimate_tokens(self, text: str) -> int:
        """估算文本的token数量
        
        Args:
            text: 要估算的文本
            
        Returns:
            估算的token数量
        """
        if not text:
            return 0
        
        # 简单的token估算：中文字符按1.5计算，英文按4个字符1个token计算
        chinese_count = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        english_count = len(text) - chinese_count
        
        return int(chinese_count / 1.5 + english_count / 4)


# 注册到工厂
LLMFactory.register("doubao", DoubaoLLM) 