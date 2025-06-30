"""
图结构和执行引擎 - 基于LangGraph设计理念重构
"""
from typing import Dict, List, Any, Optional, Set, Tuple, Union, Callable, TypeVar, Generic, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import networkx as nx
from enum import Enum
import inspect

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.base import BaseNode, BaseExecutor, NodeResult, ExecutionState
from core.types import NodeInput, NodeOutput, NodeType

T = TypeVar('T')  # 状态类型


class RouteResult:
    """路由结果 - 可以是节点名称、节点列表或END"""
    def __init__(self, target: Union[str, List[str], None]):
        if target is None:
            self.targets = []
            self.is_end = True
        elif isinstance(target, str):
            if target == "__end__" or target == "END":
                self.targets = []
                self.is_end = True
            else:
                self.targets = [target]
                self.is_end = False
        elif isinstance(target, list):
            self.targets = target
            self.is_end = False
        else:
            raise ValueError(f"无效的路由目标: {target}")
    
    def __str__(self):
        return f"RouteResult(targets={self.targets}, is_end={self.is_end})"


class Command:
    """命令对象 - 用于同时更新状态和控制流程"""
    def __init__(self, 
                 update: Optional[Dict[str, Any]] = None,
                 goto: Optional[Union[str, List[str]]] = None):
        self.update = update or {}
        self.goto = goto
    
    def __str__(self):
        return f"Command(update={self.update}, goto={self.goto})"


class Send:
    """发送对象 - 用于动态创建新的执行分支"""
    def __init__(self, node: str, state: Dict[str, Any]):
        self.node = node
        self.state = state
    
    def __str__(self):
        return f"Send(node={self.node}, state={self.state})"


# 路由函数类型定义
RouteFunction = Callable[[Dict[str, Any]], Union[str, List[str], RouteResult, None]]
ConditionalRouteFunction = Callable[[Dict[str, Any]], Union[str, List[str], Command, Send, List[Send], RouteResult, None]]





@dataclass
class Edge:
    """边定义"""
    from_node: str
    to_node: str
    condition: Optional[RouteFunction] = None
    
    def can_traverse(self, state: Dict[str, Any]) -> bool:
        """检查是否可以遍历此边"""
        if self.condition is None:
            return True
        
        try:
            result = self.condition(state)
            # 如果路由函数返回的目标包含此边的目标节点，则可以遍历
            if isinstance(result, RouteResult):
                return self.to_node in result.targets
            elif isinstance(result, str):
                return result == self.to_node
            elif isinstance(result, list):
                return self.to_node in result
            return bool(result)
        except Exception as e:
            print(f"边条件评估失败: {e}")
            return False


@dataclass
class ConditionalEdge:
    """条件边定义"""
    from_node: str
    route_function: ConditionalRouteFunction
    route_map: Optional[Dict[str, str]] = None  # 路由映射
    
    def get_next_nodes(self, state: Dict[str, Any]) -> Tuple[List[str], Optional[Command], List[Send]]:
        """获取下一个节点列表"""
        try:
            result = self.route_function(state)
            
            # 处理Command返回
            if isinstance(result, Command):
                if result.goto is None:
                    return [], result, []
                elif isinstance(result.goto, str):
                    target = self._map_route(result.goto)
                    return [target] if target else [], result, []
                elif isinstance(result.goto, list):
                    targets = [self._map_route(t) for t in result.goto if self._map_route(t)]
                    return targets, result, []
            
            # 处理Send返回
            elif isinstance(result, Send):
                return [], None, [result]
            
            # 处理Send列表返回
            elif isinstance(result, list) and all(isinstance(s, Send) for s in result):
                return [], None, result
            
            # 处理RouteResult返回
            elif isinstance(result, RouteResult):
                if result.is_end:
                    return [], None, []
                targets = [self._map_route(t) for t in result.targets if self._map_route(t)]
                return targets, None, []
            
            # 处理字符串返回
            elif isinstance(result, str):
                target = self._map_route(result)
                return [target] if target else [], None, []
            
            # 处理字符串列表返回
            elif isinstance(result, list):
                targets = [self._map_route(t) for t in result if isinstance(t, str) and self._map_route(t)]
                return targets, None, []
            
            # 处理None返回
            elif result is None:
                return [], None, []
            
            else:
                print(f"未知的路由函数返回类型: {type(result)}")
                return [], None, []
                
        except Exception as e:
            print(f"条件边路由失败: {e}")
            return [], None, []
    
    def _map_route(self, route_key: str) -> Optional[str]:
        """映射路由键到实际节点名"""
        if route_key in ["__end__", "END", None]:
            return None
        
        if self.route_map:
            return self.route_map.get(route_key, route_key)
        return route_key





class StateGraph(Generic[T]):
    """状态图 - 基于LangGraph设计理念"""
    
    def __init__(self, 
                 state_schema: Optional[type] = None,
                 name: str = "state_graph"):
        self.name = name
        self.state_schema = state_schema or dict
        self.nodes: Dict[str, BaseNode] = {}
        self.edges: List[Edge] = []
        self.conditional_edges: List[ConditionalEdge] = []
        self.entry_point: Optional[str] = None
        self.compiled = False
        
    def add_node(self, name: str, node: BaseNode) -> 'StateGraph[T]':
        """添加节点"""
        if name in self.nodes:
            raise ValueError(f"节点 {name} 已存在")
        
        self.nodes[name] = node
        # 确保节点名称匹配
        node.name = name
        return self
    
    def add_edge(self, from_node: str, to_node: str) -> 'StateGraph[T]':
        """添加普通边"""
        self._validate_nodes_exist(from_node, to_node)
        
        edge = Edge(from_node=from_node, to_node=to_node)
        self.edges.append(edge)
        return self
    
    def add_conditional_edges(self,
                            from_node: str,
                            route_function: ConditionalRouteFunction,
                            route_map: Optional[Dict[str, str]] = None) -> 'StateGraph[T]':
        """添加条件边"""
        if from_node not in self.nodes and from_node not in ["__start__", "START"]:
            raise ValueError(f"源节点 {from_node} 不存在")
        
        conditional_edge = ConditionalEdge(
            from_node=from_node,
            route_function=route_function,
            route_map=route_map
        )
        self.conditional_edges.append(conditional_edge)
        return self
    
    def set_entry_point(self, node_name: str) -> 'StateGraph[T]':
        """设置入口点"""
        if node_name not in self.nodes:
            raise ValueError(f"节点 {node_name} 不存在")
        self.entry_point = node_name
        return self
    
    def get_next_nodes(self, current_node: str, state: Dict[str, Any]) -> Tuple[List[str], Optional[Command], List[Send]]:
        """获取下一个要执行的节点"""
        next_nodes = []
        command = None
        sends = []
        
        # 首先检查条件边
        for conditional_edge in self.conditional_edges:
            if conditional_edge.from_node == current_node:
                nodes, cmd, send_list = conditional_edge.get_next_nodes(state)
                next_nodes.extend(nodes)
                if cmd:
                    command = cmd
                sends.extend(send_list)
        
        # 如果没有条件边匹配，检查普通边
        if not next_nodes and not sends:
            for edge in self.edges:
                if edge.from_node == current_node and edge.can_traverse(state):
                    next_nodes.append(edge.to_node)
        
        return next_nodes, command, sends
    
    def validate(self) -> bool:
        """验证图的有效性"""
        if not self.entry_point:
            raise ValueError("未设置入口点")
        
        # 检查所有引用的节点是否存在
        for edge in self.edges:
            self._validate_nodes_exist(edge.from_node, edge.to_node)
        
        # 检查条件边引用的节点
        for conditional_edge in self.conditional_edges:
            if (conditional_edge.from_node not in self.nodes and 
                conditional_edge.from_node not in ["__start__", "START"]):
                raise ValueError(f"条件边源节点 {conditional_edge.from_node} 不存在")
        
        return True
    
    def compile(self, **kwargs) -> 'CompiledStateGraph[T]':
        """编译图"""
        self.validate()
        self.compiled = True
        return CompiledStateGraph(self, **kwargs)
    
    def _validate_nodes_exist(self, from_node: str, to_node: str):
        """验证节点存在"""
        if from_node not in self.nodes and from_node not in ["__start__", "START"]:
            raise ValueError(f"源节点 {from_node} 不存在")
        if to_node not in self.nodes and to_node not in ["__end__", "END"]:
            raise ValueError(f"目标节点 {to_node} 不存在")
    
    def visualize(self) -> str:
        """生成Mermaid图可视化"""
        lines = ["graph TD"]
        
        # 添加节点
        for node_name in self.nodes:
            lines.append(f'    {node_name}["{node_name}"]')
        
        # 添加普通边
        for edge in self.edges:
            lines.append(f"    {edge.from_node} --> {edge.to_node}")
        
        # 添加条件边
        for conditional_edge in self.conditional_edges:
            lines.append(f"    {conditional_edge.from_node} -->|condition| ?")
        
        return "\n".join(lines)


class CompiledStateGraph(Generic[T]):
    """编译后的状态图"""
    
    def __init__(self, graph: StateGraph[T], **kwargs):
        self.graph = graph
        self.config = kwargs
        
    async def invoke(self, 
                    initial_state: Optional[Dict[str, Any]] = None,
                    config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """调用图执行"""
        from .executor import StateGraphExecutor
        
        executor = StateGraphExecutor()
        return await executor.execute(
            self.graph, 
            initial_state or {},
            config or {}
        )
    
    async def stream(self,
                    initial_state: Optional[Dict[str, Any]] = None,
                    config: Optional[Dict[str, Any]] = None):
        """流式执行图"""
        from .executor import StateGraphExecutor
        
        executor = StateGraphExecutor()
        async for result in executor.stream_execute(
            self.graph,
            initial_state or {},
            config or {}
        ):
            yield result


class GraphBuilder:
    """图构建器 - 基于StateGraph的流式API"""
    
    def __init__(self, name: str, state_schema: Optional[type] = None):
        self.graph = StateGraph(state_schema, name)
        
    def add_node(self, node: BaseNode) -> "GraphBuilder":
        """添加节点"""
        self.graph.add_node(node.name, node)
        return self
        
    def connect(self,
               from_node: str,
               to_node: str,
               **kwargs) -> "GraphBuilder":
        """连接节点"""
        condition = kwargs.get('condition')
        
        if condition:
            # 将字符串条件转换为路由函数
            def route_func(state: Dict[str, Any]) -> str:
                try:
                    # 简单的条件评估
                    context = {"output": state, "metadata": state.get("metadata", {})}
                    if eval(condition, {"__builtins__": {}}, context):
                        return to_node
                    return "END"
                except:
                    return "END"
            
            self.graph.add_conditional_edges(from_node, route_func)
        else:
            self.graph.add_edge(from_node, to_node)
        return self
        
    def entry(self, node_name: str) -> "GraphBuilder":
        """设置入口"""
        self.graph.set_entry_point(node_name)
        return self
        
    def exit(self, node_name: str) -> "GraphBuilder":
        """添加出口（通过条件边END实现）"""
        # StateGraph通过条件边的END返回实现出口
        return self
        
    def build(self) -> StateGraph:
        """构建StateGraph"""
        return self.graph


class StateGraphExecutor(BaseExecutor):
    """状态图执行器 - 基于LangGraph设计理念"""
    
    def __init__(self, max_iterations: int = 100):
        self.max_iterations = max_iterations
        
    async def execute(self, 
                     graph: StateGraph, 
                     initial_state: Dict[str, Any],
                     config: Dict[str, Any]) -> Dict[str, Any]:
        """执行状态图"""
        from .executor import StateManager, add_reducer
        
        # 设置默认状态合并器
        state_manager = StateManager({
            "messages": add_reducer,  # 消息列表使用追加合并
        })
        
        # 初始化状态
        current_state = initial_state.copy()
        
        # 执行统计
        iteration = 0
        current_nodes = [graph.entry_point] if graph.entry_point else []
        visited_nodes = []
        
        print(f"[StateGraphExecutor] 开始执行图: {graph.name}")
        print(f"[StateGraphExecutor] 入口节点: {graph.entry_point}")
        print(f"[StateGraphExecutor] 初始状态: {current_state}")
        
        while current_nodes and iteration < self.max_iterations:
            iteration += 1
            print(f"\n[StateGraphExecutor] === 迭代 {iteration} ===")
            print(f"[StateGraphExecutor] 当前节点: {current_nodes}")
            
            # 并行执行当前层的所有节点
            node_results = []
            for node_name in current_nodes:
                if node_name in graph.nodes:
                    node = graph.nodes[node_name]
                    print(f"[StateGraphExecutor] 执行节点: {node_name}")
                    
                    try:
                        # 执行节点
                        result = await node.run(current_state)
                        node_results.append(result)
                        visited_nodes.append(node_name)
                        
                        print(f"[StateGraphExecutor] 节点 {node_name} 执行完成")
                        print(f"[StateGraphExecutor] 状态更新: {result.state_update}")
                        
                        # 合并状态更新
                        if result.is_success and result.state_update:
                            current_state = state_manager.merge_state(
                                current_state, 
                                result.state_update
                            )
                        
                    except Exception as e:
                        print(f"[StateGraphExecutor] 节点 {node_name} 执行失败: {e}")
                        # 继续执行其他节点
                        continue
            
            # 确定下一步执行的节点
            next_nodes = []
            commands = []
            sends = []
            
            for i, node_name in enumerate(current_nodes):
                if i < len(node_results) and node_results[i].is_success:
                    # 检查是否有Command返回
                    if "command" in node_results[i].metadata:
                        command = node_results[i].metadata["command"]
                        if isinstance(command, Command):
                            commands.append(command)
                            if command.goto:
                                if isinstance(command.goto, str):
                                    next_nodes.append(command.goto)
                                elif isinstance(command.goto, list):
                                    next_nodes.extend(command.goto)
                            continue
                    
                    # 使用图的路由逻辑
                    nodes, command, send_list = graph.get_next_nodes(node_name, current_state)
                    next_nodes.extend(nodes)
                    if command:
                        commands.append(command)
                    sends.extend(send_list)
            
            # 处理Command状态更新
            for command in commands:
                if command.update:
                    current_state = state_manager.merge_state(
                        current_state, 
                        command.update
                    )
            
            # 处理Send对象（动态节点创建）
            for send in sends:
                # Send对象创建新的执行分支，这里简化处理
                if send.node in graph.nodes:
                    # 将Send的状态合并到当前状态
                    current_state = state_manager.merge_state(current_state, send.state)
                    next_nodes.append(send.node)
            
            # 过滤有效的下一个节点
            current_nodes = [node for node in next_nodes if node in graph.nodes]
            
            # 去重
            current_nodes = list(set(current_nodes))
            
            print(f"[StateGraphExecutor] 下一轮节点: {current_nodes}")
            print(f"[StateGraphExecutor] 当前状态: {current_state}")
            
            # 如果没有下一个节点，结束执行
            if not current_nodes:
                print(f"[StateGraphExecutor] 没有更多节点，执行结束")
                break
        
        if iteration >= self.max_iterations:
            print(f"[StateGraphExecutor] 达到最大迭代次数限制: {self.max_iterations}")
        
        print(f"\n[StateGraphExecutor] 执行完成")
        print(f"[StateGraphExecutor] 总迭代次数: {iteration}")
        print(f"[StateGraphExecutor] 访问的节点: {visited_nodes}")
        print(f"[StateGraphExecutor] 最终状态: {current_state}")
        
        return current_state
    
    async def stream_execute(self,
                           graph: StateGraph,
                           initial_state: Dict[str, Any], 
                           config: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """流式执行状态图"""
        # 简化实现，实际使用时可以参考execute方法实现流式版本
        result = await self.execute(graph, initial_state, config)
        yield {"type": "final", "state": result} 