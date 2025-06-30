"""
豆包(Doubao) LLM 实现
"""
import json
import aiohttp
from typing import List, Dict, Any, AsyncIterator, Optional, NamedTuple
from datetime import datetime

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
        使用DeepSeek R1推理模型进行思考
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            ThinkResult: 包含推理过程和最终答案的结果
        """
        # 获取DeepSeek R1模型名称，默认从环境变量获取
        deepseek_model = os.getenv('DOUBAO_MODEL_DEEPSEEKR1', 'deepseek-reasoner')
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        # 转换消息格式
        formatted_messages = self._convert_messages(messages)
        
        # 构建请求数据 - DeepSeek R1推理模型专用配置
        data = {
            "model": deepseek_model,
            "messages": formatted_messages,
            "temperature": kwargs.get("temperature", 0.6),  # DeepSeek R1推荐温度
            "max_tokens": kwargs.get("max_tokens", 16384),  # DeepSeek R1最大支持16384 tokens
        }
        
        # DeepSeek R1不支持的参数，需要过滤
        unsupported_params = ['top_p', 'presence_penalty', 'frequency_penalty']
        if self.config.extra_params:
            filtered_params = {k: v for k, v in self.config.extra_params.items() 
                             if k not in unsupported_params}
            data.update(filtered_params)
            
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
                
                # 提取推理内容和最终答案
                choice = result["choices"][0]["message"]
                reasoning_content = choice.get("reasoning_content", "")
                content = choice.get("content", "")
                
                # 构建元数据
                metadata = {
                    "model": deepseek_model,
                    "usage": result.get("usage", {}),
                    "finish_reason": result["choices"][0].get("finish_reason"),
                    "has_reasoning": bool(reasoning_content),
                    "reasoning_length": len(reasoning_content),
                    "content_length": len(content)
                }
                
                return ThinkResult(
                    reasoning_content=reasoning_content,
                    content=content,
                    metadata=metadata
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
            Dict: 包含推理过程或最终答案的流式数据
        """
        # 获取DeepSeek R1模型名称
        deepseek_model = os.getenv('DOUBAO_MODEL_DEEPSEEKR1', 'deepseek-reasoner')
        
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
                
                # 累积内容用于构建完整结果
                accumulated_reasoning = ""
                accumulated_content = ""
                
                # 处理流式响应
                async for line in response.content:
                    line_text = line.decode('utf-8').strip()
                    if not line_text:
                        continue
                        
                    if line_text.startswith("data: "):
                        line_text = line_text[6:]
                        
                    if line_text == "[DONE]":
                        # 发送最终完整结果
                        yield {
                            "type": "think_complete",
                            "reasoning_content": accumulated_reasoning,
                            "content": accumulated_content,
                            "metadata": {
                                "model": deepseek_model,
                                "has_reasoning": bool(accumulated_reasoning),
                                "reasoning_length": len(accumulated_reasoning),
                                "content_length": len(accumulated_content)
                            }
                        }
                        break
                        
                    try:
                        chunk = json.loads(line_text)
                        
                        if chunk.get("choices") and len(chunk["choices"]) > 0:
                            choice = chunk["choices"][0]
                            delta = choice.get("delta", {})
                            
                            # 处理推理内容
                            if delta.get("reasoning_content"):
                                reasoning_chunk = delta["reasoning_content"]
                                accumulated_reasoning += reasoning_chunk
                                yield {
                                    "type": "reasoning_chunk",
                                    "content": reasoning_chunk,
                                    "accumulated_reasoning": accumulated_reasoning
                                }
                            
                            # 处理最终答案内容
                            if delta.get("content"):
                                content_chunk = delta["content"]
                                accumulated_content += content_chunk
                                yield {
                                    "type": "content_chunk",
                                    "content": content_chunk,
                                    "accumulated_content": accumulated_content
                                }
                                
                    except json.JSONDecodeError as e:
                        # 跳过JSON解析错误，但输出调试信息
                        print(f"[DoubaoLLM.stream_think] JSON解析失败: {line_text[:100]}")
                        continue
                    except Exception as e:
                        print(f"[DoubaoLLM.stream_think] 处理chunk时出错: {e}")
                        continue
            
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
                                           mode: str = "normal",
                                           interrupt_checker=None,
                                           **kwargs) -> AsyncIterator[str]:
        """支持中断检查的流式生成
        
        Args:
            messages: 消息列表
            mode: 生成模式，'normal' 或 'think'
            interrupt_checker: 中断检查器（可选）
            **kwargs: 其他参数
        """
        # 如果是think模式，使用流式think
        if mode == "think":
            accumulated_reasoning = ""
            accumulated_content = ""
            
            async for result in self._stream_think(messages, **kwargs):
                if result.get("type") == "reasoning_chunk":
                    reasoning_chunk = result.get("content", "")
                    accumulated_reasoning += reasoning_chunk
                    # 输出推理过程
                    if not accumulated_content:  # 第一次输出时添加标题
                        if not accumulated_reasoning.startswith("**🧠 推理过程：**"):
                            yield "**🧠 推理过程：**\n"
                    yield reasoning_chunk
                
                elif result.get("type") == "content_chunk":
                    content_chunk = result.get("content", "")
                    if not accumulated_content:  # 第一次输出内容时添加分隔符
                        yield "\n\n**结论：**\n"
                    accumulated_content += content_chunk
                    yield content_chunk
                
                elif result.get("type") == "think_complete":
                    # think完成，不需要额外输出
                    break
                
                # 中断检查
                if interrupt_checker and interrupt_checker(accumulated_reasoning + accumulated_content):
                    break
            return
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