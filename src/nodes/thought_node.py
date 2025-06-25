"""
思考节点 - 负责分析问题和制定行动计划
"""
import sys
import os
from typing import Dict, Any, List

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole
from llm.base import BaseLLMProvider


class ThoughtNode(BaseNode):
    """思考节点 - 分析问题并制定下一步行动计划"""
    
    def __init__(self, name: str, llm: BaseLLMProvider, **kwargs):
        """
        初始化思考节点
        
        Args:
            name: 节点名称
            llm: LLM提供者
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.THINK, "思考分析节点", **kwargs)
        self.llm = llm
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行思考分析"""
        context = input_data.context
        
        # 获取对话历史和可用工具
        messages = context.messages.copy()
        available_tools = context.available_tools or []
        
        # 构建思考提示词
        system_prompt = self._build_thought_prompt(available_tools, context)
        
        # 添加系统提示
        if not any(msg.role == MessageRole.SYSTEM for msg in messages):
            messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ))
        
        # 获取当前思考轮次
        thought_count = context.variables.get("thought_count", 0) + 1
        context.variables["thought_count"] = thought_count
        
        # 生成思考内容
        try:
            response = await self.llm.generate(messages)
            
            # 提取响应内容（Message对象 -> 字符串）
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析思考结果
            thought_analysis = self._parse_thought_response(response_text)
            
            # 创建思考消息
            thought_message = Message(
                role=MessageRole.ASSISTANT,
                content=f"思考 {thought_count}: {thought_analysis['reasoning']}",
                metadata={
                    "node_type": "thought",
                    "thought_count": thought_count,
                    "needs_tools": thought_analysis['needs_tools'],
                    "planned_actions": thought_analysis['planned_actions'],
                    "confidence": thought_analysis['confidence']
                }
            )
            
            # 添加到上下文
            context.messages.append(thought_message)
            
            # 确定下一步行动
            if thought_analysis['needs_tools'] and available_tools:
                next_node = "action"
            elif thought_analysis['has_final_answer']:
                next_node = "final_answer"
            else:
                # 如果没有工具但需要更多信息，直接给出最终答案
                next_node = "final_answer"
            
            return NodeOutput(
                data={
                    "thought": thought_analysis['reasoning'],
                    "needs_tools": thought_analysis['needs_tools'],
                    "planned_actions": thought_analysis['planned_actions'],
                    "has_final_answer": thought_analysis['has_final_answer'],
                    "confidence": thought_analysis['confidence'],
                    "thought_count": thought_count,
                    "messages": [thought_message]
                },
                next_node=next_node,
                should_continue=True,
                metadata={
                    "node_type": "thought",
                    "thought_count": thought_count
                }
            )
            
        except Exception as e:
            error_msg = str(e)
            print(f"[ThoughtNode] LLM调用失败: {error_msg}")
            
            # 如果是API调用失败，需要更智能的处理
            if "InvalidEndpointOrModel" in error_msg or "NotFound" in error_msg:
                # API配置问题，直接给出错误说明
                return NodeOutput(
                    data={
                        "error": f"思考节点执行失败: {error_msg}",
                        "thought": "由于LLM服务不可用，无法进行推理分析",
                        "has_final_answer": True,
                        "needs_tools": False,
                        "confidence": 0
                    },
                    next_node="final_answer", 
                    should_continue=True,
                    metadata={"error": error_msg, "error_type": "llm_api_error"}
                )
            else:
                # 其他错误，尝试基于现有信息回答
                return NodeOutput(
                    data={
                        "error": f"思考节点执行失败: {error_msg}",
                        "thought": "分析过程中遇到错误，将尝试基于现有信息回答",
                        "has_final_answer": True,
                        "needs_tools": False,
                        "confidence": 3
                    },
                    next_node="final_answer",
                    should_continue=True,
                    metadata={"error": error_msg, "error_type": "general_error"}
                )
    
    def _build_thought_prompt(self, available_tools: List[str], context) -> str:
        """构建思考提示词"""
        # 获取记忆上下文
        memory_context = ""
        if hasattr(context, 'variables') and context.variables:
            memory_context = context.variables.get("memory_context", "")
        
        prompt = "你是一个专业的AI助手，擅长分析问题并制定解决方案。\n\n"
        
        # 添加记忆上下文
        if memory_context:
            prompt += f"相关历史信息：\n{memory_context}\n\n"
        
        # 添加工具信息
        if available_tools:
            prompt += f"可用工具：{', '.join(available_tools)}\n\n"
        
        prompt += """请分析当前问题并制定解决方案。你的回复应该包含：

1. **分析**：对问题的深入分析和理解
2. **策略**：解决问题的具体策略和方法
3. **工具需求**：是否需要使用工具以及具体计划
4. **信心评估**：对当前分析的信心程度（1-10分）

回复格式：
分析：[你对问题的分析]
策略：[解决方案的具体步骤]
工具需求：[是否需要工具，需要哪些工具]
信心评估：[1-10分的信心评估]

请保持分析的专业性和准确性。"""
        
        return prompt
    
    def _parse_thought_response(self, response: str) -> Dict[str, Any]:
        """解析思考响应"""
        # 默认值
        result = {
            "reasoning": response,
            "needs_tools": False,
            "planned_actions": [],
            "has_final_answer": False,
            "confidence": 5
        }
        
        try:
            # 解析结构化响应
            lines = response.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('分析：'):
                    current_section = 'analysis'
                    result['reasoning'] = line[3:].strip()
                elif line.startswith('策略：'):
                    current_section = 'strategy'
                elif line.startswith('工具需求：'):
                    current_section = 'tools'
                    tool_text = line[5:].strip()
                    if '需要' in tool_text or '使用' in tool_text:
                        result['needs_tools'] = True
                elif line.startswith('信心评估：'):
                    current_section = 'confidence'
                    try:
                        # 提取数字
                        import re
                        confidence_match = re.search(r'(\d+)', line)
                        if confidence_match:
                            result['confidence'] = int(confidence_match.group(1))
                    except:
                        pass
                elif current_section == 'analysis' and line:
                    result['reasoning'] += f" {line}"
            
            # 判断是否有最终答案
            if result['confidence'] >= 8 and not result['needs_tools']:
                result['has_final_answer'] = True
                
        except Exception as e:
            print(f"解析思考响应失败: {e}")
        
        return result 