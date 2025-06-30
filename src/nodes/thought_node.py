"""
思考节点 - 负责分析问题和制定行动计划
"""
import sys
import os
from typing import Dict, Any, List

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from core.base import BaseNode, Command
from core.types import NodeType, Message, MessageRole
from llm.base import BaseLLMProvider
from typing import Union


class ThoughtNode(BaseNode):
    """思考节点 - 分析问题并制定下一步行动计划（StateGraph版本）"""
    
    def __init__(self, name: str, llm: BaseLLMProvider, **kwargs):
        """初始化思考节点"""
        super().__init__(name, NodeType.THINK, "思考分析节点", llm=llm, **kwargs)
        
    async def execute(self, state: Dict[str, Any]) -> Union[Dict[str, Any], Command]:
        """执行思考分析（状态驱动版本）"""
        # 获取状态中的信息
        messages = self.get_messages(state)
        available_tools = state.get("available_tools", [])
        memory_context = state.get("memory_context", "")
        
        # 获取当前思考轮次
        thought_count = state.get("thought_count", 0) + 1
        
        # 构建思考提示词（使用集成的build_prompt方法）
        system_prompt = self.build_prompt("thought", 
                                         query=messages[-1].content if messages else "",
                                         tools=", ".join(available_tools) if available_tools else "无",
                                         context=memory_context)
        
        # 生成思考内容（使用集成的generate方法）
        try:
            response = await self.generate(messages, system_prompt=system_prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析思考结果（使用集成的parse方法）
            thought_analysis = self.parse(response_text, format_type="structured")
            
            # 处理解析结果，提取关键信息
            analysis_text = thought_analysis.get("分析", thought_analysis.get("analysis", response_text))
            strategy_text = thought_analysis.get("策略", thought_analysis.get("strategy", ""))
            tools_text = thought_analysis.get("工具需求", thought_analysis.get("tools", ""))
            confidence_text = thought_analysis.get("信心评估", thought_analysis.get("confidence", "5"))
            
            # 判断是否需要工具
            needs_tools = ("需要" in tools_text or "使用" in tools_text) and available_tools
            
            # 提取信心分数
            try:
                confidence = int(''.join(filter(str.isdigit, str(confidence_text))))
                confidence = max(1, min(10, confidence))  # 限制在1-10范围
            except (ValueError, TypeError):
                confidence = 5
            
            # 创建思考消息
            thought_content = f"💭 思考 {thought_count}:\n\n**分析**: {analysis_text}"
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
                "confidence": confidence
            }
            
            # 创建状态更新
            state_update = {
                "messages": [thought_message],
                "thought_count": thought_count,
                "last_thought": analysis_text,
                "needs_tools": needs_tools,
                "confidence": confidence
            }
            
            # 决定下一步行动并返回Command
            if needs_tools:
                return Command(update=state_update, goto="action")
            else:
                # 直接给出最终答案
                return Command(update=state_update, goto="final_answer")
            
        except Exception as e:
            error_msg = str(e)
            print(f"[ThoughtNode] LLM调用失败: {error_msg}")
            
            # 创建错误响应消息
            error_message = self.create_ai_message(
                f"思考过程中遇到问题: {error_msg}，我将基于现有信息尽力回答。"
            )
            
            return Command(
                update={"messages": [error_message], "has_error": True},
                goto="final_answer"
            ) 