"""
行动节点 - 负责选择和执行工具
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from typing import Dict, Any, Optional, List

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole, ToolCall
from llm.base import BaseLLMProvider
from parsers.tool_parser import ToolCallParser
from tools.base import ToolManager


class ActNode(BaseNode):
    """行动节点 - 选择并执行工具"""
    
    def __init__(self,
                 name: str,
                 llm: BaseLLMProvider,
                 tool_manager: ToolManager,
                 parser: Optional[ToolCallParser] = None,
                 **kwargs):
        """
        初始化行动节点
        
        Args:
            name: 节点名称
            llm: LLM提供者
            tool_manager: 工具管理器
            parser: 工具调用解析器
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.ACT, "选择并执行工具", **kwargs)
        self.llm = llm
        self.tool_manager = tool_manager
        self.parser = parser or ToolCallParser()
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行行动逻辑"""
        context = input_data.context
        
        # 从之前的思考中获取信息
        thought = None
        if input_data.previous_output and isinstance(input_data.previous_output, dict):
            thought = input_data.previous_output.get("thought", "")
            
        # 构建工具选择提示
        action_prompt = self._build_action_prompt(context, thought)
        
        # 添加提示到消息历史
        context.messages.append(Message(
            role=MessageRole.USER,
            content=action_prompt
        ))
        
        # 调用LLM选择工具
        response = await self.llm.generate(context.messages)
        
        # 添加响应到消息历史
        context.messages.append(response)
        
        # 检查是否选择跳过工具使用
        if "跳过工具使用" in response.content or "不使用工具" in response.content:
            # 用户选择不使用工具，直接进入最终化阶段
            return NodeOutput(
                data={
                    "action": response.content,
                    "tool_calls": [],
                    "results": [],
                    "skipped_tools": True
                },
                next_node="finalize",
                should_continue=False,
                metadata={
                    "tools_used": [],
                    "success_count": 0,
                    "action_type": "skip_tools"
                }
            )
        
        # 解析工具调用
        tool_calls = await self.parser.aparse(response.content)
        
        # 执行工具调用
        results = []
        if tool_calls:
            for tool_call in tool_calls:
                try:
                    result = await self.tool_manager.execute_tool(
                        tool_call.name,
                        tool_call.arguments
                    )
                    tool_call.result = result
                    results.append({
                        "tool": tool_call.name,
                        "arguments": tool_call.arguments,
                        "result": result,
                        "success": True
                    })
                except Exception as e:
                    tool_call.error = str(e)
                    results.append({
                        "tool": tool_call.name,
                        "arguments": tool_call.arguments,
                        "error": str(e),
                        "success": False
                    })
        
        # 决定是否需要继续
        should_continue = len(results) > 0
        next_node = "observe" if should_continue else "finalize"
        
        return NodeOutput(
            data={
                "action": response.content,
                "tool_calls": [tc.model_dump() for tc in tool_calls] if tool_calls else [],
                "results": results
            },
            next_node=next_node,
            should_continue=should_continue,
            metadata={
                "tools_used": [tc.name for tc in tool_calls] if tool_calls else [],
                "success_count": sum(1 for r in results if r.get("success", False)),
                "action_type": "use_tools" if tool_calls else "no_tools"
            }
        )
        
    def _build_action_prompt(self, context: Any, thought: Optional[str]) -> str:
        """构建行动提示"""
        # 获取可用工具描述
        tools_desc = self.tool_manager.get_tools_description()
        
        prompt = f"""【行动阶段】

基于思考结果，现在需要选择具体的行动：

思考结果：
{thought if thought else "需要采取行动来解决问题。"}

现在，这里是可用的工具：
{tools_desc}

行动选择：
你可以选择以下两种行动之一：

**选项1: 使用工具**
如果需要获取更多信息，请使用以下JSON格式选择工具：

```json
{{
    "tool": "工具名称", 
    "arguments": {{
        "参数名": "参数值"
    }}
}}
```

**选项2: 不使用工具**
如果思考阶段已经确定可以直接回答，可以回复"跳过工具使用"。

选择指导：
1. 只选择对解决问题最必要的工具
2. 确保参数正确且完整
3. 工具名称必须与上面列表中的名称完全匹配
4. 每次只选择一个工具以便观察结果

请做出你的选择："""
        
        return prompt 