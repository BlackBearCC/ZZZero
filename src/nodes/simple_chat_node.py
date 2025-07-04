"""
简单对话节点 - 用于没有工具时的对话场景
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from typing import Dict, Any

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole
from llm.base import BaseLLMProvider


class SimpleChatNode(BaseNode):
    """简单对话节点 - 用于无工具的对话场景"""
    
    def __init__(self, name: str, llm: BaseLLMProvider, **kwargs):
        """
        初始化简单对话节点
        
        Args:
            name: 节点名称
            llm: LLM提供者
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.CHAT, "简单对话节点", **kwargs)
        self.llm = llm
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行简单对话逻辑"""
        context = input_data.context
        
        # 获取对话历史
        messages = context.messages.copy()
        
        # 添加系统提示
        if not any(msg.role == MessageRole.SYSTEM for msg in messages):
            system_prompt = self._build_system_prompt(context)
            
            messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ))
        
        # 调用LLM生成回复
        response = await self.llm.generate(messages)
        
        # 添加响应到上下文
        context.messages.append(response)
        
        return NodeOutput(
            data={
                "messages": [response],
                "chat_response": response.content,
                "conversation_ended": True
            },
            next_node=None,
            should_continue=False,  # 简单对话一轮结束
            metadata={
                "node_type": "simple_chat",
                "response_length": len(response.content)
            }
        )
    
    def _build_system_prompt(self, context: Any) -> str:
        """构建简单对话系统提示词 - 支持记忆上下文"""
        base_prompt = ""
        
        # 从上下文中获取记忆信息
        memory_context = ""
        if hasattr(context, 'variables') and context.variables:
            memory_context = context.variables.get("memory_context", "")
        
        # 添加记忆上下文
        if memory_context:
            base_prompt += f"=== 记忆上下文 ===\n{memory_context}\n\n"
        
        base_prompt += "你是一个有用的AI助手。请根据你的知识回答用户的问题。\n"
        base_prompt += "如果你不确定答案，请诚实地说明你不知道，而不是编造信息。\n"
        base_prompt += "请提供清晰、有帮助的回复。\n"
        base_prompt += "如果有记忆上下文，请充分利用这些历史信息为用户提供个性化的回复。"
        
        return base_prompt 