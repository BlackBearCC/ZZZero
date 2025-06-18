"""
并行节点 - 支持并行执行多个子节点
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType


class ParallelNode(BaseNode):
    """并行节点 - 并行执行多个子节点"""
    
    def __init__(self,
                 name: str,
                 sub_nodes: List[BaseNode],
                 aggregation_strategy: str = "all",
                 max_workers: Optional[int] = None,
                 timeout: Optional[float] = None,
                 **kwargs):
        """
        初始化并行节点
        
        Args:
            name: 节点名称
            sub_nodes: 要并行执行的子节点列表
            aggregation_strategy: 结果聚合策略
                - "all": 等待所有节点完成
                - "first": 返回第一个完成的结果
                - "majority": 多数完成即可
                - "custom": 自定义聚合函数
            max_workers: 最大并行数（None表示不限制）
            timeout: 超时时间（秒）
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.PARALLEL, "并行执行多个节点", **kwargs)
        self.sub_nodes = sub_nodes
        self.aggregation_strategy = aggregation_strategy
        self.max_workers = max_workers or len(sub_nodes)
        self.timeout = timeout
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行并行逻辑"""
        start_time = datetime.now()
        
        # 创建任务列表
        tasks = []
        for i, node in enumerate(self.sub_nodes):
            # 为每个子节点创建独立的输入副本
            node_input = NodeInput(
                context=input_data.context,
                previous_output=input_data.previous_output,
                parameters={
                    **input_data.parameters,
                    "parallel_index": i,
                    "parallel_total": len(self.sub_nodes)
                }
            )
            
            # 创建任务
            task = asyncio.create_task(
                self._execute_sub_node(node, node_input)
            )
            tasks.append((node.name, task))
        
        # 根据聚合策略执行
        if self.aggregation_strategy == "first":
            results = await self._execute_first_completed(tasks)
        elif self.aggregation_strategy == "majority":
            results = await self._execute_majority(tasks)
        else:  # "all" 或 "custom"
            results = await self._execute_all(tasks)
        
        # 聚合结果
        aggregated = self._aggregate_results(results)
        
        # 计算执行时间
        duration = (datetime.now() - start_time).total_seconds()
        
        # 决定下一个节点
        next_node = self._decide_next_node(aggregated)
        
        return NodeOutput(
            data={
                "parallel_results": results,
                "aggregated": aggregated,
                "execution_time": duration,
                "strategy": self.aggregation_strategy
            },
            next_node=next_node,
            should_continue=aggregated.get("should_continue", True),
            metadata={
                "parallel_count": len(self.sub_nodes),
                "completed_count": len(results),
                "success_count": sum(1 for r in results.values() if r.get("success", False))
            }
        )
    
    async def _execute_sub_node(self, 
                               node: BaseNode, 
                               input_data: NodeInput) -> Dict[str, Any]:
        """执行单个子节点"""
        try:
            # 如果设置了超时，使用超时控制
            if self.timeout:
                result = await asyncio.wait_for(
                    node.run(input_data),
                    timeout=self.timeout
                )
            else:
                result = await node.run(input_data)
            
            return {
                "node_name": node.name,
                "node_type": node.node_type.value,
                "success": result.state.value == "success",
                "output": result.output.data if result.output else None,
                "metadata": result.output.metadata if result.output else {},
                "duration": result.duration,
                "error": result.error
            }
            
        except asyncio.TimeoutError:
            return {
                "node_name": node.name,
                "node_type": node.node_type.value,
                "success": False,
                "output": None,
                "error": f"超时（{self.timeout}秒）",
                "timeout": True
            }
        except Exception as e:
            return {
                "node_name": node.name,
                "node_type": node.node_type.value,
                "success": False,
                "output": None,
                "error": str(e),
                "exception": True
            }
    
    async def _execute_all(self, 
                          tasks: List[Tuple[str, asyncio.Task]]) -> Dict[str, Any]:
        """执行所有任务"""
        results = {}
        
        # 使用信号量限制并发数
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def limited_task(name: str, task: asyncio.Task):
            async with semaphore:
                return name, await task
        
        # 等待所有任务完成
        completed = await asyncio.gather(
            *[limited_task(name, task) for name, task in tasks],
            return_exceptions=True
        )
        
        # 处理结果
        for item in completed:
            if isinstance(item, Exception):
                # 任务执行失败
                results["error"] = {
                    "success": False,
                    "error": str(item)
                }
            else:
                name, result = item
                results[name] = result
                
        return results
    
    async def _execute_first_completed(self, 
                                     tasks: List[Tuple[str, asyncio.Task]]) -> Dict[str, Any]:
        """返回第一个完成的结果"""
        # 等待第一个完成的任务
        done, pending = await asyncio.wait(
            [task for _, task in tasks],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # 取消其他任务
        for task in pending:
            task.cancel()
            
        # 获取结果
        for task in done:
            try:
                # 找到对应的节点名称
                for name, t in tasks:
                    if t == task:
                        return {name: await task}
            except Exception as e:
                continue
                
        return {}
    
    async def _execute_majority(self, 
                              tasks: List[Tuple[str, asyncio.Task]]) -> Dict[str, Any]:
        """等待多数任务完成"""
        results = {}
        required = len(tasks) // 2 + 1
        completed_count = 0
        
        # 逐个等待任务完成
        for future in asyncio.as_completed([task for _, task in tasks]):
            try:
                result = await future
                # 找到对应的节点名称
                for name, task in tasks:
                    if task == future:
                        results[name] = result
                        completed_count += 1
                        break
                        
                # 检查是否达到多数
                if completed_count >= required:
                    # 取消剩余任务
                    for name, task in tasks:
                        if name not in results:
                            task.cancel()
                    break
                    
            except Exception as e:
                continue
                
        return results
    
    def _aggregate_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """聚合结果"""
        if not results:
            return {"success": False, "message": "没有结果"}
            
        # 统计成功和失败的数量
        success_count = sum(1 for r in results.values() if r.get("success", False))
        total_count = len(results)
        
        # 收集所有输出
        all_outputs = []
        all_errors = []
        
        for name, result in results.items():
            if result.get("success"):
                if result.get("output"):
                    all_outputs.append({
                        "node": name,
                        "output": result["output"]
                    })
            else:
                all_errors.append({
                    "node": name,
                    "error": result.get("error", "Unknown error")
                })
        
        # 基本聚合结果
        aggregated = {
            "success": success_count > 0,
            "success_rate": success_count / total_count if total_count > 0 else 0,
            "outputs": all_outputs,
            "errors": all_errors,
            "should_continue": success_count > 0
        }
        
        # 如果是自定义聚合策略，调用自定义函数
        if self.aggregation_strategy == "custom" and hasattr(self, "custom_aggregate"):
            aggregated = self.custom_aggregate(results, aggregated)
            
        return aggregated
    
    def _decide_next_node(self, aggregated: Dict[str, Any]) -> Optional[str]:
        """决定下一个节点"""
        # 如果所有节点都失败，可能需要转到错误处理节点
        if not aggregated.get("success"):
            return self.config.get("error_node")
            
        # 如果配置了特定的下一个节点
        if "next_node" in self.config:
            return self.config["next_node"]
            
        # 否则返回None，让图执行器决定
        return None
    
    def add_sub_node(self, node: BaseNode):
        """动态添加子节点"""
        self.sub_nodes.append(node)
        
    def remove_sub_node(self, node_name: str):
        """动态移除子节点"""
        self.sub_nodes = [n for n in self.sub_nodes if n.name != node_name] 