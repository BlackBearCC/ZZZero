"""
行动节点 - 负责选择和执行工具
"""
from typing import Dict, Any, Optional, List

from ..core.base import BaseNode
from ..core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole, ToolCall
from ..llm.base import BaseLLMProvider
from ..parsers.tool_parser import ToolCallParser
from ..tools.base import ToolManager


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
        
        return NodeOutput(
            data={
                "action": response.content,
                "tool_calls": [tc.model_dump() for tc in tool_calls],
                "results": results
            },
            next_node="observe" if should_continue else "finalize",
            should_continue=should_continue,
            metadata={
                "tools_used": [tc.name for tc in tool_calls],
                "success_count": sum(1 for r in results if r.get("success", False))
            }
        )
        
    def _build_action_prompt(self, context: Any, thought: Optional[str]) -> str:
        """构建行动提示"""
        # 获取可用工具描述
        tools_desc = self.tool_manager.get_tools_description()
        
        prompt = f"""基于以下思考，选择合适的工具来执行：

{thought if thought else "需要采取行动来解决问题。"}

可用工具：
{tools_desc}

请选择一个或多个工具来执行。使用以下JSON格式：

```json
{{
    "tool": "工具名称",
    "arguments": {{
        "参数名": "参数值"
    }}
}}
```

如果需要调用多个工具，可以返回多个JSON块。

重要：
1. 只选择必要的工具
2. 确保参数正确且完整
3. 工具名称必须与可用工具列表中的名称完全匹配"""
        
        return prompt 