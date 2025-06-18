"""
最终化节点 - 负责生成最终答案
"""
from typing import Dict, Any, Optional, List

from ..core.base import BaseNode
from ..core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole
from ..llm.base import BaseLLMProvider


class FinalizeNode(BaseNode):
    """最终化节点 - 整合所有信息生成最终答案"""
    
    def __init__(self,
                 name: str,
                 llm: BaseLLMProvider,
                 **kwargs):
        """
        初始化最终化节点
        
        Args:
            name: 节点名称
            llm: LLM提供者
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.FINALIZE, "生成最终答案", **kwargs)
        self.llm = llm
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行最终化逻辑"""
        context = input_data.context
        
        # 收集执行过程中的关键信息
        execution_summary = self._build_execution_summary(context)
        
        # 构建最终化提示
        finalize_prompt = self._build_finalize_prompt(context, execution_summary)
        
        # 添加提示到消息历史
        context.messages.append(Message(
            role=MessageRole.USER,
            content=finalize_prompt
        ))
        
        # 调用LLM生成最终答案
        response = await self.llm.generate(context.messages)
        
        # 添加响应到消息历史
        context.messages.append(response)
        
        # 提取答案质量指标
        quality_metrics = self._assess_answer_quality(response.content, execution_summary)
        
        return NodeOutput(
            data={
                "answer": response.content,
                "summary": execution_summary,
                "quality_metrics": quality_metrics
            },
            next_node=None,  # 最终节点，没有下一个节点
            should_continue=False,  # 结束执行
            metadata={
                "total_steps": execution_summary.get("total_steps", 0),
                "tools_used": execution_summary.get("tools_used", []),
                "confidence": quality_metrics.get("confidence", 0.8)
            }
        )
        
    def _build_execution_summary(self, context: Any) -> Dict[str, Any]:
        """构建执行摘要"""
        summary = {
            "query": self._extract_original_query(context),
            "total_steps": 0,
            "thoughts": [],
            "actions": [],
            "observations": [],
            "tools_used": set(),
            "key_findings": []
        }
        
        # 分析消息历史，提取关键信息
        for i, msg in enumerate(context.messages):
            content = msg.content.lower()
            
            # 识别思考步骤
            if "思考" in content or "分析" in content:
                summary["thoughts"].append({
                    "step": i,
                    "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                })
                
            # 识别行动步骤
            elif "工具" in content or "执行" in content:
                summary["actions"].append({
                    "step": i,
                    "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                })
                
            # 识别观察步骤
            elif "结果" in content or "发现" in content:
                summary["observations"].append({
                    "step": i,
                    "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                })
                
        summary["total_steps"] = len(summary["thoughts"]) + len(summary["actions"]) + len(summary["observations"])
        
        # 提取使用的工具
        for msg in context.messages:
            if "tool" in msg.content:
                # 简单的工具名提取
                import re
                tool_matches = re.findall(r'"tool":\s*"([^"]+)"', msg.content)
                summary["tools_used"].update(tool_matches)
                
        summary["tools_used"] = list(summary["tools_used"])
        
        return summary
        
    def _build_finalize_prompt(self, context: Any, summary: Dict[str, Any]) -> str:
        """构建最终化提示"""
        prompt = f"""基于整个执行过程，生成最终答案。

原始问题：{summary['query']}

执行摘要：
- 总步骤数：{summary['total_steps']}
- 思考次数：{len(summary['thoughts'])}
- 行动次数：{len(summary['actions'])}
- 观察次数：{len(summary['observations'])}
- 使用工具：{', '.join(summary['tools_used']) if summary['tools_used'] else '无'}

关键发现：
"""
        
        # 添加最近的观察结果作为关键发现
        for obs in summary['observations'][-3:]:  # 最多取最后3个观察
            prompt += f"- {obs['content']}\n"
            
        prompt += """
请生成一个完整、准确、有用的最终答案：

要求：
1. **完整性**：确保回答了用户问题的所有方面
2. **准确性**：基于收集到的信息，确保答案准确无误
3. **清晰性**：使用简洁明了的语言，避免冗余
4. **实用性**：如果适用，提供具体的建议或下一步行动
5. **诚实性**：如果某些信息不确定或缺失，明确指出

请直接给出答案，不需要重复执行过程。"""
        
        return prompt
        
    def _extract_original_query(self, context: Any) -> str:
        """提取原始查询"""
        # 查找第一个用户消息（跳过系统消息）
        for msg in context.messages:
            if msg.role == MessageRole.USER:
                # 检查是否是原始查询（不是系统生成的提示）
                if not any(keyword in msg.content.lower() for keyword in ["基于", "分析", "选择", "工具"]):
                    return msg.content
        return "未找到原始查询"
        
    def _assess_answer_quality(self, answer: str, summary: Dict[str, Any]) -> Dict[str, Any]:
        """评估答案质量"""
        metrics = {
            "completeness": 0.0,
            "confidence": 0.0,
            "clarity": 0.0,
            "usefulness": 0.0
        }
        
        # 简单的启发式评估
        answer_lower = answer.lower()
        
        # 完整性：答案长度和是否包含关键信息
        if len(answer) > 100:
            metrics["completeness"] += 0.5
        if len(answer) > 300:
            metrics["completeness"] += 0.3
        if any(tool in answer_lower for tool in summary["tools_used"]):
            metrics["completeness"] += 0.2
            
        # 置信度：基于执行步骤和工具使用
        if summary["total_steps"] > 3:
            metrics["confidence"] += 0.4
        if len(summary["tools_used"]) > 0:
            metrics["confidence"] += 0.4
        if "不确定" not in answer_lower and "可能" not in answer_lower:
            metrics["confidence"] += 0.2
            
        # 清晰度：是否有结构化的表达
        if any(marker in answer for marker in ["1.", "2.", "•", "-", "首先", "其次"]):
            metrics["clarity"] += 0.5
        if len(answer.split('\n')) > 3:  # 有段落划分
            metrics["clarity"] += 0.3
        if answer.count('。') > 3:  # 句子结构清晰
            metrics["clarity"] += 0.2
            
        # 实用性：是否包含具体建议
        useful_keywords = ["建议", "可以", "应该", "步骤", "方法", "解决方案"]
        if any(keyword in answer_lower for keyword in useful_keywords):
            metrics["usefulness"] += 0.6
        if "具体" in answer_lower or "例如" in answer_lower:
            metrics["usefulness"] += 0.4
            
        # 确保所有指标在0-1范围内
        for key in metrics:
            metrics[key] = min(1.0, max(0.0, metrics[key]))
            
        # 计算总体置信度
        metrics["overall"] = sum(metrics.values()) / len(metrics)
        
        return metrics 