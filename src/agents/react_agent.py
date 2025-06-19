"""
ReAct Agent - 基于Reasoning and Acting范式的智能代理
"""
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.base import BaseAgent, AgentContext
from core.types import AgentType, TaskResult, Message, MessageRole
from core.graph import Graph, GraphBuilder, GraphExecutor
from nodes.think_node import ThinkNode
from nodes.act_node import ActNode
from nodes.observe_node import ObserveNode
from llm.base import BaseLLMProvider
from tools.base import ToolManager


class ReactAgent(BaseAgent):
    """ReAct智能代理 - 循环进行推理和行动"""
    
    def __init__(self,
                 llm: BaseLLMProvider,
                 tool_manager: Optional[ToolManager] = None,
                 max_iterations: int = 5,
                 name: Optional[str] = None,
                 **kwargs):
        """
        初始化ReAct Agent
        
        Args:
            llm: LLM提供者
            tool_manager: 工具管理器（可选）
            max_iterations: 最大迭代次数
            name: Agent名称
            **kwargs: 其他配置
        """
        super().__init__(
            agent_type=AgentType.REACT,
            name=name or "react_agent",
            description="基于ReAct范式的智能代理",
            **kwargs
        )
        self.llm = llm
        self.tool_manager = tool_manager
        self.max_iterations = max_iterations
        self.executor = GraphExecutor(max_iterations=max_iterations)
        
    def build_graph(self) -> Graph:
        """构建ReAct执行图"""
        builder = GraphBuilder("react_graph")
        
        # 创建节点
        think_node = ThinkNode("think", self.llm)
        
        # 创建最终化节点
        from nodes.finalize_node import FinalizeNode
        finalize_node = FinalizeNode("finalize", self.llm)
        
        # 判断是否有工具可用
        if self.tool_manager and self.tool_manager.list_tools():
            # 有工具时使用完整的ReAct流程
            act_node = ActNode("act", self.llm, self.tool_manager)
            observe_node = ObserveNode("observe", self.llm)
            
            # 构建完整图
            graph = (builder
                .add_node(think_node)
                .add_node(act_node)
                .add_node(observe_node)
                .add_node(finalize_node)
                .entry("think")
                .connect("think", "act")
                .connect("act", "observe")
                .connect("observe", "think", condition="output['continue'] == True")
                .connect("observe", "finalize", condition="output['continue'] == False")
                .connect("think", "finalize", condition="output['should_continue'] == False")
                .exit("finalize")
                .build()
            )
        else:
            # 没有工具时，直接从思考到最终化
            graph = (builder
                .add_node(think_node)
                .add_node(finalize_node)
                .entry("think")
                .connect("think", "finalize")
                .exit("finalize")
                .build()
            )
        
        return graph
        
    async def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> TaskResult:
        """运行ReAct Agent"""
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建任务结果
        result = TaskResult(
            task_id=task_id,
            query=query,
            agent_type=self.agent_type
        )
        
        try:
            # 初始化
            await self.initialize()
            
            # 获取可用工具列表
            available_tools = []
            if self.tool_manager:
                available_tools = self.tool_manager.list_tools()
            
            # 创建执行上下文
            agent_context = AgentContext(
                task_id=task_id,
                agent_type=self.agent_type,
                available_tools=available_tools,
                messages=[
                    Message(
                        role=MessageRole.SYSTEM,
                        content=self._build_system_prompt()
                    ),
                    Message(
                        role=MessageRole.USER,
                        content=query
                    )
                ],
                variables=context or {}
            )
            print(f"agent_context: {agent_context}")
            # 构建并执行图
            graph = self.build_graph()
            node_results = await self.executor.execute(graph, agent_context)
            
            # 提取最终结果
            for node_result in reversed(node_results):
                if node_result.node_name == "finalize" and node_result.output:
                    result.result = node_result.output.data.get("answer", "无法生成答案")
                    result.success = True
                    break
                    
            # 构建执行轨迹
            result.execution_trace = [
                {
                    "node": nr.node_name,
                    "type": nr.node_type.value,
                    "duration": nr.duration,
                    "state": nr.state.value,
                    "output": nr.output.data if nr.output else None
                }
                for nr in node_results
            ]
            
            # 计算指标
            result.metrics = {
                "total_nodes": len(node_results),
                "iterations": sum(1 for nr in node_results if nr.node_name == "think"),
                "tool_calls": sum(1 for nr in node_results if nr.node_name == "act"),
                "total_duration": sum(nr.duration or 0 for nr in node_results)
            }
            
        except Exception as e:
            result.success = False
            result.error = str(e)
            
        return result
        
    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        # 检查是否有工具可用
        if self.tool_manager and self.tool_manager.list_tools():
            return """你是一个基于ReAct（Reasoning and Acting）范式的智能助手。

你的工作流程：
1. **思考（Thought）**: 推理分析，确定问题的关键信息和解决思路，
2. **行动（Action）**: 根据思考结果选择合适的工具执行，或者决定不使用工具
3. **观察（Observation）**: 分析工具执行结果，判断是否需要继续
4. **最终回答（Final）**: 当信息充足时生成完整答案

重要规则：
- **思考阶段**：专注于分析和推理，不考虑具体工具，但可以直接跳到最终回答
- **行动阶段**：此时才会获得工具信息，选择最合适的工具或选择不使用工具
- **观察阶段**：基于结果决定是否继续循环或直接给出答案
- 每次只执行一个工具，仔细分析每个结果

请始终保持清晰的推理过程。"""
        else:
            # 没有工具时的提示
            return """你是一个智能助手。

由于当前没有可用的外部工具，你需要：
1. 仔细分析用户的问题
2. 基于你的知识库提供最佳答案
3. 如果无法确定答案，诚实地说明情况
4. 提供清晰、有帮助的回复

请保持友好、专业的态度回答用户问题。"""
        
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