"""
最终答案节点 - 负责整合信息并生成最终回答
"""
import sys
import os
from typing import Dict, Any, List

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole
from llm.base import BaseLLMProvider


class FinalAnswerNode(BaseNode):
    """最终答案节点 - 整合所有推理过程并生成专业的最终回答"""
    
    def __init__(self, name: str, llm: BaseLLMProvider, **kwargs):
        """
        初始化最终答案节点
        
        Args:
            name: 节点名称
            llm: LLM提供者
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.FINALIZE, "最终答案生成节点", **kwargs)
        self.llm = llm
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """生成最终答案"""
        context = input_data.context
        
        # 获取对话历史
        messages = context.messages.copy()
        
        # 构建最终答案生成提示词
        system_prompt = self._build_final_answer_prompt(context)
        
        # 添加系统提示
        if not any(msg.role == MessageRole.SYSTEM for msg in messages):
            messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ))
        
        # 获取统计信息
        thought_count = context.variables.get("thought_count", 0)
        iteration_count = context.variables.get("iteration_count", 0)
        
        try:
            # 生成最终答案
            response = await self.llm.generate(messages)
            
            # 提取响应内容（Message对象 -> 字符串）
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 清理和格式化响应
            final_answer = self._format_final_answer(response_text, thought_count, iteration_count)
            
            # 创建最终答案消息
            final_message = Message(
                role=MessageRole.ASSISTANT,
                content=final_answer,
                metadata={
                    "node_type": "final_answer",
                    "thought_count": thought_count,
                    "iteration_count": iteration_count,
                    "is_final_answer": True
                }
            )
            
            # 添加到上下文
            context.messages.append(final_message)
            
            return NodeOutput(
                data={
                    "final_answer": final_answer,
                    "raw_response": response_text,
                    "thought_count": thought_count,
                    "iteration_count": iteration_count,
                    "messages": [final_message],
                    "is_complete": True
                },
                next_node=None,  # 最终节点，没有下一个节点
                should_continue=False,  # 推理结束
                metadata={
                    "node_type": "final_answer",
                    "is_complete": True,
                    "reasoning_stats": {
                        "thought_count": thought_count,
                        "iteration_count": iteration_count
                    }
                }
            )
            
        except Exception as e:
            # 即使生成失败，也要提供一个基本的回答
            fallback_answer = self._generate_fallback_answer(context, str(e))
            
            fallback_message = Message(
                role=MessageRole.ASSISTANT,
                content=fallback_answer,
                metadata={
                    "node_type": "final_answer",
                    "is_fallback": True,
                    "error": str(e)
                }
            )
            
            context.messages.append(fallback_message)
            
            return NodeOutput(
                data={
                    "final_answer": fallback_answer,
                    "error": f"最终答案生成失败: {str(e)}",
                    "is_fallback": True,
                    "messages": [fallback_message],
                    "is_complete": True
                },
                next_node=None,
                should_continue=False,
                metadata={"error": str(e), "is_fallback": True}
            )
    
    def _build_final_answer_prompt(self, context) -> str:
        """构建最终答案生成提示词"""
        # 获取记忆上下文
        memory_context = ""
        if hasattr(context, 'variables') and context.variables:
            memory_context = context.variables.get("memory_context", "")
        
        prompt = """你是一个专业的AI助手，现在需要基于前面的分析和推理过程，给出最终的专业回答。

请注意：
1. **整合信息**：综合前面所有的思考、行动和观察结果
2. **专业性**：保持回答的专业性和准确性
3. **完整性**：确保回答完整地解决了用户的问题
4. **简洁性**：避免重复前面的推理过程，直接给出结论
5. **实用性**：提供具体可行的建议或答案

"""
        
        # 添加记忆上下文指导
        if memory_context:
            prompt += "参考相关历史信息，确保回答的连贯性和一致性。\n"
        
        prompt += """回答格式要求：
- 直接回答用户的问题
- 如果有具体数据或结果，清晰地展示
- 如果需要操作步骤，提供清晰的指导
- 如果有建议，给出具体可行的方案
- 保持语言专业、准确、易懂

不要包含：
- "根据前面的分析..."这样的引用
- 重复的推理过程
- 不必要的解释性文字

请基于完整的上下文信息，给出专业、准确、完整的最终答案。"""
        
        return prompt
    
    def _format_final_answer(self, response: str, thought_count: int, iteration_count: int) -> str:
        """格式化最终答案"""
        # 清理响应，移除不必要的前缀
        cleaned_response = response.strip()
        
        # 移除常见的不必要前缀
        prefixes_to_remove = [
            "最终答案：",
            "Final Answer:",
            "答案：",
            "回答：",
            "结论：",
            "总结："
        ]
        
        for prefix in prefixes_to_remove:
            if cleaned_response.startswith(prefix):
                cleaned_response = cleaned_response[len(prefix):].strip()
        
        # 确保答案不为空
        if not cleaned_response:
            cleaned_response = "抱歉，无法基于当前信息生成完整的回答。"
        
        return cleaned_response
    
    def _generate_fallback_answer(self, context, error_msg: str) -> str:
        """生成备用回答"""
        # 尝试从对话历史中提取一些有用信息
        user_query = ""
        tool_results_summary = []
        
        for message in context.messages:
            if message.role == MessageRole.USER:
                user_query = message.content
                break
        
        # 提取工具执行结果
        for message in context.messages:
            if hasattr(message, 'metadata') and message.metadata:
                if message.metadata.get('node_type') == 'action':
                    tool_results = message.metadata.get('tool_results', [])
                    for result in tool_results:
                        if result.get('success', False):
                            tool_name = result.get('tool_name', '工具')
                            tool_results_summary.append(f"- {tool_name}: 执行成功")
        
        fallback_parts = []
        
        if user_query:
            fallback_parts.append(f"针对您的问题：{user_query}")
        
        if tool_results_summary:
            fallback_parts.append("执行的操作：")
            fallback_parts.extend(tool_results_summary)
        
        fallback_parts.append(f"由于技术原因（{error_msg}），无法生成完整的分析结果。")
        fallback_parts.append("请您重新描述问题，我将重新为您分析。")
        
        return "\n".join(fallback_parts)
    
    def _extract_reasoning_summary(self, context) -> Dict[str, Any]:
        """提取推理过程摘要"""
        summary = {
            "total_thoughts": 0,
            "total_actions": 0,
            "successful_tools": 0,
            "failed_tools": 0,
            "key_findings": []
        }
        
        for message in context.messages:
            if hasattr(message, 'metadata') and message.metadata:
                node_type = message.metadata.get('node_type')
                
                if node_type == 'thought':
                    summary["total_thoughts"] += 1
                elif node_type == 'action':
                    summary["total_actions"] += 1
                    tool_results = message.metadata.get('tool_results', [])
                    for result in tool_results:
                        if result.get('success', False):
                            summary["successful_tools"] += 1
                        else:
                            summary["failed_tools"] += 1
                elif node_type == 'observation':
                    analysis = message.metadata.get('analysis', {})
                    if analysis.get('summary'):
                        summary["key_findings"].append(analysis['summary'])
        
        return summary 