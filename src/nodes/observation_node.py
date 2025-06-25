"""
观察节点 - 负责分析工具执行结果并决定下一步行动
"""
import sys
import os
import json
from typing import Dict, Any, List

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole
from llm.base import BaseLLMProvider


class ObservationNode(BaseNode):
    """观察节点 - 分析工具执行结果并决定是否继续推理循环"""
    
    def __init__(self, name: str, llm: BaseLLMProvider, max_iterations: int = 5, **kwargs):
        """
        初始化观察节点
        
        Args:
            name: 节点名称
            llm: LLM提供者
            max_iterations: 最大迭代次数
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.OBSERVE, "结果观察分析节点", **kwargs)
        self.llm = llm
        self.max_iterations = max_iterations
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行观察分析"""
        context = input_data.context
        
        # 获取工具执行结果（兼容NodeOutput对象和字典）
        tool_results = []
        actions_executed = 0
        
        if input_data.previous_output:
            if hasattr(input_data.previous_output, 'data'):
                # NodeOutput对象
                tool_results = input_data.previous_output.data.get("tool_results", [])
                actions_executed = input_data.previous_output.data.get("actions_executed", 0)
            elif isinstance(input_data.previous_output, dict):
                # 字典对象
                tool_results = input_data.previous_output.get("tool_results", [])
                actions_executed = input_data.previous_output.get("actions_executed", 0)
            else:
                print(f"[ObservationNode] 未知的previous_output类型: {type(input_data.previous_output)}")
        
        # 获取对话历史
        messages = context.messages.copy()
        
        # 构建观察分析提示词
        system_prompt = self._build_observation_prompt(context)
        
        # 添加系统提示
        if not any(msg.role == MessageRole.SYSTEM for msg in messages):
            messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ))
        
        # 获取当前迭代次数
        iteration_count = context.variables.get("iteration_count", 0)
        thought_count = context.variables.get("thought_count", 0)
        
        try:
            # 生成观察分析
            response = await self.llm.generate(messages)
            
            # 提取响应内容（Message对象 -> 字符串）
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析观察结果
            observation_analysis = self._parse_observation_response(response_text, tool_results)
            
            # 创建观察消息
            observation_content = self._format_observation_content(
                tool_results, observation_analysis, thought_count
            )
            
            observation_message = Message(
                role=MessageRole.ASSISTANT,
                content=observation_content,
                metadata={
                    "node_type": "observation",
                    "iteration_count": iteration_count,
                    "tool_results_count": len(tool_results),
                    "analysis": observation_analysis
                }
            )
            
            # 添加到上下文
            context.messages.append(observation_message)
            
            # 决定下一步行动
            next_node = self._decide_next_action(
                observation_analysis, iteration_count, thought_count, context
            )
            
            # 更新迭代计数
            if next_node == "thought":
                context.variables["iteration_count"] = iteration_count + 1
            
            return NodeOutput(
                data={
                    "observation": observation_analysis["summary"],
                    "quality_score": observation_analysis["quality_score"],
                    "problem_solved": observation_analysis["problem_solved"],
                    "needs_more_info": observation_analysis["needs_more_info"],
                    "continue_reasoning": observation_analysis["continue_reasoning"],
                    "next_action": next_node,
                    "iteration_count": iteration_count,
                    "tool_results_analysis": observation_analysis["tool_analysis"],
                    "messages": [observation_message]
                },
                next_node=next_node,
                should_continue=True,
                metadata={
                    "node_type": "observation",
                    "quality_score": observation_analysis["quality_score"],
                    "continue_reasoning": observation_analysis["continue_reasoning"]
                }
            )
            
        except Exception as e:
            # 发生错误时，通常直接给出最终答案
            return NodeOutput(
                data={
                    "error": f"观察节点执行失败: {str(e)}",
                    "observation": "分析过程中遇到错误，将基于现有信息给出回答",
                    "problem_solved": True,
                    "continue_reasoning": False,
                    "next_action": "final_answer"
                },
                next_node="final_answer",
                should_continue=True,
                metadata={"error": str(e)}
            )
    
    def _build_observation_prompt(self, context) -> str:
        """构建观察分析提示词"""
        prompt = """你是一个专业的AI助手，需要分析工具执行的结果并决定下一步行动。

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
分析总结：[对当前结果的详细分析]

请保持分析的客观性和准确性，帮助做出最佳的推理决策。"""
        
        return prompt
    
    def _parse_observation_response(self, response: str, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """解析观察分析响应"""
        # 默认值
        analysis = {
            "quality_score": 5,
            "problem_solved": False,
            "needs_more_info": True,
            "continue_reasoning": True,
            "summary": response,
            "tool_analysis": self._analyze_tool_results(tool_results)
        }
        
        try:
            # 解析结构化响应
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
                        
                elif line.startswith('信息完整性：'):
                    completeness = line[6:].strip()
                    if '完整' in completeness and '不完整' not in completeness:
                        analysis['needs_more_info'] = False
                    else:
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
        
        # 检查是否有有用的数据
        has_useful_data = False
        for result in tool_results:
            if result.get("success", False):
                result_content = str(result.get("result", ""))
                if len(result_content) > 10 and "失败" not in result_content:
                    has_useful_data = True
                    break
        
        # 收集错误信息
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
        
        # 工具执行摘要
        if tool_results:
            tool_analysis = analysis["tool_analysis"]
            content_parts.append(
                f"工具执行结果：{tool_analysis['success_count']}/{tool_analysis['total_tools']} 成功 "
                f"(成功率: {tool_analysis['success_rate']:.1%})"
            )
            
            # 详细结果
            for i, result in enumerate(tool_results):
                tool_name = result.get("tool_name", f"工具{i+1}")
                status = "✅" if result.get("success", False) else "❌"
                content_parts.append(f"  {status} {tool_name}")
                
                # 简化结果显示
                if result.get("success", False):
                    result_str = str(result.get("result", ""))
                    if len(result_str) > 200:
                        result_str = result_str[:200] + "..."
                    content_parts.append(f"     结果：{result_str}")
                else:
                    error = result.get("error", "未知错误")
                    content_parts.append(f"     错误：{error}")
        
        # 分析总结
        content_parts.append(f"\n分析：{analysis['summary']}")
        content_parts.append(f"质量评分：{analysis['quality_score']}/10")
        
        return "\n".join(content_parts)
    
    def _decide_next_action(self, analysis: Dict[str, Any], iteration_count: int, 
                          thought_count: int, context) -> str:
        """决定下一步行动"""
        # 检查是否超过最大迭代次数
        if iteration_count >= self.max_iterations:
            return "final_answer"
        
        # 如果问题已解决且质量较高，给出最终答案
        if analysis["problem_solved"] and analysis["quality_score"] >= 7:
            return "final_answer"
        
        # 如果质量很低且需要更多信息，继续思考
        if analysis["quality_score"] <= 4 and analysis["needs_more_info"]:
            # 但不能无限循环思考
            if thought_count >= 8:
                return "final_answer"
            return "thought"
        
        # 根据continue_reasoning标志决定
        if analysis["continue_reasoning"] and thought_count < 6:
            return "thought"
        else:
            return "final_answer" 