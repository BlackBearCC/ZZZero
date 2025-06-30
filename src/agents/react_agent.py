"""
ReAct Agent - 基于Reasoning and Acting范式的智能代理
"""
import uuid
from typing import Dict, Any, Optional, List, AsyncIterator, Union
from datetime import datetime

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.base import BaseAgent, BaseNode, Command
from core.types import AgentType, TaskResult, Message, MessageRole, NodeType
from core.graph import StateGraph, GraphBuilder, StateGraphExecutor
from core.memory import MemoryManager, SQLiteMemoryStore
  
from llm.base import BaseLLMProvider
from tools.base import ToolManager

# 添加MCPToolManager的导入（避免循环导入）
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tools.mcp_tools import MCPToolManager

import json
import asyncio
import time


class ReactAgent(BaseAgent):
    """ReAct智能代理 - 循环进行推理和行动"""
    
    # ==================== 内置节点类 ====================
    
    class ThoughtNode(BaseNode):
        """思考节点 - 分析问题并制定下一步行动计划"""
        
        def __init__(self, name: str, llm: BaseLLMProvider, use_think_mode: bool = True, **kwargs):
            super().__init__(name, NodeType.THINK, "思考分析节点", llm=llm, **kwargs)
            self.use_think_mode = use_think_mode
            
        async def execute(self, state: Dict[str, Any]) -> Union[Dict[str, Any], Command]:
            """执行思考分析"""
            messages = self.get_messages(state)
            available_tools = state.get("available_tools", [])
            memory_context = state.get("memory_context", "")
            
            thought_count = state.get("thought_count", 0) + 1
            
            print(f"[ThoughtNode] 开始思考，迭代: {thought_count}")
            print(f"[ThoughtNode] 消息数量: {len(messages)}")
            print(f"[ThoughtNode] 可用工具: {available_tools}")
            print(f"[ThoughtNode] 使用Think模式: {self.use_think_mode}")
            
            # 使用集成的build_prompt方法
            system_prompt = self.build_prompt("thought", 
                                             query=messages[-1].content if messages else "",
                                             tools=", ".join(available_tools) if available_tools else "无",
                                             context=memory_context)
            
            print(f"[ThoughtNode] 系统提示词长度: {len(system_prompt)}")
            
            try:
                reasoning_content = ""
                
                # 根据配置选择调用方式
                mode = "think" if self.use_think_mode else "normal"
                print(f"[ThoughtNode] 使用模式: {mode}")
                
                response = await self.generate(messages, system_prompt=system_prompt, mode=mode)
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                # 检查是否有推理过程
                reasoning_content = ""
                if hasattr(response, 'metadata') and response.metadata.get("reasoning_content"):
                    reasoning_content = response.metadata["reasoning_content"]
                    print(f"[ThoughtNode] 推理过程长度: {len(reasoning_content)}")
                    print(f"[ThoughtNode] 推理过程预览: {reasoning_content[:200]}...")
                
                print(f"[ThoughtNode] 响应长度: {len(response_text)}")
                print(f"[ThoughtNode] 有推理过程: {bool(reasoning_content)}")
                
                print(f"[ThoughtNode] LLM响应预览: {response_text[:300]}...")
                
                # 使用集成的parse方法
                thought_analysis = self.parse(response_text, format_type="structured")
                
                # 处理解析结果
                analysis_text = thought_analysis.get("分析", thought_analysis.get("analysis", response_text))
                strategy_text = thought_analysis.get("策略", thought_analysis.get("strategy", ""))
                tools_text = thought_analysis.get("工具需求", thought_analysis.get("tools", ""))
                confidence_text = thought_analysis.get("信心评估", thought_analysis.get("confidence", "5"))
                
                # 判断是否需要工具
                needs_tools = ("需要" in tools_text or "使用" in tools_text) and available_tools
                
                # 提取信心分数
                try:
                    confidence = int(''.join(filter(str.isdigit, str(confidence_text))))
                    confidence = max(1, min(10, confidence))
                except (ValueError, TypeError):
                    confidence = 5
                
                print(f"[ThoughtNode] 分析结果 - 需要工具: {needs_tools}, 置信度: {confidence}")
                
                # 创建思考消息
                thought_content = f"💭 思考 {thought_count}:\n\n"
                
                # 如果有推理过程，先显示推理过程
                if reasoning_content:
                    thought_content += f"**🧠 推理过程：**\n{reasoning_content}\n\n"
                
                thought_content += f"**分析**: {analysis_text}"
                if strategy_text:
                    thought_content += f"\n\n**策略**: {strategy_text}"
                if tools_text:
                    thought_content += f"\n\n**工具需求**: {tools_text}"
                thought_content += f"\n\n**信心评估**: {confidence}/10"
                
                thought_message = self.create_ai_message(thought_content)
                thought_message.metadata = {
                    "node_type": "thought",
                    "thought_count": thought_count,
                    "needs_tools": needs_tools,
                    "confidence": confidence,
                    "has_reasoning": bool(reasoning_content),
                    "reasoning_length": len(reasoning_content) if reasoning_content else 0
                }
                
                # 创建状态更新
                state_update = {
                    "messages": [thought_message],
                    "thought_count": thought_count,
                    "last_thought": analysis_text,
                    "reasoning_content": reasoning_content,
                    "needs_tools": needs_tools,
                    "confidence": confidence
                }
                
                # 决定下一步行动
                next_node = "action" if needs_tools else "final_answer"
                print(f"[ThoughtNode] 决定跳转到: {next_node}")
                
                return Command(update=state_update, goto=next_node)
                    
            except Exception as e:
                error_msg = str(e)
                print(f"[ThoughtNode] LLM调用失败: {error_msg}")
                import traceback
                print(f"[ThoughtNode] 详细错误信息:\n{traceback.format_exc()}")
                
                error_message = self.create_ai_message(
                    f"思考过程中遇到问题: {error_msg}，我将基于现有信息尽力回答。"
                )
                
                return Command(
                    update={"messages": [error_message], "has_error": True},
                    goto="final_answer"
                )
    
    class ActionNode(BaseNode):
        """行动节点 - 执行工具调用并收集结果"""
        
        def __init__(self, name: str, llm: BaseLLMProvider, tool_manager=None, **kwargs):
            super().__init__(name, NodeType.ACT, "工具执行节点", llm=llm, **kwargs)
            self.tool_manager = tool_manager
            
        async def execute(self, state: Dict[str, Any]) -> Union[Dict[str, Any], Command]:
            """执行工具调用"""
            messages = self.get_messages(state)
            available_tools = state.get("available_tools", [])
            
            if not self.tool_manager or not available_tools:
                error_message = self.create_ai_message("没有可用的工具管理器或工具")
                return Command(
                    update={"messages": [error_message], "error": "No tools available"},
                    goto="final_answer"
                )
            
            # 构建工具选择提示词
            tools_desc = self.tool_manager.get_tools_description() if self.tool_manager else ""
            system_prompt = f"""你是一个专业的AI助手，需要根据前面的思考分析选择合适的工具来解决问题。

可用工具：
{tools_desc}

请根据前面的分析，选择需要执行的工具。回复格式（JSON格式）：
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

注意：工具名必须是可用工具列表中的一个：{', '.join(available_tools)}"""
            
            try:
                # 生成工具调用计划
                response = await self.generate(messages, system_prompt=system_prompt)
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                # 解析工具调用
                planned_actions = self._parse_action_response(response_text, available_tools)
                
                if not planned_actions:
                    error_message = self.create_ai_message("未能解析出有效的工具调用")
                    return Command(
                        update={"messages": [error_message], "error": "No valid actions parsed"},
                        goto="observation"
                    )
                
                # 并行执行工具调用
                tool_results = await self._execute_tools_parallel(planned_actions)
                
                # 创建行动消息
                action_content = self._format_action_summary(planned_actions, tool_results)
                action_message = self.create_ai_message(action_content)
                action_message.metadata = {
                    "node_type": "action",
                    "actions_executed": len(planned_actions),
                    "tool_results": tool_results
                }
                
                return Command(
                    update={
                        "messages": [action_message],
                        "planned_actions": planned_actions,
                        "tool_results": tool_results,
                        "actions_executed": len(planned_actions)
                    },
                    goto="observation"
                )
                
            except Exception as e:
                error_msg = str(e)
                print(f"[ActionNode] 执行失败: {error_msg}")
                
                error_message = self.create_ai_message(f"行动节点执行失败: {error_msg}")
                return Command(
                    update={"messages": [error_message], "error": error_msg},
                    goto="final_answer" if "InvalidEndpointOrModel" in error_msg else "observation"
                )
        
        def _parse_action_response(self, response: str, available_tools: List[str]) -> List[Dict[str, Any]]:
            """解析工具调用响应"""
            try:
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response.strip()
                
                data = json.loads(json_str)
                actions = data.get("actions", [])
                
                valid_actions = []
                for action in actions:
                    tool_name = action.get("tool_name", "")
                    if tool_name in available_tools:
                        valid_actions.append({
                            "tool_name": tool_name,
                            "parameters": action.get("parameters", {}),
                            "reason": action.get("reason", "")
                        })
                
                return valid_actions
                
            except Exception as e:
                print(f"解析工具调用失败: {e}")
                return []
        
        async def _execute_tools_parallel(self, planned_actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """并行执行多个工具调用"""
            if not planned_actions:
                return []
            
            tasks = []
            for i, action in enumerate(planned_actions):
                task = self._execute_single_tool(action, i)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
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
            start_time = time.time()
            
            tool_name = action["tool_name"]
            parameters = action["parameters"]
            
            try:
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
                
                result_info = next((r for r in tool_results if r["action_index"] == i), None)
                if result_info:
                    status = "✅ 成功" if result_info["success"] else "❌ 失败"
                    summary_parts.append(f"{i+1}. {tool_name} - {status}")
                    if reason:
                        summary_parts.append(f"   原因：{reason}")
                else:
                    summary_parts.append(f"{i+1}. {tool_name} - ⏳ 执行中")
            
            return "\n".join(summary_parts)
    
    class ObservationNode(BaseNode):
        """观察节点 - 分析工具执行结果并决定下一步行动"""
        
        def __init__(self, name: str, llm: BaseLLMProvider, max_iterations: int = 5, **kwargs):
            super().__init__(name, NodeType.OBSERVE, "结果观察分析节点", llm=llm, **kwargs)
            self.max_iterations = max_iterations
            
        async def execute(self, state: Dict[str, Any]) -> Union[Dict[str, Any], Command]:
            """执行观察分析"""
            messages = self.get_messages(state)
            tool_results = state.get("tool_results", [])
            
            # 构建观察分析提示词
            system_prompt = """你是一个专业的AI助手，需要分析工具执行的结果并决定下一步行动。

请仔细分析刚才执行的工具结果，评估：
1. **结果质量**：工具执行是否成功，返回的数据是否有用
2. **问题解决程度**：当前结果是否足以回答用户的问题
3. **信息完整性**：是否还需要获取更多信息
4. **下一步建议**：应该继续思考、执行更多工具，还是给出最终答案

请按以下格式回复：

结果质量评分：[1-10分，评估工具执行结果的质量]
问题解决状态：[已解决/部分解决/未解决]
信息完整性：[完整/基本完整/不完整]
继续推理：[是/否，是否需要继续思考和行动]
建议行动：[继续思考/直接回答/需要更多工具]
分析总结：[对当前结果的详细分析]"""
            
            iteration_count = state.get("iteration_count", 0)
            thought_count = state.get("thought_count", 0)
            
            try:
                response = await self.generate(messages, system_prompt=system_prompt)
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                # 解析观察结果
                observation_analysis = self._parse_observation_response(response_text, tool_results)
                
                # 创建观察消息
                observation_content = self._format_observation_content(tool_results, observation_analysis, thought_count)
                observation_message = self.create_ai_message(observation_content)
                observation_message.metadata = {
                    "node_type": "observation",
                    "iteration_count": iteration_count,
                    "tool_results_count": len(tool_results),
                    "analysis": observation_analysis
                }
                
                # 决定下一步行动
                next_node = self._decide_next_action(observation_analysis, iteration_count, thought_count)
                
                # 更新迭代计数
                new_iteration_count = iteration_count + 1 if next_node == "thought" else iteration_count
                
                return Command(
                    update={
                        "messages": [observation_message],
                        "observation": observation_analysis["summary"],
                        "quality_score": observation_analysis["quality_score"],
                        "problem_solved": observation_analysis["problem_solved"],
                        "continue_reasoning": observation_analysis["continue_reasoning"],
                        "iteration_count": new_iteration_count
                    },
                    goto=next_node
                )
                
            except Exception as e:
                error_message = self.create_ai_message("分析过程中遇到错误，将基于现有信息给出回答")
                return Command(
                    update={"messages": [error_message], "error": str(e)},
                    goto="final_answer"
                )
        
        def _parse_observation_response(self, response: str, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
            """解析观察分析响应"""
            analysis = {
                "quality_score": 5,
                "problem_solved": False,
                "needs_more_info": True,
                "continue_reasoning": True,
                "summary": response,
                "tool_analysis": self._analyze_tool_results(tool_results)
            }
            
            try:
                lines = response.split('\n')
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('结果质量评分：'):
                        try:
                            import re
                            score_match = re.search(r'(\d+)', line)
                            if score_match:
                                analysis['quality_score'] = int(score_match.group(1))
                        except:
                            pass
                            
                    elif line.startswith('问题解决状态：'):
                        status = line[7:].strip()
                        if '已解决' in status:
                            analysis['problem_solved'] = True
                            analysis['needs_more_info'] = False
                        elif '部分解决' in status:
                            analysis['problem_solved'] = False
                            analysis['needs_more_info'] = True
                        else:
                            analysis['problem_solved'] = False
                            analysis['needs_more_info'] = True
                            
                    elif line.startswith('继续推理：'):
                        continue_text = line[5:].strip()
                        analysis['continue_reasoning'] = '是' in continue_text
                        
                    elif line.startswith('分析总结：'):
                        analysis['summary'] = line[5:].strip()
                
                # 综合判断
                if analysis['quality_score'] >= 8 and analysis['problem_solved']:
                    analysis['continue_reasoning'] = False
                elif analysis['quality_score'] <= 3:
                    analysis['continue_reasoning'] = True
                    analysis['needs_more_info'] = True
                    
            except Exception as e:
                print(f"解析观察响应失败: {e}")
            
            return analysis
        
        def _analyze_tool_results(self, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
            """分析工具执行结果"""
            if not tool_results:
                return {
                    "total_tools": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "success_rate": 0.0,
                    "has_useful_data": False,
                    "error_summary": "没有工具执行结果"
                }
            
            success_count = sum(1 for result in tool_results if result.get("success", False))
            failed_count = len(tool_results) - success_count
            success_rate = success_count / len(tool_results) if tool_results else 0
            
            has_useful_data = False
            for result in tool_results:
                if result.get("success", False):
                    result_content = str(result.get("result", ""))
                    if len(result_content) > 10 and "失败" not in result_content:
                        has_useful_data = True
                        break
            
            errors = [result.get("error", "") for result in tool_results if not result.get("success", False)]
            error_summary = "; ".join(filter(None, errors)) if errors else ""
            
            return {
                "total_tools": len(tool_results),
                "success_count": success_count,
                "failed_count": failed_count,
                "success_rate": success_rate,
                "has_useful_data": has_useful_data,
                "error_summary": error_summary
            }
        
        def _format_observation_content(self, tool_results: List[Dict[str, Any]], 
                                      analysis: Dict[str, Any], thought_count: int) -> str:
            """格式化观察内容"""
            content_parts = [f"观察 {thought_count}："]
            
            if tool_results:
                tool_analysis = analysis["tool_analysis"]
                content_parts.append(
                    f"工具执行结果：{tool_analysis['success_count']}/{tool_analysis['total_tools']} 成功 "
                    f"(成功率: {tool_analysis['success_rate']:.1%})"
                )
                
                for i, result in enumerate(tool_results):
                    tool_name = result.get("tool_name", f"工具{i+1}")
                    status = "✅" if result.get("success", False) else "❌"
                    content_parts.append(f"  {status} {tool_name}")
                    
                    if result.get("success", False):
                        result_str = str(result.get("result", ""))
                        if len(result_str) > 200:
                            result_str = result_str[:200] + "..."
                        content_parts.append(f"     结果：{result_str}")
                    else:
                        error = result.get("error", "未知错误")
                        content_parts.append(f"     错误：{error}")
            
            content_parts.append(f"\n分析：{analysis['summary']}")
            content_parts.append(f"质量评分：{analysis['quality_score']}/10")
            
            return "\n".join(content_parts)
        
        def _decide_next_action(self, analysis: Dict[str, Any], iteration_count: int, thought_count: int) -> str:
            """决定下一步行动"""
            if iteration_count >= self.max_iterations:
                return "final_answer"
            
            if analysis["problem_solved"] and analysis["quality_score"] >= 7:
                return "final_answer"
            
            if analysis["quality_score"] <= 4 and analysis["needs_more_info"]:
                if thought_count >= 8:
                    return "final_answer"
                return "thought"
            
            if analysis["continue_reasoning"] and thought_count < 6:
                return "thought"
            else:
                return "final_answer"
    
    class FinalAnswerNode(BaseNode):
        """最终答案节点 - 整合所有推理过程并生成最终回答"""
        
        def __init__(self, name: str, llm: BaseLLMProvider, **kwargs):
            super().__init__(name, NodeType.FINALIZE, "最终答案生成节点", llm=llm, **kwargs)
            
        async def execute(self, state: Dict[str, Any]) -> Union[Dict[str, Any], Command]:
            """生成最终答案"""
            messages = self.get_messages(state)
            
            # 使用集成的build_prompt方法
            system_prompt = self.build_prompt("final_answer",
                                             query=messages[0].content if messages else "",
                                             thought="基于前面的完整推理过程",
                                             observations="已完成所有必要的分析和工具调用")
            
            thought_count = state.get("thought_count", 0)
            iteration_count = state.get("iteration_count", 0)
            
            try:
                response = await self.generate(messages, system_prompt=system_prompt)
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                # 清理和格式化响应
                final_answer = self._format_final_answer(response_text)
                
                final_message = self.create_ai_message(final_answer)
                final_message.metadata = {
                    "node_type": "final_answer",
                    "thought_count": thought_count,
                    "iteration_count": iteration_count,
                    "is_final_answer": True
                }
                
                return {
                    "messages": [final_message],
                    "final_answer": final_answer,
                    "thought_count": thought_count,
                    "iteration_count": iteration_count,
                    "is_complete": True
                }
                
            except Exception as e:
                fallback_answer = self._generate_fallback_answer(messages, str(e))
                
                fallback_message = self.create_ai_message(fallback_answer)
                fallback_message.metadata = {
                    "node_type": "final_answer",
                    "is_fallback": True,
                    "error": str(e)
                }
                
                return {
                    "messages": [fallback_message],
                    "final_answer": fallback_answer,
                    "error": f"最终答案生成失败: {str(e)}",
                    "is_fallback": True,
                    "is_complete": True
                }
        
        def _format_final_answer(self, response: str) -> str:
            """格式化最终答案"""
            cleaned_response = response.strip()
            
            prefixes_to_remove = [
                "最终答案：", "Final Answer:", "答案：", "回答：", "结论：", "总结："
            ]
            
            for prefix in prefixes_to_remove:
                if cleaned_response.startswith(prefix):
                    cleaned_response = cleaned_response[len(prefix):].strip()
            
            if not cleaned_response:
                cleaned_response = "抱歉，无法基于当前信息生成完整的回答。"
            
            return cleaned_response
        
        def _generate_fallback_answer(self, messages: List[Message], error_msg: str) -> str:
            """生成备用回答"""
            user_query = ""
            for message in messages:
                if message.role == MessageRole.USER:
                    user_query = message.content
                    break
            
            fallback_parts = []
            if user_query:
                fallback_parts.append(f"针对您的问题：{user_query}")
            
            fallback_parts.append(f"由于技术原因（{error_msg}），无法生成完整的分析结果。")
            fallback_parts.append("请您重新描述问题，我将重新为您分析。")
            
            return "\n".join(fallback_parts)
    
    # ==================== ReactAgent 主体 ====================
    
    def __init__(self,
                 llm: BaseLLMProvider,
                 tool_manager: Optional[Union[ToolManager, 'MCPToolManager']] = None,
                 max_iterations: int = 5,
                 name: Optional[str] = None,
                 memory_enabled: bool = True,
                 memory_store: Optional[SQLiteMemoryStore] = None,
                 short_term_limit: int = 30000,
                 session_id: Optional[str] = None,
                 use_think_mode: bool = True,
                 **kwargs):
        """
        初始化ReAct Agent
        
        Args:
            llm: LLM提供者
            tool_manager: 工具管理器（可选，支持ToolManager或MCPToolManager）
            max_iterations: 最大迭代次数
            name: Agent名称
            memory_enabled: 是否启用记忆功能
            memory_store: 记忆存储实例（可选）
            short_term_limit: 短期记忆字符限制
            session_id: 会话ID（用于记忆隔离）
            **kwargs: 其他配置
        """
        super().__init__(
            agent_type=AgentType.REACT,
            name=name or "react_agent",
            description="基于ReAct范式的智能代理（支持记忆）",
            **kwargs
        )
        self.llm = llm
        self.tool_manager = tool_manager
        self.max_iterations = max_iterations
        self.use_think_mode = use_think_mode
        self.executor = StateGraphExecutor(max_iterations=max_iterations)
        
        # 记忆管理
        self.memory_enabled = memory_enabled
        self.memory_manager = None
        if memory_enabled:
            self.memory_manager = MemoryManager(
                llm=llm,
                store=memory_store or SQLiteMemoryStore("./workspace/memory.db"),
                short_term_limit=short_term_limit,
                session_id=session_id
            )
        
    def build_graph(self, use_stream: bool = False) -> StateGraph:
        """构建ReAct执行图
        
        Args:
            use_stream: 是否使用流式节点
        """
        builder = GraphBuilder("react_graph")
        
        # 判断是否有工具可用
        if self.tool_manager and self.tool_manager.list_tools():
            if use_stream:
                # 使用流式节点（保持向后兼容）
                from nodes.stream_react_agent_node import StreamReactAgentNode
                agent_node = StreamReactAgentNode("agent", self.llm, self.tool_manager)
                
                # 流式节点不需要工具节点，内部处理工具调用
                graph = (builder
                    .add_node(agent_node)
                    .entry("agent")
                    .build()
                )
            else:
                # 使用内置的分离式ReAct节点架构
                thought_node = self.ThoughtNode("thought", self.llm, use_think_mode=self.use_think_mode)
                action_node = self.ActionNode("action", self.llm, self.tool_manager)
                observation_node = self.ObservationNode("observation", self.llm, self.max_iterations)
                final_answer_node = self.FinalAnswerNode("final_answer", self.llm)
                
                # 构建分离式ReAct图
                graph = (builder
                    .add_node(thought_node)
                    .add_node(action_node)
                    .add_node(observation_node)
                    .add_node(final_answer_node)
                    .entry("thought")
                    .build()
                )
        else:
            # 没有工具时的简单对话模式
            from nodes.simple_chat_node import SimpleChatNode
            chat_node = SimpleChatNode("chat", self.llm)
            
            graph = (builder
                .add_node(chat_node)
                .entry("chat")
                .build()
            )
        
        return graph
    
    def _should_continue(self, state: Dict[str, Any]) -> str:
        """决定是否继续使用工具"""
        messages = state.get("messages", [])
        if not messages:
            return "end"
            
        last_message = messages[-1]
        # 检查是否有工具调用
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"
        return "end"
        
    async def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> TaskResult:
        """运行ReAct Agent（基于StateGraph）"""
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建任务结果
        result = TaskResult(
            task_id=task_id,
            query=query,
            agent_type=self.agent_type
        )
        
        # 初始化
        await self.initialize()
        
        # 获取可用工具列表
        available_tools = []
        if self.tool_manager:
            available_tools = self.tool_manager.list_tools()
        
        # 构建记忆上下文
        memory_context = ""
        if self.memory_enabled and self.memory_manager:
            try:
                memory_context = await self.memory_manager.get_context_for_query(query, max_entries=5)
            except Exception as e:
                print(f"获取记忆上下文失败: {e}")
        
        # 处理对话历史
        messages = []
        if context and context.get("conversation_history") and context.get("preserve_history"):
            messages = context["conversation_history"].copy()
            print(f"[ReactAgent.run] 使用完整对话历史，消息数: {len(messages)}")
        else:
            messages = [Message(role=MessageRole.USER, content=query)]
            print(f"[ReactAgent.run] 仅使用当前消息")
        
        # 创建初始状态
        initial_state = {
            "task_id": task_id,
            "agent_type": self.agent_type.value,
            "available_tools": available_tools,
            "messages": messages,
            "memory_context": memory_context,
            "memory_manager": self.memory_manager,
            **(context or {})
        }
        
        print(f"[ReactAgent.run] 初始状态消息数: {len(initial_state['messages'])}")
        
        # 构建并执行StateGraph
        graph = self.build_graph(use_stream=False)
        final_state = await self.executor.execute(graph, initial_state, {})
        
        # 从最终状态提取结果
        if final_state:
            # 优先从final_answer字段获取
            if "final_answer" in final_state:
                result.result = final_state["final_answer"]
                result.success = True
            # 从消息中提取最终回答
            elif "messages" in final_state and final_state["messages"]:
                last_message = final_state["messages"][-1]
                if hasattr(last_message, 'content'):
                    result.result = last_message.content
                    result.success = True
                else:
                    result.result = str(last_message)
                    result.success = True
            # 从其他响应字段获取
            elif "agent_response" in final_state:
                result.result = final_state["agent_response"]
                result.success = True
            elif "chat_response" in final_state:
                result.result = final_state["chat_response"]
                result.success = True
            else:
                result.result = "抱歉，无法生成回复"
        
        # 保存记忆
        if self.memory_enabled and self.memory_manager and result.success:
            try:
                has_history = context and context.get("conversation_history") and len(context["conversation_history"]) > 1
                if not has_history:
                    await self.memory_manager.add_conversation(query, result.result)
                    print(f"对话已保存到记忆，会话ID: {self.memory_manager.session_id}")
            except Exception as e:
                print(f"保存对话记忆失败: {e}")
        
        # 构建简化的执行轨迹
        result.execution_trace = [
            {
                "graph_name": graph.name,
                "final_state_keys": list(final_state.keys()) if final_state else [],
                "success": result.success
            }
        ]
        
        # 计算指标
        result.metrics = {
            "state_keys": list(final_state.keys()) if final_state else [],
            "has_memory": self.memory_enabled
        }
        
        # 添加记忆统计信息
        if self.memory_enabled and self.memory_manager:
            try:
                memory_stats = await self.memory_manager.get_stats()
                result.metrics.update({
                    "memory_stats": memory_stats
                })
            except Exception as e:
                print(f"获取记忆统计失败: {e}")

        return result
    
    async def stream_run(self, query: str, context: Optional[Dict[str, Any]] = None) -> AsyncIterator[Dict[str, Any]]:
        """流式运行ReAct Agent - 简化版本"""
        # 暂时回退到标准执行
        result = await self.run(query, context)
        yield {
            "type": "final_result",
            "content": result.result,
            "task_id": result.task_id,
            "metadata": {"success": result.success}
        }
        
    # _build_system_prompt 方法已移到基类 BaseAgent 中
        
    async def initialize(self):
        """初始化Agent"""
        await self.llm.initialize()
        if self.tool_manager:
            await self.tool_manager.initialize()
        
    async def cleanup(self):
        """清理资源"""
        await self.llm.cleanup()
        if self.tool_manager:
            await self.tool_manager.cleanup() 
    
    async def get_memory_stats(self) -> Optional[Dict[str, Any]]:
        """获取记忆统计信息"""
        if self.memory_enabled and self.memory_manager:
            return await self.memory_manager.get_stats()
        return None
    
    async def clear_memory(self):
        """清空当前会话记忆"""
        if self.memory_enabled and self.memory_manager:
            await self.memory_manager.clear_all()
            print(f"已清空会话记忆: {self.memory_manager.session_id}")
    
    async def export_memory(self) -> Optional[Dict[str, Any]]:
        """导出记忆数据"""
        if self.memory_enabled and self.memory_manager:
            return await self.memory_manager.export_data()
        return None