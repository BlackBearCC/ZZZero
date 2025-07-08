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
    fallback_node: Optional[str] = None  # 失败时的回退节点
    retry_count: int = 0  # 重试次数
    max_retries: int = 3  # 最大重试次数
    
    def get_next_nodes(self, state: Dict[str, Any]) -> Tuple[List[str], Optional[Command], List[Send]]:
        """获取下一个节点列表"""
        for attempt in range(self.max_retries + 1):
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
                    return self._get_fallback_route()
                    
            except Exception as e:
                print(f"条件边路由失败 (尝试 {attempt + 1}/{self.max_retries + 1}): {e}")
                if attempt < self.max_retries:
                    continue
                else:
                    # 所有重试都失败，使用回退路由
                    return self._get_fallback_route()
        
        return self._get_fallback_route()
    
    def _get_fallback_route(self) -> Tuple[List[str], Optional[Command], List[Send]]:
        """获取失败时的回退路由"""
        if self.fallback_node:
            return [self.fallback_node], None, []
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
        self.error_handlers: Dict[str, Callable] = {}  # 错误处理器
        self.retry_policies: Dict[str, Dict[str, Any]] = {}  # 重试策略
        
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
    
    def add_error_handler(self, node_name: str, handler: Callable) -> 'StateGraph[T]':
        """添加错误处理器"""
        self.error_handlers[node_name] = handler
        return self
    
    def add_retry_policy(self, node_name: str, max_retries: int = 3, 
                        retry_delay: float = 1.0, exponential_backoff: bool = True) -> 'StateGraph[T]':
        """添加重试策略"""
        self.retry_policies[node_name] = {
            "max_retries": max_retries,
            "retry_delay": retry_delay,
            "exponential_backoff": exponential_backoff
        }
        return self
    
    def compile(self, **kwargs) -> 'CompiledStateGraph[T]':
        """编译图"""
        self.validate()
        self._optimize_graph()
        self.compiled = True
        return CompiledStateGraph(self, **kwargs)
    
    def _optimize_graph(self):
        """优化图结构"""
        print(f"[StateGraph] 开始优化图: {self.name}")
        
        # 1. 拓扑排序验证
        if not self._validate_topology():
            raise ValueError("图存在循环依赖")
        
        # 2. 死锁检测
        if self._detect_deadlocks():
            raise ValueError("检测到潜在的死锁")
        
        # 3. 优化并行执行机会
        self._optimize_parallel_execution()
        
        print(f"[StateGraph] 图优化完成")
    
    def _validate_topology(self) -> bool:
        """验证图的拓扑结构"""
        try:
            # 使用 NetworkX 进行拓扑排序
            G = nx.DiGraph()
            
            # 添加节点
            for node_name in self.nodes:
                G.add_node(node_name)
            
            # 添加边
            for edge in self.edges:
                G.add_edge(edge.from_node, edge.to_node)
            
            # 添加条件边
            for cond_edge in self.conditional_edges:
                # 为条件边创建虚拟连接
                G.add_edge(cond_edge.from_node, f"cond_{cond_edge.from_node}")
            
            # 检查是否有环
            if nx.is_directed_acyclic_graph(G):
                # 计算拓扑排序
                topo_order = list(nx.topological_sort(G))
                print(f"[StateGraph] 拓扑排序: {topo_order}")
                return True
            else:
                print(f"[StateGraph] 检测到循环依赖")
                return False
                
        except Exception as e:
            print(f"[StateGraph] 拓扑验证失败: {e}")
            return False
    
    def _detect_deadlocks(self) -> bool:
        """检测潜在的死锁"""
        # 简单的死锁检测：检查是否有节点没有出边且不是终止节点
        for node_name in self.nodes:
            has_outgoing = False
            
            # 检查普通边
            for edge in self.edges:
                if edge.from_node == node_name:
                    has_outgoing = True
                    break
            
            # 检查条件边
            if not has_outgoing:
                for cond_edge in self.conditional_edges:
                    if cond_edge.from_node == node_name:
                        has_outgoing = True
                        break
            
            # 如果没有出边且不是明确的终止节点，可能存在死锁
            if not has_outgoing and node_name != "__end__":
                print(f"[StateGraph] 潜在死锁节点: {node_name}")
                # 这里可以选择是否认为这是死锁
                # 对于某些应用，终止节点是合理的
        
        return False  # 暂时不认为是死锁
    
    def _optimize_parallel_execution(self):
        """优化并行执行机会"""
        # 分析哪些节点可以并行执行
        parallel_groups = self._identify_parallel_groups()
        print(f"[StateGraph] 识别到并行组: {parallel_groups}")
    
    def _identify_parallel_groups(self) -> List[List[str]]:
        """识别可以并行执行的节点组"""
        # 简单实现：如果多个节点没有相互依赖，可以并行执行
        groups = []
        
        # 构建依赖图
        dependencies = {}
        for node_name in self.nodes:
            dependencies[node_name] = set()
        
        # 添加边依赖
        for edge in self.edges:
            if edge.to_node in dependencies:
                dependencies[edge.to_node].add(edge.from_node)
        
        # 查找没有相互依赖的节点
        independent_nodes = []
        for node_name in self.nodes:
            if len(dependencies[node_name]) == 0:
                independent_nodes.append(node_name)
        
        if len(independent_nodes) > 1:
            groups.append(independent_nodes)
        
        return groups
    
    def _validate_nodes_exist(self, from_node: str, to_node: str):
        """验证节点存在"""
        if from_node not in self.nodes and from_node not in ["__start__", "START"]:
            raise ValueError(f"源节点 {from_node} 不存在")
        if to_node not in self.nodes and to_node not in ["__end__", "END"]:
            raise ValueError(f"目标节点 {to_node} 不存在")
    
    def visualize(self, format: str = "mermaid", include_metadata: bool = True) -> str:
        """生成图可视化"""
        if format == "mermaid":
            return self._generate_mermaid_diagram(include_metadata)
        elif format == "graphviz":
            return self._generate_graphviz_diagram(include_metadata)
        else:
            raise ValueError(f"不支持的可视化格式: {format}")
    
    def _generate_mermaid_diagram(self, include_metadata: bool = True) -> str:
        """生成Mermaid图"""
        lines = ["graph TD"]
        
        # 添加节点
        for node_name, node in self.nodes.items():
            node_label = node_name
            if include_metadata:
                node_type = getattr(node, 'node_type', 'unknown')
                node_label = f"{node_name}\\n({node_type})"
            
            lines.append(f'    {node_name}["{node_label}"]')
        
        # 添加普通边
        for edge in self.edges:
            lines.append(f"    {edge.from_node} --> {edge.to_node}")
        
        # 添加条件边
        for conditional_edge in self.conditional_edges:
            lines.append(f"    {conditional_edge.from_node} -->|condition| {conditional_edge.from_node}_cond{{条件判断}}")
        
        # 添加入口点标记
        if self.entry_point:
            lines.append(f"    START((开始)) --> {self.entry_point}")
        
        return "\n".join(lines)
    
    def _generate_graphviz_diagram(self, include_metadata: bool = True) -> str:
        """生成Graphviz图"""
        lines = ["digraph StateGraph {", "  rankdir=TB;"]
        
        # 添加节点
        for node_name, node in self.nodes.items():
            node_label = node_name
            if include_metadata:
                node_type = getattr(node, 'node_type', 'unknown')
                node_label = f"{node_name}\\n({node_type})"
            
            lines.append(f'  {node_name} [label="{node_label}"];')
        
        # 添加普通边
        for edge in self.edges:
            lines.append(f"  {edge.from_node} -> {edge.to_node};")
        
        # 添加条件边
        for conditional_edge in self.conditional_edges:
            lines.append(f'  {conditional_edge.from_node} -> {conditional_edge.from_node}_cond [label="condition"];')
        
        # 添加入口点标记
        if self.entry_point:
            lines.append(f'  START [shape=circle, label="开始"];')
            lines.append(f"  START -> {self.entry_point};")
        
        lines.append("}")
        return "\n".join(lines)
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计信息"""
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "conditional_edge_count": len(self.conditional_edges),
            "entry_point": self.entry_point,
            "compiled": self.compiled,
            "has_error_handlers": len(self.error_handlers) > 0,
            "has_retry_policies": len(self.retry_policies) > 0,
            "nodes": {name: {
                "type": str(getattr(node, 'node_type', 'unknown')),
                "stream_enabled": getattr(node, 'stream', False)
            } for name, node in self.nodes.items()}
        }


class CompiledStateGraph(Generic[T]):
    """编译后的状态图"""
    
    def __init__(self, graph: StateGraph[T], **kwargs):
        self.graph = graph
        self.config = kwargs
        self.executor = StateGraphExecutor(
            max_iterations=kwargs.get("max_iterations", 100),
            enable_parallel=kwargs.get("enable_parallel", True)
        )
        
    async def invoke(self, 
                     initial_state: Optional[Dict[str, Any]] = None,
                     config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """调用图执行"""
        return await self.executor.execute(
            self.graph, 
            initial_state or {},
            config or {}
        )
    
    async def stream(self,
                    initial_state: Optional[Dict[str, Any]] = None,
                    config: Optional[Dict[str, Any]] = None):
        """流式执行图"""
        async for result in self.executor.stream_execute(
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
    """状态图执行器 - 增强版，支持真正并行执行和错误处理"""
    
    def __init__(self, 
                 max_iterations: int = 100, 
                 enable_parallel: bool = True,
                 max_concurrent_nodes: int = 10,
                 enable_error_handling: bool = True,
                 enable_state_locking: bool = True):
        self.max_iterations = max_iterations
        self.enable_parallel = enable_parallel
        self.max_concurrent_nodes = max_concurrent_nodes
        self.enable_error_handling = enable_error_handling
        self.enable_state_locking = enable_state_locking
        
        # 状态同步锁
        self._state_lock = asyncio.Lock() if enable_state_locking else None
        
        # 错误处理器
        if enable_error_handling:
            from .error_handling import global_error_handler
            self.error_handler = global_error_handler
        else:
            self.error_handler = None
        
    async def execute(self, 
                     graph: StateGraph, 
                     initial_state: Dict[str, Any],
                     config: Dict[str, Any]) -> Dict[str, Any]:
        """执行状态图 - 增强版"""
        from .executor import StateManager, add_reducer, CheckpointStorage
        
        # 从配置中获取StateManager设置
        enable_checkpoints = config.get("enable_checkpoints", True)
        enable_versioning = config.get("enable_versioning", True)
        checkpoint_storage = config.get("checkpoint_storage", CheckpointStorage.MEMORY)
        
        # 设置默认状态合并器
        state_manager = StateManager(
            reducers={
                "messages": add_reducer,  # 消息列表使用追加合并
            },
            enable_versioning=enable_versioning,
            enable_checkpoints=enable_checkpoints,
            checkpoint_storage=checkpoint_storage
        )
        
        # 初始化状态
        current_state = initial_state.copy()
        
        # 执行统计
        iteration = 0
        current_nodes = [graph.entry_point] if graph.entry_point else []
        visited_nodes = []
        execution_start_time = datetime.now()
        
        print(f"[StateGraphExecutor] 开始执行图: {graph.name}")
        print(f"[StateGraphExecutor] 入口节点: {graph.entry_point}")
        print(f"[StateGraphExecutor] 并行执行: {self.enable_parallel}")
        print(f"[StateGraphExecutor] 错误处理: {self.enable_error_handling}")
        print(f"[StateGraphExecutor] 初始状态: {list(current_state.keys())}")
        
        try:
            while current_nodes and iteration < self.max_iterations:
                iteration += 1
                iteration_start_time = datetime.now()
                print(f"\n[StateGraphExecutor] === 迭代 {iteration} ===")
                print(f"[StateGraphExecutor] 当前节点: {current_nodes}")
                
                # 创建迭代检查点
                if enable_checkpoints:
                    checkpoint_id = state_manager.create_checkpoint(
                        current_state, 
                        f"iteration_{iteration}",
                        {"iteration": iteration, "nodes": current_nodes}
                    )
                    print(f"[StateGraphExecutor] 创建检查点: {checkpoint_id}")
                
                # 执行节点
                node_results = await self._execute_nodes_batch(
                    graph, current_nodes, current_state, state_manager, iteration
                )
                
                # 记录访问的节点
                for result in node_results:
                    if result and result.is_success:
                        visited_nodes.append(result.node_name)
                
                # 合并状态更新（线程安全）
                current_state = await self._merge_node_results(
                    current_state, node_results, state_manager
                )
                
                # 确定下一步执行的节点
                next_nodes, should_continue = await self._determine_next_nodes(
                    graph, current_nodes, node_results, current_state
                )
                
                current_nodes = next_nodes
                
                iteration_duration = (datetime.now() - iteration_start_time).total_seconds()
                print(f"[StateGraphExecutor] 迭代 {iteration} 完成，耗时: {iteration_duration:.2f}s")
                print(f"[StateGraphExecutor] 下一轮节点: {current_nodes}")
                
                if not should_continue:
                    print(f"[StateGraphExecutor] 收到终止信号，提前结束执行")
                    break
                
                # 如果没有下一个节点，结束执行
                if not current_nodes:
                    print(f"[StateGraphExecutor] 没有更多节点，执行结束")
                    break
            
            if iteration >= self.max_iterations:
                print(f"[StateGraphExecutor] 达到最大迭代次数限制: {self.max_iterations}")
            
        except Exception as e:
            print(f"[StateGraphExecutor] 执行过程中发生严重错误: {e}")
            # 如果启用了检查点，可以考虑回滚
            if enable_checkpoints:
                checkpoints = state_manager.list_checkpoints(limit=1)
                if checkpoints:
                    print(f"[StateGraphExecutor] 尝试回滚到最近的检查点")
                    rollback_state = state_manager.restore_checkpoint(checkpoints[0].id)
                    if rollback_state:
                        current_state = rollback_state
            raise e
        
        execution_duration = (datetime.now() - execution_start_time).total_seconds()
        print(f"\n[StateGraphExecutor] 执行完成")
        print(f"[StateGraphExecutor] 总迭代次数: {iteration}")
        print(f"[StateGraphExecutor] 访问的节点: {visited_nodes}")
        print(f"[StateGraphExecutor] 总耗时: {execution_duration:.2f}s")
        print(f"[StateGraphExecutor] 最终状态键: {list(current_state.keys())}")
        
        # 添加执行元数据
        current_state["_execution_metadata"] = {
            "total_iterations": iteration,
            "visited_nodes": visited_nodes,
            "execution_time": execution_duration,
            "graph_name": graph.name
        }
        
        return current_state
    
    async def _execute_nodes_batch(self,
                                  graph: StateGraph,
                                  node_names: List[str],
                                  current_state: Dict[str, Any],
                                  state_manager,
                                  iteration: int) -> List[Optional[NodeResult]]:
        """批量执行节点"""
        if not node_names:
            return []
        
        # 控制并发数量
        concurrent_nodes = min(len(node_names), self.max_concurrent_nodes)
        
        if self.enable_parallel and len(node_names) > 1:
            print(f"[StateGraphExecutor] 并行执行 {len(node_names)} 个节点，最大并发: {concurrent_nodes}")
            return await self._execute_nodes_parallel(graph, node_names, current_state, iteration)
        else:
            print(f"[StateGraphExecutor] 串行执行 {len(node_names)} 个节点")
            return await self._execute_nodes_sequential(graph, node_names, current_state, iteration)
    
    async def _execute_nodes_parallel(self,
                                     graph: StateGraph,
                                     node_names: List[str],
                                     current_state: Dict[str, Any],
                                     iteration: int) -> List[Optional[NodeResult]]:
        """并行执行节点"""
        semaphore = asyncio.Semaphore(self.max_concurrent_nodes)
        
        async def execute_single_node(node_name: str) -> Optional[NodeResult]:
            async with semaphore:
                if node_name not in graph.nodes:
                    print(f"[StateGraphExecutor] 节点 {node_name} 不存在")
                    return None
                
                node = graph.nodes[node_name]
                print(f"[StateGraphExecutor] 开始并行执行节点: {node_name}")
                
                try:
                    if self.error_handler:
                        result = await self.error_handler.execute_with_retry(
                            func=node.run,
                            node_name=node_name,
                            state=current_state
                        )
                        # 包装为NodeResult
                        if hasattr(result, 'node_name'):
                            return result
                        else:
                            # 如果不是NodeResult，创建一个
                            from .base import NodeResult, ExecutionState
                            return NodeResult(
                                node_name=node_name,
                                node_type=getattr(node, 'node_type', None),
                                state_update=result if isinstance(result, dict) else {},
                                execution_state=ExecutionState.SUCCESS,
                                end_time=datetime.now()
                            )
                    else:
                        return await node.run(current_state)
                
                except Exception as e:
                    print(f"[StateGraphExecutor] 并行节点 {node_name} 执行失败: {e}")
                    # 返回失败的NodeResult
                    from .base import NodeResult, ExecutionState
                    return NodeResult(
                        node_name=node_name,
                        node_type=getattr(node, 'node_type', None),
                        state_update={},
                        execution_state=ExecutionState.FAILED,
                        error=str(e),
                        end_time=datetime.now()
                    )
        
        # 创建并发任务
        tasks = [execute_single_node(node_name) for node_name in node_names]
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"[StateGraphExecutor] 节点 {node_names[i]} 任务异常: {result}")
                from .base import NodeResult, ExecutionState
                final_results.append(NodeResult(
                    node_name=node_names[i],
                    node_type=None,
                    state_update={},
                    execution_state=ExecutionState.FAILED,
                    error=str(result),
                    end_time=datetime.now()
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    async def _execute_nodes_sequential(self,
                                       graph: StateGraph,
                                       node_names: List[str],
                                       current_state: Dict[str, Any],
                                       iteration: int) -> List[Optional[NodeResult]]:
        """串行执行节点"""
        results = []
        
        for node_name in node_names:
            if node_name not in graph.nodes:
                print(f"[StateGraphExecutor] 节点 {node_name} 不存在")
                results.append(None)
                continue
            
            node = graph.nodes[node_name]
            print(f"[StateGraphExecutor] 开始串行执行节点: {node_name}")
            
            try:
                if self.error_handler:
                    result = await self.error_handler.execute_with_retry(
                        func=node.run,
                        node_name=node_name,
                        state=current_state
                    )
                    results.append(result)
                else:
                    result = await node.run(current_state)
                    results.append(result)
                
                print(f"[StateGraphExecutor] 串行节点 {node_name} 执行完成")
                
            except Exception as e:
                print(f"[StateGraphExecutor] 串行节点 {node_name} 执行失败: {e}")
                from .base import NodeResult, ExecutionState
                results.append(NodeResult(
                    node_name=node_name,
                    node_type=getattr(node, 'node_type', None),
                    state_update={},
                    execution_state=ExecutionState.FAILED,
                    error=str(e),
                    end_time=datetime.now()
                ))
        
        return results
    
    async def _merge_node_results(self,
                                 current_state: Dict[str, Any],
                                 node_results: List[Optional[NodeResult]],
                                 state_manager) -> Dict[str, Any]:
        """合并节点执行结果到状态"""
        if self._state_lock:
            async with self._state_lock:
                return self._do_merge_node_results(current_state, node_results, state_manager)
        else:
            return self._do_merge_node_results(current_state, node_results, state_manager)
    
    def _do_merge_node_results(self,
                              current_state: Dict[str, Any],
                              node_results: List[Optional[NodeResult]],
                              state_manager) -> Dict[str, Any]:
        """实际执行状态合并"""
        result_state = current_state.copy()
        
        for node_result in node_results:
            if node_result and node_result.is_success and node_result.state_update:
                try:
                    result_state = state_manager.merge_state(
                        result_state, 
                        node_result.state_update,
                        node_result.node_name
                    )
                    print(f"[StateGraphExecutor] 合并节点 {node_result.node_name} 的状态更新")
                except Exception as e:
                    print(f"[StateGraphExecutor] 合并节点 {node_result.node_name} 状态失败: {e}")
        
        return result_state
    
    async def _determine_next_nodes(self,
                                   graph: StateGraph,
                                   current_nodes: List[str],
                                   node_results: List[Optional[NodeResult]],
                                   current_state: Dict[str, Any]) -> Tuple[List[str], bool]:
        """确定下一步执行的节点"""
        next_nodes = []
        commands = []
        sends = []
        should_continue = True
        
        # 处理每个节点的结果
        for i, node_name in enumerate(current_nodes):
            if i < len(node_results) and node_results[i] and node_results[i].is_success:
                node_result = node_results[i]
                
                # 检查是否有Command返回
                if "command" in node_result.metadata:
                    command = node_result.metadata["command"]
                    if isinstance(command, Command):
                        commands.append(command)
                        print(f"[StateGraphExecutor] 节点 {node_name} 返回Command: {command}")
                        
                        if command.goto:
                            if isinstance(command.goto, str):
                                if command.goto not in ["__end__", "END"]:
                                    next_nodes.append(command.goto)
                                else:
                                    should_continue = False
                            elif isinstance(command.goto, list):
                                for target in command.goto:
                                    if target not in ["__end__", "END"]:
                                        next_nodes.append(target)
                                    else:
                                        should_continue = False
                        continue
                
                # 使用图的路由逻辑
                nodes, command, send_list = graph.get_next_nodes(node_name, current_state)
                next_nodes.extend(nodes)
                if command:
                    commands.append(command)
                sends.extend(send_list)
        
        # 处理Send对象（动态节点创建）
        for send in sends:
            if send.node in graph.nodes:
                next_nodes.append(send.node)
        
        # 过滤有效的下一个节点并去重
        valid_next_nodes = [node for node in next_nodes if node in graph.nodes]
        unique_next_nodes = list(set(valid_next_nodes))
        
        return unique_next_nodes, should_continue
    
    
    async def stream_execute(self,
                           graph: StateGraph,
                           initial_state: Dict[str, Any], 
                           config: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """流式执行状态图 - 真实实现"""
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
        
        print(f"[StreamExecutor] 开始流式执行图: {graph.name}")
        yield {"type": "start", "message": f"开始执行工作流: {graph.name}", "state": current_state}
        
        while current_nodes and iteration < self.max_iterations:
            iteration += 1
            print(f"\n[StreamExecutor] === 迭代 {iteration} ===")
            print(f"[StreamExecutor] 当前节点: {current_nodes}")
            
            # 逐个执行节点（流式） - 改为串行执行，确保状态正确传递
            node_results = {}  # 存储本轮所有节点的执行结果
            
            for node_name in current_nodes:
                if node_name in graph.nodes:
                    node = graph.nodes[node_name]
                    print(f"[StreamExecutor] 开始执行节点: {node_name}")
                    
                    # 发送节点开始信号
                    yield {
                        "type": "node_start", 
                        "node": node_name, 
                        "state": current_state,
                        "iteration": iteration
                    }
                    
                    try:
                        # 检查节点是否支持流式执行
                        if hasattr(node, 'stream') and node.stream:
                            # 流式执行节点
                            final_result = None
                            async for intermediate_result in node.run_stream(current_state):
                                final_result = intermediate_result
                                
                                # 发送中间结果信号
                                yield {
                                    "type": "node_streaming",
                                    "node": node_name,
                                    "intermediate_result": intermediate_result,
                                    "state": current_state
                                }
                                
                                # 注意：不在这里合并中间状态，避免状态污染
                                # 只有最终结果才合并到状态中
                            
                            result = final_result
                        else:
                            # 非流式执行节点
                            result = await node.run(current_state)
                        
                        node_results[node_name] = result
                        visited_nodes.append(node_name)
                        
                        print(f"[StreamExecutor] 节点 {node_name} 执行完成")
                        
                        # 发送节点完成信号
                        yield {
                            "type": "node_complete", 
                            "node": node_name, 
                            "result": result,
                            "state": current_state
                        }
                        
                        # 立即合并状态更新，确保后续节点能获取到更新
                        if result and result.is_success and result.state_update:
                            print(f"[StreamExecutor] 合并节点 {node_name} 的状态更新: {list(result.state_update.keys())}")
                            current_state = state_manager.merge_state(
                                current_state, 
                                result.state_update
                            )
                            
                            # 发送状态更新信号
                            yield {
                                "type": "state_update",
                                "node": node_name,
                                "update": result.state_update,
                                "new_state": current_state
                            }
                        
                    except Exception as e:
                        print(f"[StreamExecutor] 节点 {node_name} 执行失败: {e}")
                        
                        # 发送错误信号
                        yield {
                            "type": "node_error",
                            "node": node_name,
                            "error": str(e),
                            "state": current_state
                        }
                        # 继续执行其他节点
                        continue
            
            # 确定下一步执行的节点
            next_nodes = []
            commands = []
            sends = []
            
            for node_name in current_nodes:
                # 使用图的路由逻辑，基于最新的状态
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
                if send.node in graph.nodes:
                    current_state = state_manager.merge_state(current_state, send.state)
                    next_nodes.append(send.node)
            
            # 过滤有效的下一个节点
            current_nodes = [node for node in next_nodes if node in graph.nodes]
            current_nodes = list(set(current_nodes))  # 去重
            
            print(f"[StreamExecutor] 下一轮节点: {current_nodes}")
            
            # 发送迭代完成信号
            yield {
                "type": "iteration_complete",
                "iteration": iteration,
                "next_nodes": current_nodes,
                "state": current_state
            }
            
            # 如果没有下一个节点，结束执行
            if not current_nodes:
                print(f"[StreamExecutor] 没有更多节点，执行结束")
                break
        
        # 发送最终完成信号
        yield {
            "type": "final", 
            "state": current_state,
            "visited_nodes": visited_nodes,
            "iterations": iteration
        } 