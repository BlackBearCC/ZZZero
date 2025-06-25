"""
行动节点 - 负责执行工具调用（支持并行执行多个工具）
"""
import sys
import os
import json
import asyncio
from typing import Dict, Any, List, Tuple

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole
from llm.base import BaseLLMProvider


class ActionNode(BaseNode):
    """行动节点 - 执行工具调用并收集结果"""
    
    def __init__(self, name: str, llm: BaseLLMProvider, tool_manager=None, **kwargs):
        """
        初始化行动节点
        
        Args:
            name: 节点名称
            llm: LLM提供者
            tool_manager: 工具管理器
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.ACT, "工具执行节点", **kwargs)
        self.llm = llm
        self.tool_manager = tool_manager
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行工具调用"""
        context = input_data.context
        
        # 获取对话历史和可用工具
        messages = context.messages.copy()
        available_tools = context.available_tools or []
        
        if not self.tool_manager or not available_tools:
            return NodeOutput(
                data={
                    "error": "没有可用的工具管理器或工具",
                    "tool_results": [],
                    "actions_executed": 0
                },
                next_node="observation",
                should_continue=True,
                metadata={"error": "No tools available"}
            )
        
        # 构建工具选择提示词
        system_prompt = self._build_action_prompt(available_tools, context)
        
        # 添加系统提示
        if not any(msg.role == MessageRole.SYSTEM for msg in messages):
            messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ))
        
        try:
            # 生成工具调用计划
            response = await self.llm.generate(messages)
            
            # 提取响应内容（Message对象 -> 字符串）
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析工具调用
            planned_actions = self._parse_action_response(response_text, available_tools)
            
            if not planned_actions:
                return NodeOutput(
                    data={
                        "error": "未能解析出有效的工具调用",
                        "tool_results": [],
                        "actions_executed": 0,
                        "raw_response": response
                    },
                    next_node="observation",
                    should_continue=True,
                    metadata={"error": "No valid actions parsed"}
                )
            
            # 并行执行工具调用
            tool_results = await self._execute_tools_parallel(planned_actions)
            
            # 创建行动消息
            action_content = self._format_action_summary(planned_actions, tool_results)
            action_message = Message(
                role=MessageRole.ASSISTANT,
                content=action_content,
                metadata={
                    "node_type": "action",
                    "actions_executed": len(planned_actions),
                    "tool_results": tool_results
                }
            )
            
            # 添加到上下文
            context.messages.append(action_message)
            
            return NodeOutput(
                data={
                    "planned_actions": planned_actions,
                    "tool_results": tool_results,
                    "actions_executed": len(planned_actions),
                    "action_summary": action_content,
                    "messages": [action_message]
                },
                next_node="observation",
                should_continue=True,
                metadata={
                    "node_type": "action",
                    "tools_used": [action["tool_name"] for action in planned_actions]
                }
            )
            
        except Exception as e:
            error_msg = str(e)
            print(f"[ActionNode] 执行失败: {error_msg}")
            
            # 如果是LLM API调用失败，应该跳过工具执行环节
            if "InvalidEndpointOrModel" in error_msg or "NotFound" in error_msg:
                return NodeOutput(
                    data={
                        "error": f"行动节点执行失败: {error_msg}",
                        "tool_results": [],
                        "actions_executed": 0,
                        "action_summary": "由于LLM服务不可用，无法制定工具执行计划"
                    },
                    next_node="final_answer",  # 直接跳到最终答案
                    should_continue=True,
                    metadata={"error": error_msg, "error_type": "llm_api_error"}
                )
            else:
                return NodeOutput(
                    data={
                        "error": f"行动节点执行失败: {error_msg}",
                        "tool_results": [],
                        "actions_executed": 0,
                        "action_summary": "工具执行计划制定失败"
                    },
                    next_node="observation",
                    should_continue=True,
                    metadata={"error": error_msg, "error_type": "general_error"}
                )
    
    def _build_action_prompt(self, available_tools: List[str], context) -> str:
        """构建工具选择提示词"""
        # 获取工具描述
        tools_desc = ""
        if self.tool_manager:
            tools_desc = self.tool_manager.get_tools_description()
        
        prompt = f"""你是一个专业的AI助手，需要根据前面的思考分析选择合适的工具来解决问题。

可用工具：
{tools_desc}

请根据前面的分析，选择需要执行的工具。你可以：
1. 选择单个工具
2. 选择多个工具并行执行
3. 为每个工具提供具体的参数

回复格式（JSON格式）：
```json
{{
    "actions": [
        {{
            "tool_name": "工具名称",
            "parameters": {{
                "参数名": "参数值"
            }},
            "reason": "使用此工具的原因"
        }}
    ]
}}
```

注意：
- 工具名必须是可用工具列表中的一个：{', '.join(available_tools)}
- 参数要根据工具的要求提供
- 可以同时指定多个工具进行并行执行
- 如果不需要工具，返回空的actions数组

请基于前面的思考分析，制定具体的工具执行计划。"""
        
        return prompt
    
    def _parse_action_response(self, response: str, available_tools: List[str]) -> List[Dict[str, Any]]:
        """解析工具调用响应"""
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response.strip()
            
            data = json.loads(json_str)
            actions = data.get("actions", [])
            
            # 验证工具名称
            valid_actions = []
            for action in actions:
                tool_name = action.get("tool_name", "")
                if tool_name in available_tools:
                    valid_actions.append({
                        "tool_name": tool_name,
                        "parameters": action.get("parameters", {}),
                        "reason": action.get("reason", "")
                    })
                else:
                    print(f"忽略无效工具: {tool_name}")
            
            return valid_actions
            
        except Exception as e:
            print(f"解析工具调用失败: {e}")
            # 备用解析：尝试从文本中提取工具名称
            backup_actions = []
            for tool in available_tools:
                if tool in response:
                    backup_actions.append({
                        "tool_name": tool,
                        "parameters": {},
                        "reason": f"从文本中检测到工具: {tool}"
                    })
            return backup_actions
    
    async def _execute_tools_parallel(self, planned_actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """并行执行多个工具调用"""
        if not planned_actions:
            return []
        
        # 创建异步任务
        tasks = []
        for i, action in enumerate(planned_actions):
            task = self._execute_single_tool(action, i)
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        tool_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                tool_results.append({
                    "action_index": i,
                    "tool_name": planned_actions[i]["tool_name"],
                    "success": False,
                    "result": f"执行失败: {str(result)}",
                    "error": str(result),
                    "execution_time": 0
                })
            else:
                tool_results.append(result)
        
        return tool_results
    
    async def _execute_single_tool(self, action: Dict[str, Any], action_index: int) -> Dict[str, Any]:
        """执行单个工具"""
        import time
        start_time = time.time()
        
        tool_name = action["tool_name"]
        parameters = action["parameters"]
        
        try:
            # 调用工具
            result = await self.tool_manager.execute_tool(tool_name, parameters)
            execution_time = time.time() - start_time
            
            return {
                "action_index": action_index,
                "tool_name": tool_name,
                "parameters": parameters,
                "success": True,
                "result": result,
                "execution_time": execution_time,
                "reason": action.get("reason", "")
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "action_index": action_index,
                "tool_name": tool_name,
                "parameters": parameters,
                "success": False,
                "result": f"工具执行失败: {str(e)}",
                "error": str(e),
                "execution_time": execution_time,
                "reason": action.get("reason", "")
            }
    
    def _format_action_summary(self, planned_actions: List[Dict[str, Any]], tool_results: List[Dict[str, Any]]) -> str:
        """格式化行动摘要"""
        if not planned_actions:
            return "行动：未执行任何工具"
        
        summary_parts = [f"行动：执行了 {len(planned_actions)} 个工具"]
        
        for i, action in enumerate(planned_actions):
            tool_name = action["tool_name"]
            reason = action.get("reason", "")
            
            # 找到对应的结果
            result_info = next((r for r in tool_results if r["action_index"] == i), None)
            if result_info:
                status = "✅ 成功" if result_info["success"] else "❌ 失败"
                summary_parts.append(f"{i+1}. {tool_name} - {status}")
                if reason:
                    summary_parts.append(f"   原因：{reason}")
            else:
                summary_parts.append(f"{i+1}. {tool_name} - ⏳ 执行中")
        
        return "\n".join(summary_parts) 