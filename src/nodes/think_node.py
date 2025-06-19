"""
思考节点 - 负责分析问题和推理
"""
from typing import Dict, Any, Optional

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole
from llm.base import BaseLLMProvider
try:
    from prompts.templates import ThinkingPromptTemplate
except ImportError:
    # 如果没有模板模块，使用简单实现
    ThinkingPromptTemplate = None


class ThinkNode(BaseNode):
    """思考节点 - 分析问题并生成推理"""
    
    def __init__(self,
                 name: str,
                 llm: BaseLLMProvider,
                 prompt_template: Optional[ThinkingPromptTemplate] = None,
                 **kwargs):
        """
        初始化思考节点
        
        Args:
            name: 节点名称
            llm: LLM提供者
            prompt_template: 思考提示模板
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.THINK, "分析问题并生成推理", **kwargs)
        self.llm = llm
        self.prompt_template = prompt_template or self._get_default_template()
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行思考逻辑"""
        context = input_data.context
        
        # 构建思考提示
        think_prompt = self._build_think_prompt(context, input_data.previous_output)
        
        # 添加思考提示到消息历史
        context.messages.append(Message(
            role=MessageRole.USER,
            content=think_prompt
        ))
        
        # 调用LLM进行思考
        response = await self.llm.generate(context.messages)
        
        # 添加响应到消息历史
        context.messages.append(response)
        
        # 分析思考结果
        analysis = self._analyze_thinking(response.content)
        
        # 决定下一步
        next_node = self._decide_next_node(analysis)
        should_continue = analysis.get("needs_action", True)
        
        return NodeOutput(
            data={
                "thought": response.content,
                "analysis": analysis,
                "confidence": analysis.get("confidence", 0.5)
            },
            next_node=next_node,
            should_continue=should_continue,
            metadata={
                "thinking_type": analysis.get("thinking_type", "general"),
                "key_insights": analysis.get("key_insights", [])
            }
        )
        
    def _build_think_prompt(self, context: Any, previous_output: Any) -> str:
        """构建思考提示"""
        # 提取关键信息
        query = self._extract_query(context)
        previous_thought = None
        previous_action = None
        
        if previous_output and isinstance(previous_output, dict):
            previous_thought = previous_output.get("thought")
            previous_action = previous_output.get("action")
            
        # 使用模板生成提示（不传递工具信息）
        return self.prompt_template.format(
            query=query,
            previous_thought=previous_thought,
            previous_action=previous_action
        )
        
    def _extract_query(self, context: Any) -> str:
        """从上下文中提取查询"""
        # 查找用户消息
        for msg in reversed(context.messages):
            if msg.role == MessageRole.USER:
                # 跳过系统生成的提示
                if not msg.content.startswith("Based on"):
                    return msg.content
        return "No query found"
        
    def _analyze_thinking(self, thought_content: str) -> Dict[str, Any]:
        """分析思考内容"""
        analysis = {
            "needs_action": True,
            "confidence": 0.5,
            "thinking_type": "general",
            "key_insights": []
        }
        
        # 简单的关键词分析
        lower_content = thought_content.lower()
        
        # 检查是否需要行动
        if any(keyword in lower_content for keyword in ["需要", "应该", "可以使用", "调用"]):
            analysis["needs_action"] = True
        elif any(keyword in lower_content for keyword in ["已经", "完成", "不需要", "足够"]):
            analysis["needs_action"] = False
            
        # 评估置信度
        if any(keyword in lower_content for keyword in ["确定", "明确", "显然"]):
            analysis["confidence"] = 0.9
        elif any(keyword in lower_content for keyword in ["可能", "也许", "不确定"]):
            analysis["confidence"] = 0.3
            
        # 确定思考类型
        if "分析" in lower_content:
            analysis["thinking_type"] = "analytical"
        elif "计划" in lower_content:
            analysis["thinking_type"] = "planning"
        elif "反思" in lower_content:
            analysis["thinking_type"] = "reflective"
            
        # 提取关键洞察（简单实现）
        lines = thought_content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') or line.startswith('*') or line.startswith('•'):
                analysis["key_insights"].append(line[1:].strip())
                
        return analysis
        
    def _decide_next_node(self, analysis: Dict[str, Any]) -> Optional[str]:
        """决定下一个节点"""
        if analysis["needs_action"]:
            return "act"  # 默认转到行动节点
        else:
            return "finalize"  # 转到最终化节点
            
    def _get_default_template(self) -> ThinkingPromptTemplate:
        """获取默认思考模板"""
        from prompts.templates import ThinkingPromptTemplate
        return ThinkingPromptTemplate() 