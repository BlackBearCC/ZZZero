"""
图编译器模块 - 实现图编译优化和验证
"""
import asyncio
import networkx as nx
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from .graph import StateGraph, Command, Send
from .error_handling import ErrorHandler, RetryPolicy, CircuitBreakerConfig

logger = logging.getLogger(__name__)

class OptimizationLevel(Enum):
    """优化级别"""
    NONE = "none"
    BASIC = "basic"
    AGGRESSIVE = "aggressive"

@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

@dataclass
class CompilationResult:
    """编译结果"""
    optimized_graph: Optional[StateGraph]
    validation_result: ValidationResult
    optimization_report: Dict[str, Any] = field(default_factory=dict)
    compilation_time: float = 0.0

@dataclass
class NodeDependency:
    """节点依赖关系"""
    node_name: str
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    depth: int = 0
    can_parallel: bool = True

class GraphCompiler:
    """图编译器 - 实现图优化和验证"""
    
    def __init__(self, 
                 optimization_level: OptimizationLevel = OptimizationLevel.BASIC,
                 enable_validation: bool = True,
                 enable_optimization: bool = True):
        self.optimization_level = optimization_level
        self.enable_validation = enable_validation
        self.enable_optimization = enable_optimization
        
        # 编译缓存
        self._compilation_cache: Dict[str, CompilationResult] = {}
        
    def compile(self, graph: StateGraph, force_recompile: bool = False) -> CompilationResult:
        """编译图"""
        start_time = datetime.now()
        
        # 检查缓存
        cache_key = self._generate_cache_key(graph)
        if not force_recompile and cache_key in self._compilation_cache:
            logger.info(f"使用缓存的编译结果: {graph.name}")
            return self._compilation_cache[cache_key]
        
        logger.info(f"开始编译图: {graph.name}")
        
        # 验证图
        validation_result = self.validate_graph(graph) if self.enable_validation else ValidationResult(True)
        
        if not validation_result.is_valid:
            logger.error(f"图验证失败: {validation_result.errors}")
            return CompilationResult(
                optimized_graph=None,
                validation_result=validation_result,
                compilation_time=(datetime.now() - start_time).total_seconds()
            )
        
        # 优化图
        optimized_graph = graph
        optimization_report = {}
        
        if self.enable_optimization and validation_result.is_valid:
            optimized_graph, optimization_report = self._optimize_graph(graph)
        
        compilation_time = (datetime.now() - start_time).total_seconds()
        
        result = CompilationResult(
            optimized_graph=optimized_graph,
            validation_result=validation_result,
            optimization_report=optimization_report,
            compilation_time=compilation_time
        )
        
        # 缓存结果
        self._compilation_cache[cache_key] = result
        
        logger.info(f"图编译完成，耗时: {compilation_time:.3f}s")
        return result
    
    def validate_graph(self, graph: StateGraph) -> ValidationResult:
        """验证图的有效性"""
        errors = []
        warnings = []
        suggestions = []
        
        try:
            # 基本验证
            if not graph.entry_point:
                errors.append("图没有设置入口点")
            
            if not graph.nodes:
                errors.append("图没有任何节点")
            
            # 验证入口点存在
            if graph.entry_point and graph.entry_point not in graph.nodes:
                errors.append(f"入口点 '{graph.entry_point}' 不存在于节点中")
            
            # 验证边的有效性
            for edge in graph.edges:
                if edge.from_node not in graph.nodes and edge.from_node not in ["__start__", "START"]:
                    errors.append(f"边的源节点 '{edge.from_node}' 不存在")
                if edge.to_node not in graph.nodes and edge.to_node not in ["__end__", "END"]:
                    errors.append(f"边的目标节点 '{edge.to_node}' 不存在")
            
            # 检查条件边
            for cond_edge in graph.conditional_edges:
                if (cond_edge.from_node not in graph.nodes and 
                    cond_edge.from_node not in ["__start__", "START"]):
                    errors.append(f"条件边的源节点 '{cond_edge.from_node}' 不存在")
            
            # 拓扑验证
            topology_result = self._validate_topology(graph)
            errors.extend(topology_result.get("errors", []))
            warnings.extend(topology_result.get("warnings", []))
            suggestions.extend(topology_result.get("suggestions", []))
            
            # 死锁检测
            deadlocks = self._detect_deadlocks(graph)
            if deadlocks:
                errors.extend([f"检测到死锁: {deadlock}" for deadlock in deadlocks])
            
            # 可达性验证
            unreachable_nodes = self._find_unreachable_nodes(graph)
            if unreachable_nodes:
                warnings.extend([f"节点 '{node}' 不可达" for node in unreachable_nodes])
            
            # 性能建议
            perf_suggestions = self._analyze_performance(graph)
            suggestions.extend(perf_suggestions)
            
        except Exception as e:
            errors.append(f"验证过程中发生异常: {str(e)}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    def _validate_topology(self, graph: StateGraph) -> Dict[str, List[str]]:
        """验证图的拓扑结构"""
        errors = []
        warnings = []
        suggestions = []
        
        try:
            # 构建NetworkX图
            nx_graph = self._build_networkx_graph(graph)
            
            # 检查是否为DAG (有向无环图)
            if not nx.is_directed_acyclic_graph(nx_graph):
                cycles = list(nx.simple_cycles(nx_graph))
                for cycle in cycles:
                    errors.append(f"检测到循环: {' -> '.join(cycle)}")
            
            # 检查连通性
            if not nx.is_weakly_connected(nx_graph):
                components = list(nx.weakly_connected_components(nx_graph))
                if len(components) > 1:
                    warnings.append(f"图有 {len(components)} 个弱连通分量")
            
            # 分析复杂度
            complexity = self._calculate_complexity(nx_graph)
            if complexity > 10:
                suggestions.append(f"图复杂度较高 ({complexity})，考虑简化")
            
        except Exception as e:
            errors.append(f"拓扑验证异常: {str(e)}")
        
        return {
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions
        }
    
    def _detect_deadlocks(self, graph: StateGraph) -> List[str]:
        """检测潜在的死锁"""
        deadlocks = []
        
        try:
            # 简单的死锁检测：查找可能的循环等待
            dependency_graph = self._build_dependency_graph(graph)
            
            for node_name, deps in dependency_graph.items():
                # 检查是否存在相互依赖
                for dep in deps.dependencies:
                    if dep in dependency_graph:
                        if node_name in dependency_graph[dep].dependencies:
                            deadlocks.append(f"{node_name} <-> {dep}")
            
        except Exception as e:
            logger.error(f"死锁检测异常: {e}")
        
        return deadlocks
    
    def _find_unreachable_nodes(self, graph: StateGraph) -> List[str]:
        """查找不可达的节点"""
        if not graph.entry_point:
            return list(graph.nodes.keys())
        
        reachable = set()
        to_visit = [graph.entry_point]
        
        while to_visit:
            current = to_visit.pop()
            if current in reachable:
                continue
            
            reachable.add(current)
            
            # 添加直接连接的节点
            for edge in graph.edges:
                if edge.from_node == current and edge.to_node not in reachable:
                    to_visit.append(edge.to_node)
            
            # 添加条件边连接的节点（简化处理）
            for cond_edge in graph.conditional_edges:
                if cond_edge.from_node == current:
                    # 这里简化处理，假设条件边可能到达的所有节点
                    # 实际应该根据路由映射来确定
                    if hasattr(cond_edge, 'route_map') and cond_edge.route_map:
                        for target in cond_edge.route_map.values():
                            if target and target not in reachable:
                                to_visit.append(target)
        
        all_nodes = set(graph.nodes.keys())
        unreachable = all_nodes - reachable
        
        return list(unreachable)
    
    def _analyze_performance(self, graph: StateGraph) -> List[str]:
        """分析性能并提供建议"""
        suggestions = []
        
        try:
            node_count = len(graph.nodes)
            edge_count = len(graph.edges) + len(graph.conditional_edges)
            
            # 节点数量建议
            if node_count > 50:
                suggestions.append("节点数量较多，考虑将图分解为子图")
            
            # 边数量建议
            if edge_count > node_count * 2:
                suggestions.append("边数量较多，图可能过于复杂")
            
            # 并行化建议
            parallel_opportunities = self._identify_parallel_opportunities(graph)
            if parallel_opportunities:
                suggestions.append(f"识别到 {len(parallel_opportunities)} 个并行化机会")
            
            # 瓶颈分析
            bottlenecks = self._identify_bottlenecks(graph)
            if bottlenecks:
                suggestions.append(f"潜在瓶颈节点: {', '.join(bottlenecks)}")
                
        except Exception as e:
            logger.error(f"性能分析异常: {e}")
        
        return suggestions
    
    def _optimize_graph(self, graph: StateGraph) -> Tuple[StateGraph, Dict[str, Any]]:
        """优化图"""
        optimized_graph = graph  # 创建副本进行优化
        optimization_report = {
            "applied_optimizations": [],
            "performance_improvements": {},
            "original_metrics": self._calculate_graph_metrics(graph),
        }
        
        try:
            if self.optimization_level == OptimizationLevel.NONE:
                return optimized_graph, optimization_report
            
            # 基本优化
            if self.optimization_level in [OptimizationLevel.BASIC, OptimizationLevel.AGGRESSIVE]:
                # 移除冗余边
                optimized_graph = self._remove_redundant_edges(optimized_graph)
                optimization_report["applied_optimizations"].append("remove_redundant_edges")
                
                # 合并串行节点
                optimized_graph = self._merge_sequential_nodes(optimized_graph)
                optimization_report["applied_optimizations"].append("merge_sequential_nodes")
            
            # 激进优化
            if self.optimization_level == OptimizationLevel.AGGRESSIVE:
                # 节点重排序
                optimized_graph = self._reorder_nodes(optimized_graph)
                optimization_report["applied_optimizations"].append("reorder_nodes")
                
                # 并行化优化
                optimized_graph = self._optimize_parallelization(optimized_graph)
                optimization_report["applied_optimizations"].append("optimize_parallelization")
            
            # 计算优化后的指标
            optimization_report["optimized_metrics"] = self._calculate_graph_metrics(optimized_graph)
            optimization_report["performance_improvements"] = self._calculate_improvements(
                optimization_report["original_metrics"],
                optimization_report["optimized_metrics"]
            )
            
        except Exception as e:
            logger.error(f"图优化异常: {e}")
        
        return optimized_graph, optimization_report
    
    def _build_networkx_graph(self, graph: StateGraph) -> nx.DiGraph:
        """构建NetworkX图用于分析"""
        nx_graph = nx.DiGraph()
        
        # 添加节点
        for node_name in graph.nodes:
            nx_graph.add_node(node_name)
        
        # 添加边
        for edge in graph.edges:
            if edge.from_node in graph.nodes and edge.to_node in graph.nodes:
                nx_graph.add_edge(edge.from_node, edge.to_node)
        
        # 添加条件边（简化处理）
        for cond_edge in graph.conditional_edges:
            if cond_edge.from_node in graph.nodes:
                # 添加到所有可能的目标节点
                if hasattr(cond_edge, 'route_map') and cond_edge.route_map:
                    for target in cond_edge.route_map.values():
                        if target and target in graph.nodes:
                            nx_graph.add_edge(cond_edge.from_node, target)
        
        return nx_graph
    
    def _build_dependency_graph(self, graph: StateGraph) -> Dict[str, NodeDependency]:
        """构建节点依赖图"""
        dependencies = {}
        
        # 初始化
        for node_name in graph.nodes:
            dependencies[node_name] = NodeDependency(node_name)
        
        # 分析边依赖
        for edge in graph.edges:
            if edge.from_node in dependencies and edge.to_node in dependencies:
                dependencies[edge.to_node].dependencies.add(edge.from_node)
                dependencies[edge.from_node].dependents.add(edge.to_node)
        
        # 计算深度
        for node_name in dependencies:
            dependencies[node_name].depth = self._calculate_node_depth(
                node_name, dependencies, set()
            )
        
        return dependencies
    
    def _calculate_node_depth(self, 
                             node_name: str, 
                             dependencies: Dict[str, NodeDependency],
                             visited: Set[str]) -> int:
        """计算节点深度"""
        if node_name in visited:
            return 0  # 避免循环
        
        visited.add(node_name)
        
        if not dependencies[node_name].dependencies:
            return 0
        
        max_depth = 0
        for dep in dependencies[node_name].dependencies:
            if dep in dependencies:
                depth = self._calculate_node_depth(dep, dependencies, visited)
                max_depth = max(max_depth, depth + 1)
        
        visited.remove(node_name)
        return max_depth
    
    def _calculate_complexity(self, nx_graph: nx.DiGraph) -> float:
        """计算图复杂度"""
        try:
            node_count = nx_graph.number_of_nodes()
            edge_count = nx_graph.number_of_edges()
            
            if node_count == 0:
                return 0
            
            # 使用边密度作为复杂度指标
            max_edges = node_count * (node_count - 1)
            complexity = (edge_count / max_edges) * node_count if max_edges > 0 else 0
            
            return complexity
        except Exception:
            return 0
    
    def _identify_parallel_opportunities(self, graph: StateGraph) -> List[List[str]]:
        """识别并行化机会"""
        opportunities = []
        
        try:
            dependency_graph = self._build_dependency_graph(graph)
            
            # 按深度分组节点
            depth_groups = {}
            for node_name, dep_info in dependency_graph.items():
                depth = dep_info.depth
                if depth not in depth_groups:
                    depth_groups[depth] = []
                depth_groups[depth].append(node_name)
            
            # 相同深度的节点可以并行执行
            for depth, nodes in depth_groups.items():
                if len(nodes) > 1:
                    opportunities.append(nodes)
        
        except Exception as e:
            logger.error(f"并行化分析异常: {e}")
        
        return opportunities
    
    def _identify_bottlenecks(self, graph: StateGraph) -> List[str]:
        """识别瓶颈节点"""
        bottlenecks = []
        
        try:
            dependency_graph = self._build_dependency_graph(graph)
            
            # 瓶颈判断：依赖很多节点，或被很多节点依赖
            for node_name, dep_info in dependency_graph.items():
                if (len(dep_info.dependencies) > 3 or 
                    len(dep_info.dependents) > 3):
                    bottlenecks.append(node_name)
        
        except Exception as e:
            logger.error(f"瓶颈分析异常: {e}")
        
        return bottlenecks
    
    def _remove_redundant_edges(self, graph: StateGraph) -> StateGraph:
        """移除冗余边"""
        # 这里实现边优化逻辑
        # 暂时返回原图
        return graph
    
    def _merge_sequential_nodes(self, graph: StateGraph) -> StateGraph:
        """合并串行节点"""
        # 这里实现节点合并逻辑
        # 暂时返回原图
        return graph
    
    def _reorder_nodes(self, graph: StateGraph) -> StateGraph:
        """重新排序节点"""
        # 这里实现节点重排序逻辑
        # 暂时返回原图
        return graph
    
    def _optimize_parallelization(self, graph: StateGraph) -> StateGraph:
        """优化并行化"""
        # 这里实现并行化优化逻辑
        # 暂时返回原图
        return graph
    
    def _calculate_graph_metrics(self, graph: StateGraph) -> Dict[str, Any]:
        """计算图指标"""
        return {
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges) + len(graph.conditional_edges),
            "complexity": self._calculate_complexity(self._build_networkx_graph(graph)),
            "max_depth": max([
                dep.depth for dep in self._build_dependency_graph(graph).values()
            ]) if graph.nodes else 0
        }
    
    def _calculate_improvements(self, 
                               original_metrics: Dict[str, Any],
                               optimized_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """计算改进指标"""
        improvements = {}
        
        for key in original_metrics:
            if key in optimized_metrics:
                original_val = original_metrics[key]
                optimized_val = optimized_metrics[key]
                
                if original_val != 0:
                    improvement = (original_val - optimized_val) / original_val * 100
                    improvements[f"{key}_improvement_percent"] = improvement
        
        return improvements
    
    def _generate_cache_key(self, graph: StateGraph) -> str:
        """生成缓存键"""
        import hashlib
        
        # 基于图的结构生成哈希
        graph_data = {
            "name": graph.name,
            "nodes": list(graph.nodes.keys()),
            "edges": [(e.from_node, e.to_node) for e in graph.edges],
            "conditional_edges": [e.from_node for e in graph.conditional_edges],
            "entry_point": graph.entry_point
        }
        
        graph_str = str(sorted(graph_data.items()))
        return hashlib.md5(graph_str.encode()).hexdigest()
    
    def clear_cache(self):
        """清空编译缓存"""
        self._compilation_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            "cache_size": len(self._compilation_cache),
            "cached_graphs": list(self._compilation_cache.keys())
        }

# 全局编译器实例
global_compiler = GraphCompiler()