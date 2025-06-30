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
    
    def __init__(self,
                 llm: BaseLLMProvider,
                 tool_manager: Optional[Union[ToolManager, 'MCPToolManager']] = None,
                 max_iterations: int = 5,
                 name: Optional[str] = None,
                 memory_enabled: bool = True,
                 memory_store: Optional[SQLiteMemoryStore] = None,
                 short_term_limit: int = 30000,
                 session_id: Optional[str] = None,
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
                # 使用新的分离式ReAct节点架构
                from nodes.thought_node import ThoughtNode
                from nodes.action_node import ActionNode
                from nodes.observation_node import ObservationNode
                from nodes.final_answer_node import FinalAnswerNode
                
                # 创建各个节点
                thought_node = ThoughtNode("thought", self.llm)
                action_node = ActionNode("action", self.llm, self.tool_manager)
                observation_node = ObservationNode("observation", self.llm, self.max_iterations)
                final_answer_node = FinalAnswerNode("final_answer", self.llm)
                
                # 构建分离式ReAct图
                graph = (builder
                    .add_node(thought_node)
                    .add_node(action_node)
                    .add_node(observation_node)
                    .add_node(final_answer_node)
                    .entry("thought")
                    .connect("thought", "action", condition="output.get('needs_tools', False)")
                    .connect("thought", "final_answer", condition="not output.get('needs_tools', False)")
                    .connect("action", "observation")
                    .connect("observation", "thought", condition="output.get('next_action') == 'thought'")
                    .connect("observation", "final_answer", condition="output.get('next_action') == 'final_answer'")
                    .exit("final_answer")
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