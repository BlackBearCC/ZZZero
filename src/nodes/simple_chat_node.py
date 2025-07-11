"""
被废弃的简单对话节点 - 所有智能体现在都必须从Thought开始

此类已被废弃，请使用ReactAgentNode或StreamReactAgentNode代替。
所有AI回复都必须从Thought开始，不允许直接给出答案。
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from typing import Dict, Any

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole
from llm.base import BaseLLMProvider


class SimpleChatNode(BaseNode):
    """
    【已废弃】简单对话节点 - 不再使用
    
    请使用ReactAgentNode或StreamReactAgentNode代替。
    所有AI回复都必须从"Thought:"开始。
    """
    
    def __init__(self, name: str, llm: BaseLLMProvider, **kwargs):
        """
        【已废弃】不再支持初始化
        
        Args:
            name: 节点名称 - 不再使用
            llm: LLM提供者 - 不再使用
            **kwargs: 其他配置参数 - 不再使用
        """
        raise DeprecationWarning(
            "【SimpleChatNode已废弃】\n"
            "请使用ReactAgentNode或StreamReactAgentNode代替。\n"
            "所有AI回复都必须从'Thought:'开始，\n"
            "不允许使用简单对话模式。"
        )
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """【已废弃】不再支持执行"""
        raise DeprecationWarning(
            "【SimpleChatNode已废弃】\n"
            "请使用ReactAgentNode或StreamReactAgentNode代替。\n"
            "所有AI回复都必须从'Thought:'开始，\n"
            "不允许使用简单对话模式。"
        )
    
    def _build_system_prompt(self, context: Any) -> str:
        """【已废弃】不再支持构建系统提示词"""
        raise DeprecationWarning(
            "【SimpleChatNode已废弃】\n"
            "请使用ReactAgentNode或StreamReactAgentNode代替。\n"
            "所有AI回复都必须从'Thought:'开始，\n"
            "不允许使用简单对话模式。"
        ) 