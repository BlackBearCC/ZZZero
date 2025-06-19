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
        """构建标准ReAct系统提示词 - 基于LangChain ReAct模板"""
        
        # 获取工具描述
        tools_desc = ""
        tool_names = []
        
        # 从工具管理器获取工具信息
        if self.tool_manager:
            tools_desc = self.tool_manager.get_tools_description()
            tool_names = self.tool_manager.list_tools()
        
        # 标准ReAct提示词模板 - 基于LangChain hwchase17/react
        if tools_desc:
            return f"""你是一个有用的AI助手。你可以使用以下工具来回答问题：

{tools_desc}

使用以下格式进行推理和行动：

Question: 你需要回答的问题
Thought: 你应该思考要做什么
Action: 要采取的行动，应该是 [{', '.join(tool_names)}] 中的一个
Action Input: 行动的输入
Observation: 行动的结果
... (这个 Thought/Action/Action Input/Observation 可以重复N次)
Thought: 我现在知道最终答案了
Final Answer: 对原始问题的最终答案

重要规则：
1. 如果你有足够信息回答问题，直接给出 Final Answer
2. 如果需要更多信息，使用可用的工具
3. 每次只使用一个工具
4. 仔细分析工具的返回结果

开始！"""
        else:
            return """你是一个有用的AI助手。请根据你的知识回答用户的问题。

如果你不确定答案，请诚实地说明你不知道，而不是编造信息。
请提供清晰、有帮助的回复。"""
    
    def _get_default_template(self):
        """获取默认模板（保持兼容性）"""
        return None 