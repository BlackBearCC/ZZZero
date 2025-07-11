"""
标准ReAct Agent节点 - 基于LangGraph最佳实践
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from typing import Dict, Any, List, Sequence, Annotated
from dataclasses import dataclass

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole
from llm.base import BaseLLMProvider


@dataclass
class ReactState:
    """ReAct状态 - 简化的消息状态"""
    messages: Annotated[List[Message], "对话消息列表"]


class ReactAgentNode(BaseNode):
    """标准ReAct Agent节点 - 负责推理和决策"""
    
    def __init__(self, name: str, llm: BaseLLMProvider, tool_manager=None, **kwargs):
        """
        初始化ReAct Agent节点
        
        Args:
            name: 节点名称
            llm: LLM提供者
            tool_manager: 工具管理器（可选）
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.AGENT, "ReAct智能代理节点", **kwargs)
        self.llm = llm
        self.tool_manager = tool_manager
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行ReAct推理逻辑"""
        context = input_data.context
        
        # 获取对话历史
        messages = context.messages.copy()
        
        # 添加系统提示 - 基于LangGraph标准ReAct模式
        system_prompt = self._build_system_prompt(context)
        if not any(msg.role == MessageRole.SYSTEM for msg in messages):
            messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ))
        
        # 调用LLM进行推理和决策
        response = await self.llm.generate(messages)
        
        # 添加响应到上下文
        context.messages.append(response)
        
        # 安全获取tool_calls，处理None情况
        tool_calls = getattr(response, 'tool_calls', None)
        tool_calls_list = tool_calls if tool_calls is not None else []
        
        return NodeOutput(
            data={
                "messages": [response],
                "agent_response": response.content,
                "has_tool_calls": bool(tool_calls)
            },
            next_node=None,  # 由条件边决定
            should_continue=True,
            metadata={
                "node_type": "react_agent",
                "tool_calls_count": len(tool_calls_list)
            }
        )
    
    def _build_system_prompt(self, context: Any) -> str:
        """构建标准ReAct系统提示词 - 支持记忆和角色插件"""
        base_prompt = ""
        
        # 从上下文中获取记忆信息
        memory_context = ""
        if hasattr(context, 'variables') and context.variables:
            memory_context = context.variables.get("memory_context", "")
            memory_manager = context.variables.get("memory_manager")
        
        # 添加记忆上下文
        if memory_context:
            base_prompt += f"=== 记忆上下文 ===\n{memory_context}\n\n"
        
        # 获取工具描述
        tools_desc = ""
        tool_names = []
        
        # 从工具管理器获取工具信息
        if self.tool_manager:
            tools_desc = self.tool_manager.get_tools_description()
            tool_names = self.tool_manager.list_tools()
        
        # 标准ReAct提示词模板 - 强制Thought开头
        if tools_desc:
            base_prompt += "你是一个专业的AI助手，严格遵守ReAct推理模式。\n\n"
            base_prompt += "【重要规则】无论什么情况，你都必须以'Thought:'开头，这是不可违背的规则！\n\n"
            base_prompt += f"可用工具：\n{tools_desc}\n\n"
            base_prompt += "严格按照以下格式进行推理和行动：\n\n"
            base_prompt += "Thought: [必须先思考！分析问题，决定下一步行动]\n"
            base_prompt += f"Action: [选择工具，必须是 {', '.join(tool_names)} 中的一个]\n"
            base_prompt += "Action Input: [工具输入参数]\n"
            base_prompt += "Observation: [系统自动填充工具结果]\n"
            base_prompt += "Thought: [分析结果，决定是否继续]\n"
            base_prompt += "... (重复这个循环直到获得足够信息)\n"
            base_prompt += "Thought: [最终分析和结论]\n"
            base_prompt += "Final Answer: [对问题的最终答案]\n\n"
            base_prompt += "重要规则：\n"
            base_prompt += "1. ❗ 每次回复都必须以'Thought:'开头\n"
            base_prompt += "2. 🛠️ 如需信息，合理使用工具\n"
            base_prompt += "3. 🔢 每次只使用一个工具\n"
            base_prompt += "4. 🔍 仔细分析工具返回结果\n"
            base_prompt += "5. 💡 充分利用记忆上下文\n"
            base_prompt += "6. 🎭 如需角色扮演，使用role_info工具\n"
            base_prompt += "7. ❗ 再次强调：如果不以'Thought:'开头，将被认为错误\n\n"
            base_prompt += "现在开始，记住必须从Thought开始："
        else:
            base_prompt += "你是一个专业的AI助手，即使没有外部工具也要遵守思考规则。\n\n"
            base_prompt += "【重要规则】无论什么情况，你都必须以'Thought:'开头，这是不可违背的规则！\n\n"
            base_prompt += "回复格式：\n"
            base_prompt += "Thought: [必须先思考！分析问题，基于知识进行推理]\n"
            base_prompt += "Final Answer: [基于思考给出的专业答案]\n\n"
            base_prompt += "工作原则：\n"
            base_prompt += "1. 📋 必须以'Thought:'开头进行思考\n"
            base_prompt += "2. 💡 基于知识库提供专业帮助\n"
            base_prompt += "3. 🔍 如果不确定，诚实说明\n"
            base_prompt += "4. 💡 充分利用历史信息\n"
            base_prompt += "5. ❗ 再次强调：必须从Thought开始\n\n"
            base_prompt += "现在开始，记住必须从Thought开始："
        
        return base_prompt
    
    def _get_default_template(self):
        """获取默认模板（保持兼容性）"""
        return None 