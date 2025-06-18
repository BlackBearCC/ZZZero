"""
观察节点 - 分析工具执行结果
"""
from typing import Dict, Any, Optional, List

from ..core.base import BaseNode
from ..core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole
from ..llm.base import BaseLLMProvider


class ObserveNode(BaseNode):
    """观察节点 - 分析工具执行结果并决定下一步"""
    
    def __init__(self,
                 name: str,
                 llm: BaseLLMProvider,
                 **kwargs):
        """
        初始化观察节点
        
        Args:
            name: 节点名称
            llm: LLM提供者
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.OBSERVE, "分析工具执行结果", **kwargs)
        self.llm = llm
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行观察逻辑"""
        context = input_data.context
        
        # 获取工具执行结果
        action_data = {}
        if input_data.previous_output and isinstance(input_data.previous_output, dict):
            action_data = input_data.previous_output
            
        # 构建观察提示
        observe_prompt = self._build_observe_prompt(context, action_data)
        
        # 添加提示到消息历史
        context.messages.append(Message(
            role=MessageRole.USER,
            content=observe_prompt
        ))
        
        # 调用LLM分析结果
        response = await self.llm.generate(context.messages)
        
        # 添加响应到消息历史
        context.messages.append(response)
        
        # 分析观察结果
        analysis = self._analyze_observation(response.content, action_data)
        
        # 决定是否继续
        should_continue = analysis.get("needs_more_info", True)
        next_node = "think" if should_continue else "finalize"
        
        return NodeOutput(
            data={
                "observation": response.content,
                "analysis": analysis,
                "continue": should_continue
            },
            next_node=next_node,
            should_continue=should_continue,
            metadata={
                "has_sufficient_info": not should_continue,
                "confidence": analysis.get("confidence", 0.5)
            }
        )
        
    def _build_observe_prompt(self, context: Any, action_data: Dict[str, Any]) -> str:
        """构建观察提示"""
        # 提取工具执行结果
        results = action_data.get("results", [])
        
        # 格式化结果
        results_text = self._format_results(results)
        
        prompt = f"""分析以下工具执行结果：

{results_text}

请分析：
1. 工具执行是否成功？
2. 返回的信息是否有用？
3. 是否已经收集到足够的信息来回答用户的问题？
4. 如果信息不足，还需要什么信息？

基于分析，决定：
- 如果信息充足，总结关键发现
- 如果信息不足，说明还需要什么"""
        
        return prompt
        
    def _format_results(self, results: List[Dict[str, Any]]) -> str:
        """格式化工具执行结果"""
        if not results:
            return "没有工具执行结果"
            
        formatted = []
        for i, result in enumerate(results, 1):
            tool_name = result.get("tool", "未知工具")
            success = result.get("success", False)
            
            if success:
                output = result.get("result", "无输出")
                formatted.append(f"{i}. {tool_name}: ✓ 成功\n   结果: {output}")
            else:
                error = result.get("error", "未知错误")
                formatted.append(f"{i}. {tool_name}: ✗ 失败\n   错误: {error}")
                
        return "\n\n".join(formatted)
        
    def _analyze_observation(self, observation: str, action_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析观察内容"""
        analysis = {
            "needs_more_info": True,
            "confidence": 0.5,
            "key_findings": []
        }
        
        # 简单的关键词分析
        lower_obs = observation.lower()
        
        # 检查是否需要更多信息
        if any(keyword in lower_obs for keyword in ["足够", "充分", "可以回答", "已经收集"]):
            analysis["needs_more_info"] = False
            analysis["confidence"] = 0.8
        elif any(keyword in lower_obs for keyword in ["不足", "需要", "还需", "缺少"]):
            analysis["needs_more_info"] = True
            analysis["confidence"] = 0.6
            
        # 检查工具执行成功率
        results = action_data.get("results", [])
        if results:
            success_count = sum(1 for r in results if r.get("success", False))
            success_rate = success_count / len(results)
            
            if success_rate < 0.5:
                analysis["needs_more_info"] = True
                analysis["confidence"] *= 0.7
                
        # 提取关键发现
        lines = observation.split('\n')
        for line in lines:
            line = line.strip()
            if any(marker in line for marker in ['-', '•', '*', '1.', '2.', '3.']):
                if len(line) > 10:  # 过滤太短的条目
                    analysis["key_findings"].append(line)
                    
        return analysis 