"""
标准ReAct Tool节点 - 基于LangGraph ToolNode实现
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

import json
from typing import Dict, Any, List

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole, ToolCall
from tools.base import ToolManager


class ReactToolNode(BaseNode):
    """标准ReAct Tool节点 - 负责执行工具调用"""
    
    def __init__(self, name: str, tool_manager: ToolManager, **kwargs):
        """
        初始化ReAct Tool节点
        
        Args:
            name: 节点名称
            tool_manager: 工具管理器
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.TOOL, "ReAct工具执行节点", **kwargs)
        self.tool_manager = tool_manager
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行工具调用 - 基于LangGraph ToolNode逻辑"""
        context = input_data.context
        
        # 获取最后一条消息中的工具调用
        messages = context.messages
        if not messages:
            return self._no_tool_calls_output()
            
        last_message = messages[-1]
        tool_calls = getattr(last_message, 'tool_calls', None)
        
        if not tool_calls:
            return self._no_tool_calls_output()
        
        # 执行所有工具调用
        tool_outputs = []
        for tool_call in tool_calls:
            try:
                result = await self._execute_single_tool(tool_call)
                tool_outputs.append(result)
            except Exception as e:
                # 创建错误响应
                error_message = Message(
                    role=MessageRole.TOOL,
                    content=f"工具执行失败: {str(e)}",
                    metadata={
                        "tool_call_id": getattr(tool_call, 'id', None),
                        "tool_name": getattr(tool_call, 'name', 'unknown'),
                        "error": True
                    }
                )
                tool_outputs.append(error_message)
        
        # 添加工具输出到上下文
        context.messages.extend(tool_outputs)
        
        return NodeOutput(
            data={
                "messages": tool_outputs,
                "tool_results": [msg.content for msg in tool_outputs],
                "tools_executed": len(tool_outputs)
            },
            next_node=None,  # 总是返回到agent节点
            should_continue=True,
            metadata={
                "node_type": "react_tool",
                "successful_tools": sum(1 for msg in tool_outputs 
                                       if not msg.metadata.get("error", False))
            }
        )
    
    async def _execute_single_tool(self, tool_call) -> Message:
        """执行单个工具调用（支持角色插件自动注入）"""
        tool_name = getattr(tool_call, 'name', None)
        tool_args = getattr(tool_call, 'arguments', {})
        tool_id = getattr(tool_call, 'id', None)
        
        if not tool_name:
            raise ValueError("工具调用缺少工具名称")
        
        # 执行工具 - 优先使用MCPToolManager的增强功能
        if hasattr(self.tool_manager, 'inject_role_context_to_arguments'):
            print(f"[ReactToolNode._execute_single_tool] 检测到MCPToolManager，准备注入角色上下文")
            # 这是MCPToolManager，它会在execute_tool内部自动调用inject_role_context_to_arguments
            result = await self.tool_manager.execute_tool(tool_name, tool_args)
        else:
            print(f"[ReactToolNode._execute_single_tool] 使用基础ToolManager")
            # 这是基础ToolManager
            result = await self.tool_manager.execute_tool(tool_name, tool_args)
        
        # 格式化结果
        if isinstance(result, dict):
            content = json.dumps(result, ensure_ascii=False, indent=2)
        elif isinstance(result, (list, tuple)):
            content = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            content = str(result)
        
        # 创建工具响应消息
        return Message(
            role=MessageRole.TOOL,
            content=content,
            metadata={
                "tool_call_id": tool_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
                "error": False
            }
        )
    
    def _no_tool_calls_output(self) -> NodeOutput:
        """没有工具调用时的输出"""
        return NodeOutput(
            data={
                "messages": [],
                "tool_results": [],
                "tools_executed": 0
            },
            next_node=None,
            should_continue=False,
            metadata={
                "node_type": "react_tool",
                "no_tool_calls": True
            }
        ) 