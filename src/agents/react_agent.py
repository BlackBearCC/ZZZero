"""
ReAct Agent - 基于Reasoning and Acting范式的智能代理
"""
import uuid
from typing import Dict, Any, Optional, List, AsyncIterator
from datetime import datetime

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.base import BaseAgent, AgentContext
from core.types import AgentType, TaskResult, Message, MessageRole
from core.graph import Graph, GraphBuilder, GraphExecutor

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
        
    def build_graph(self, use_stream: bool = False) -> Graph:
        """构建ReAct执行图
        
        Args:
            use_stream: 是否使用流式节点
        """
        builder = GraphBuilder("react_graph")
        
        # 判断是否有工具可用
        if self.tool_manager and self.tool_manager.list_tools():
            if use_stream:
                # 使用流式节点
                from nodes.stream_react_agent_node import StreamReactAgentNode
                agent_node = StreamReactAgentNode("agent", self.llm, self.tool_manager)
                
                # 流式节点不需要工具节点，内部处理工具调用
                graph = (builder
                    .add_node(agent_node)
                    .entry("agent")
                    .build()
                )
            else:
                # 使用标准ReAct节点
                from nodes.react_agent_node import ReactAgentNode
                from nodes.react_tool_node import ReactToolNode
                
                agent_node = ReactAgentNode("agent", self.llm, self.tool_manager)
                tool_node = ReactToolNode("tools", self.tool_manager)
                
                # 构建标准双节点ReAct图
                graph = (builder
                    .add_node(agent_node)
                    .add_node(tool_node) 
                    .entry("agent")
                    .connect("agent", "tools", condition="output.get('has_tool_calls', False)")
                    .connect("tools", "agent")
                    .exit("agent")
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
        """运行ReAct Agent"""
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
        graph = self.build_graph(use_stream=False)  # 标准模式
        node_results = await self.executor.execute(graph, agent_context)
        
        # 提取最终结果 - 从最后一个有效的输出节点获取结果
        if node_results:
            # 寻找最后一个成功执行的agent或chat节点
            for node_result in reversed(node_results):
                if (node_result.node_name in ["agent", "chat"] and 
                    node_result.output and 
                    node_result.output.data):
                    
                    # 从消息中提取最终回答
                    messages = node_result.output.data.get("messages", [])
                    if messages:
                        last_message = messages[-1]
                        result.result = last_message.content
                        result.success = True
                        break
                    
                    # 备用：从agent_response或chat_response字段获取
                    agent_response = (node_result.output.data.get("agent_response") or 
                                    node_result.output.data.get("chat_response"))
                    if agent_response:
                        result.result = agent_response
                        result.success = True
                        break
            
            # 如果没有找到有效结果，设置默认消息
            if not result.success:
                result.result = "抱歉，无法生成回复"
                
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
            

        return result
    
    async def stream_run(self, query: str, context: Optional[Dict[str, Any]] = None) -> AsyncIterator[Dict[str, Any]]:
        """流式运行ReAct Agent"""
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
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
        
        # 构建流式图
        graph = self.build_graph(use_stream=True)
        
        # 创建节点输入
        from core.types import NodeInput
        node_input = NodeInput(
            context=agent_context.to_execution_context(),
            previous_output=None,
            parameters={}
        )
        
        # 直接执行流式节点
        stream_node = graph.nodes["agent"]
        
        # 如果是流式节点，直接调用其流式方法
        if hasattr(stream_node, '_stream_react_generation'):
            async for chunk_data in stream_node._stream_react_generation(agent_context.messages):
                yield {
                    "type": chunk_data["type"],
                    "content": chunk_data["content"],
                    "task_id": task_id,
                    "metadata": chunk_data
                }
        else:
            # 回退到标准执行
            result = await self.run(query, context)
            yield {
                "type": "final_result",
                "content": result.result,
                "task_id": task_id,
                "metadata": {"success": result.success}
            }
        
    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        # 检查是否有工具可用
        if self.tool_manager and self.tool_manager.list_tools():
            # 获取工具描述
            tools_desc = self.tool_manager.get_tools_description()
            tool_names = self.tool_manager.list_tools()
            
            return f"""你是一个基于ReAct（Reasoning and Acting）范式的智能助手。

可用工具：
{tools_desc}

使用以下格式进行推理和行动：

Question: 你需要回答的问题
Thought: 你应该思考要做什么
Action: 要采取的行动，应该是 [{', '.join(tool_names)}] 中的一个
Action Input: 行动的输入
Observation: 行动的结果
... (这个 Thought/Action/Action Input/Observation 可以重复N次，直到你认为你已经得到了最终答案)
Final Answer: 对原始问题的最终答案

重要规则：
1. 如果你有足够信息回答问题，直接给出 Final Answer
2. 如果需要更多信息，使用可用的工具
3. 每次只使用一个工具
4. 仔细分析工具的返回结果

开始！"""
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