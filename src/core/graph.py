"""
图结构和执行引擎 - 实现节点编排和执行
"""
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import networkx as nx
from enum import Enum

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.base import BaseNode, BaseExecutor, NodeResult, AgentContext, ExecutionState
from core.types import NodeInput, NodeOutput, NodeType


class ConnectionType(str, Enum):
    """连接类型"""
    ALWAYS = "always"  # 总是执行
    CONDITIONAL = "conditional"  # 条件执行
    PARALLEL = "parallel"  # 并行执行


@dataclass
class NodeConnection:
    """节点连接"""
    from_node: str
    to_node: str
    connection_type: ConnectionType = ConnectionType.ALWAYS
    condition: Optional[str] = None  # 条件表达式
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def evaluate_condition(self, context: Dict[str, Any]) -> bool:
        """评估条件"""
        if self.connection_type == ConnectionType.ALWAYS:
            return True
        
        if self.connection_type == ConnectionType.CONDITIONAL and self.condition:
            try:
                # 简单的条件评估 - 实际可以使用更复杂的表达式引擎
                return eval(self.condition, {"__builtins__": {}}, context)
            except:
                return False
                
        return True


@dataclass
class ExecutionTrace:
    """执行轨迹"""
    graph_name: str
    task_id: str
    node_results: List[NodeResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    state: ExecutionState = ExecutionState.PENDING
    error: Optional[str] = None
    
    @property
    def duration(self) -> Optional[float]:
        """计算执行时长(秒)"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
        
    def add_node_result(self, result: NodeResult):
        """添加节点结果"""
        self.node_results.append(result)
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "graph_name": self.graph_name,
            "task_id": self.task_id,
            "node_results": [
                {
                    "node_name": r.node_name,
                    "node_type": r.node_type.value,
                    "state": r.state.value,
                    "duration": r.duration,
                    "error": r.error
                } for r in self.node_results
            ],
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "state": self.state.value,
            "error": self.error
        }


class Graph:
    """执行图"""
    
    def __init__(self, name: str, description: Optional[str] = None):
        self.name = name
        self.description = description
        self.nodes: Dict[str, BaseNode] = {}
        self.connections: List[NodeConnection] = []
        self.entry_point: Optional[str] = None
        self.exit_points: Set[str] = set()
        self._graph = nx.DiGraph()
        
    def add_node(self, node: BaseNode) -> "Graph":
        """添加节点"""
        self.nodes[node.name] = node
        self._graph.add_node(node.name, node=node)
        return self
        
    def add_connection(self, 
                      from_node: str,
                      to_node: str,
                      connection_type: ConnectionType = ConnectionType.ALWAYS,
                      condition: Optional[str] = None) -> "Graph":
        """添加连接"""
        if from_node not in self.nodes:
            raise ValueError(f"节点 {from_node} 不存在")
        if to_node not in self.nodes:
            raise ValueError(f"节点 {to_node} 不存在")
            
        connection = NodeConnection(
            from_node=from_node,
            to_node=to_node,
            connection_type=connection_type,
            condition=condition
        )
        self.connections.append(connection)
        self._graph.add_edge(from_node, to_node, connection=connection)
        return self
        
    def set_entry_point(self, node_name: str) -> "Graph":
        """设置入口节点"""
        if node_name not in self.nodes:
            raise ValueError(f"节点 {node_name} 不存在")
        self.entry_point = node_name
        return self
        
    def add_exit_point(self, node_name: str) -> "Graph":
        """添加出口节点"""
        if node_name not in self.nodes:
            raise ValueError(f"节点 {node_name} 不存在")
        self.exit_points.add(node_name)
        return self
        
    def get_next_nodes(self, current_node: str, context: Dict[str, Any]) -> List[str]:
        """获取下一个要执行的节点"""
        next_nodes = []
        
        for connection in self.connections:
            if connection.from_node == current_node:
                if connection.evaluate_condition(context):
                    next_nodes.append(connection.to_node)
                    
        return next_nodes
        
    def validate(self) -> bool:
        """验证图的有效性"""
        if not self.entry_point:
            raise ValueError("未设置入口节点")
            
        # 对于ReAct等需要循环的图，跳过循环检查
        # 只检查强连通分量，确保图结构合理
        strongly_connected = list(nx.strongly_connected_components(self._graph))
        
        # 检查是否有强连通分量包含多个节点（实际的循环）
        for component in strongly_connected:
            if len(component) > 1:
                # 检查是否是允许的循环模式（如ReAct的think->act->observe->think）
                if not self._is_allowed_cycle(component):
                    raise ValueError(f"图中存在不允许的循环: {component}")
            
        # 检查所有节点是否可达（在有向图中使用弱连通性）
        if not nx.is_weakly_connected(self._graph):
            # 找出不可达的节点
            reachable = set()
            stack = [self.entry_point]
            visited = set()
            
            while stack:
                node = stack.pop()
                if node not in visited:
                    visited.add(node)
                    reachable.add(node)
                    # 添加后继节点
                    stack.extend(self._graph.successors(node))
                    # 添加前驱节点（对于循环图）
                    stack.extend(self._graph.predecessors(node))
            
            unreachable = set(self.nodes.keys()) - reachable
            if unreachable:
                raise ValueError(f"以下节点不可达: {unreachable}")
            
        return True
    
    def _is_allowed_cycle(self, component: set) -> bool:
        """检查是否是允许的循环模式"""
        # 允许的循环模式：
        # 1. 传统ReAct循环 (think, act, observe)
        react_pattern = {"think", "act", "observe"}
        
        # 2. 标准LangGraph ReAct循环 (agent, tools)
        langgraph_react_pattern = {"agent", "tools"}
        
        # 如果循环包含ReAct模式的子集，则允许
        if component.issubset(react_pattern) and len(component) >= 2:
            return True
            
        # 如果循环包含LangGraph ReAct模式，则允许
        if component.issubset(langgraph_react_pattern) and len(component) >= 2:
            return True
            
        # 允许包含finalize节点的循环（可能的路径）
        if "finalize" in component:
            return True
            
        # 其他情况需要具体判断，暂时允许所有包含条件连接的循环
        for node in component:
            outgoing_edges = self._graph.edges(node, data=True)
            for _, _, data in outgoing_edges:
                connection = data.get('connection')
                if connection and connection.connection_type == ConnectionType.CONDITIONAL:
                    return True
                    
        return False
        
    def visualize(self) -> str:
        """生成图的可视化表示（Mermaid格式）"""
        lines = ["graph TD"]
        
        # 添加节点
        for node_name, node in self.nodes.items():
            shape = "[]" if node.node_type == NodeType.ROUTER else "()"
            label = f"{node_name}\\n[{node.node_type.value}]"
            lines.append(f"    {node_name}{shape[0]}\"{label}\"{shape[1]}")
            
        # 添加连接
        for conn in self.connections:
            if conn.connection_type == ConnectionType.CONDITIONAL:
                label = f"|{conn.condition}|"
                lines.append(f"    {conn.from_node} -->|{label}| {conn.to_node}")
            else:
                lines.append(f"    {conn.from_node} --> {conn.to_node}")
                
        return "\n".join(lines)


class GraphBuilder:
    """图构建器 - 提供流式API"""
    
    def __init__(self, name: str):
        self.graph = Graph(name)
        
    def add_node(self, node: BaseNode) -> "GraphBuilder":
        """添加节点"""
        self.graph.add_node(node)
        return self
        
    def connect(self,
               from_node: str,
               to_node: str,
               **kwargs) -> "GraphBuilder":
        """连接节点"""
        self.graph.add_connection(from_node, to_node, **kwargs)
        return self
        
    def entry(self, node_name: str) -> "GraphBuilder":
        """设置入口"""
        self.graph.set_entry_point(node_name)
        return self
        
    def exit(self, node_name: str) -> "GraphBuilder":
        """添加出口"""
        self.graph.add_exit_point(node_name)
        return self
        
    def build(self) -> Graph:
        """构建并验证图"""
        self.graph.validate()
        return self.graph


class GraphExecutor(BaseExecutor):
    """图执行器 - 负责执行图"""
    
    def __init__(self, max_iterations: int = 100):
        self.max_iterations = max_iterations
        
    async def execute(self,
                     graph: Graph,
                     context: AgentContext,
                     **kwargs) -> List[NodeResult]:
        """执行图"""
        trace = ExecutionTrace(
            graph_name=graph.name,
            task_id=context.task_id,
            state=ExecutionState.RUNNING
        )
        
        try:
            # 验证图
            graph.validate()
            
            # 执行节点
            visited = set()
            current_nodes = [graph.entry_point]
            iteration = 0
            
            while current_nodes and iteration < self.max_iterations:
                iteration += 1
                
                # 并行执行当前层的节点
                tasks = []
                for node_name in current_nodes:
                    if node_name not in visited:
                        visited.add(node_name)
                        node = graph.nodes[node_name]
                        
                        # 构建节点输入
                        node_input = self._build_node_input(
                            context, 
                            trace.node_results
                        )
                        
                        # 创建执行任务
                        task = asyncio.create_task(
                            self._execute_node(node, node_input, trace)
                        )
                        tasks.append((node_name, task))
                
                # 等待所有节点执行完成
                next_nodes = []
                for node_name, task in tasks:
                    result = await task
                    
                    # 根据结果决定下一步
                    if result.state == ExecutionState.SUCCESS:
                        if result.output.should_continue:
                            # 获取下一个节点
                            eval_context = {
                                "output": result.output.data,
                                "metadata": result.output.metadata
                            }
                            next_candidates = graph.get_next_nodes(
                                node_name, 
                                eval_context
                            )
                            next_nodes.extend(next_candidates)
                            
                            # 如果输出指定了下一个节点
                            if result.output.next_node:
                                if result.output.next_node in graph.nodes:
                                    next_nodes.append(result.output.next_node)
                
                # 去重并更新当前节点列表
                current_nodes = list(set(next_nodes))
                
                # 检查是否到达出口
                if any(node in graph.exit_points for node in visited):
                    break
                    
            # 完成执行
            trace.end_time = datetime.now()
            trace.state = ExecutionState.SUCCESS
            
        except Exception as e:
            trace.end_time = datetime.now()
            trace.state = ExecutionState.FAILED
            trace.error = str(e)
            raise
            
        return trace.node_results
        
    async def _execute_node(self,
                          node: BaseNode,
                          input_data: NodeInput,
                          trace: ExecutionTrace) -> NodeResult:
        """执行单个节点"""
        try:
            result = await node.run(input_data)
            trace.add_node_result(result)
            return result
        except Exception as e:
            # 创建失败结果
            result = NodeResult(
                node_name=node.name,
                node_type=node.node_type,
                output=None,
                state=ExecutionState.FAILED,
                error=str(e),
                end_time=datetime.now()
            )
            trace.add_node_result(result)
            raise
            
    def _build_node_input(self,
                         context: AgentContext,
                         previous_results: List[NodeResult]) -> NodeInput:
        """构建节点输入"""
        # 获取最后一个成功节点的输出
        previous_output = None
        for result in reversed(previous_results):
            if result.state == ExecutionState.SUCCESS and result.output:
                previous_output = result.output.data
                break
                
        return NodeInput(
            context=context.to_execution_context(),
            previous_output=previous_output,
            parameters={}
        ) 