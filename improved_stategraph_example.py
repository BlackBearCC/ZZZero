#!/usr/bin/env python3
"""
改进的 StateGraph 实现示例

展示与 LangGraph 对标的新功能：
1. 增强的状态管理机制
2. 改进的条件路由
3. 真正的并行执行
4. 强化的错误处理和容错性
5. 优化的流式执行
6. 图编译和优化
7. 调试和可视化能力
"""

import asyncio
from typing import Dict, Any, List
from src.core.graph import StateGraph, Command, RouteResult
from src.core.base import BaseNode, NodeResult, ExecutionState
from src.core.executor import StateManager, add_reducer, merge_reducer, count_reducer
from src.core.types import NodeType, Message, MessageRole


class ExampleNode(BaseNode):
    """示例节点实现"""
    
    def __init__(self, name: str, processing_time: float = 1.0):
        super().__init__(name, NodeType.CUSTOM, stream=True)
        self.processing_time = processing_time
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点逻辑"""
        print(f"[{self.name}] 开始处理，状态: {list(state.keys())}")
        
        # 模拟处理时间
        await asyncio.sleep(self.processing_time)
        
        # 返回状态更新
        return {
            "messages": [Message(
                role=MessageRole.ASSISTANT,
                content=f"节点 {self.name} 处理完成"
            )],
            "processing_count": 1,
            "processed_by": {self.name}
        }
    
    async def execute_stream(self, state: Dict[str, Any]):
        """流式执行"""
        print(f"[{self.name}] 开始流式处理")
        
        # 分步骤处理
        steps = ["初始化", "处理", "完成"]
        for i, step in enumerate(steps):
            await asyncio.sleep(self.processing_time / len(steps))
            yield {
                "messages": [Message(
                    role=MessageRole.ASSISTANT,
                    content=f"节点 {self.name} - {step}"
                )],
                "progress": (i + 1) / len(steps)
            }


class ConditionalNode(BaseNode):
    """条件节点实现"""
    
    def __init__(self, name: str):
        super().__init__(name, NodeType.ROUTER)
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """执行条件判断"""
        processing_count = state.get("processing_count", 0)
        
        if processing_count < 3:
            # 继续处理
            return Command(
                update={"decision": "continue"},
                goto=["parallel_node_1", "parallel_node_2"]
            )
        else:
            # 结束处理
            return Command(
                update={"decision": "finish"},
                goto="END"
            )


async def error_handler(error: Exception, state: Dict[str, Any]) -> NodeResult:
    """错误处理器示例"""
    print(f"处理错误: {error}")
    return NodeResult(
        node_name="error_handler",
        node_type=NodeType.CUSTOM,
        state_update={"error_handled": True, "error_message": str(error)},
        execution_state=ExecutionState.SUCCESS
    )


def route_function(state: Dict[str, Any]) -> str:
    """路由函数示例"""
    decision = state.get("decision", "continue")
    if decision == "continue":
        return "conditional_node"
    else:
        return "END"


async def demonstrate_improved_stategraph():
    """演示改进的 StateGraph 功能"""
    
    print("=== StateGraph 改进功能演示 ===\n")
    
    # 1. 创建状态图
    graph = StateGraph(name="improved_example")
    
    # 2. 添加节点
    graph.add_node("start_node", ExampleNode("start_node", 0.5))
    graph.add_node("parallel_node_1", ExampleNode("parallel_node_1", 1.0))
    graph.add_node("parallel_node_2", ExampleNode("parallel_node_2", 1.5))
    graph.add_node("conditional_node", ConditionalNode("conditional_node"))
    graph.add_node("final_node", ExampleNode("final_node", 0.3))
    
    # 3. 设置状态合并策略
    state_manager = StateManager({
        "messages": add_reducer,  # 消息列表追加
        "processing_count": count_reducer,  # 计数累加
        "processed_by": merge_reducer  # 集合合并
    })
    
    # 4. 添加边
    graph.add_edge("start_node", "conditional_node")
    graph.add_edge("parallel_node_1", "final_node")
    graph.add_edge("parallel_node_2", "final_node")
    
    # 5. 添加条件边
    graph.add_conditional_edges(
        "conditional_node",
        route_function
    )
    
    graph.add_conditional_edges(
        "final_node",
        route_function
    )
    
    # 6. 设置入口点
    graph.set_entry_point("start_node")
    
    # 7. 添加错误处理和重试策略
    graph.add_error_handler("parallel_node_1", error_handler)
    graph.add_retry_policy("parallel_node_2", max_retries=2, retry_delay=0.5)
    
    # 8. 编译图（包含优化）
    print("编译图...")
    compiled_graph = graph.compile(
        max_iterations=10,
        enable_parallel=True
    )
    
    # 9. 显示图统计信息
    stats = graph.get_execution_stats()
    print(f"\n图统计信息:")
    print(f"- 节点数量: {stats['node_count']}")
    print(f"- 边数量: {stats['edge_count']}")
    print(f"- 条件边数量: {stats['conditional_edge_count']}")
    print(f"- 入口点: {stats['entry_point']}")
    print(f"- 错误处理器: {stats['has_error_handlers']}")
    print(f"- 重试策略: {stats['has_retry_policies']}")
    
    # 10. 生成可视化
    print(f"\nMermaid 图:")
    print(graph.visualize(format="mermaid"))
    
    # 11. 初始状态
    initial_state = {
        "messages": [],
        "processing_count": 0,
        "processed_by": set()
    }
    
    # 12. 流式执行
    print(f"\n=== 开始流式执行 ===")
    async for event in compiled_graph.stream(initial_state):
        event_type = event.get("type", "unknown")
        print(f"事件: {event_type}")
        
        if event_type == "node_complete":
            node_name = event.get("node")
            print(f"  节点 {node_name} 完成")
        elif event_type == "state_update":
            update_keys = list(event.get("update", {}).keys())
            print(f"  状态更新: {update_keys}")
        elif event_type == "final":
            final_state = event.get("state", {})
            print(f"  最终状态: {list(final_state.keys())}")
            
            # 显示最终结果
            messages = final_state.get("messages", [])
            print(f"\n处理的消息数量: {len(messages)}")
            for i, msg in enumerate(messages):
                print(f"  {i+1}. {msg.content}")
            
            print(f"总处理次数: {final_state.get('processing_count', 0)}")
            print(f"处理节点: {final_state.get('processed_by', set())}")


async def demonstrate_parallel_execution():
    """演示并行执行能力"""
    
    print("\n=== 并行执行演示 ===\n")
    
    # 创建包含多个并行节点的图
    graph = StateGraph(name="parallel_demo")
    
    # 添加多个可以并行执行的节点
    for i in range(1, 5):
        graph.add_node(f"parallel_{i}", ExampleNode(f"parallel_{i}", i * 0.5))
    
    graph.add_node("aggregator", ExampleNode("aggregator", 0.2))
    
    # 所有并行节点都连接到聚合器
    for i in range(1, 5):
        graph.add_edge(f"parallel_{i}", "aggregator")
    
    graph.set_entry_point("parallel_1")
    
    # 编译并执行
    compiled_graph = graph.compile(enable_parallel=True)
    
    initial_state = {"messages": [], "processing_count": 0}
    
    import time
    start_time = time.time()
    
    result = await compiled_graph.invoke(initial_state)
    
    end_time = time.time()
    
    print(f"并行执行完成，耗时: {end_time - start_time:.2f}s")
    print(f"处理次数: {result.get('processing_count', 0)}")


async def demonstrate_error_handling():
    """演示错误处理能力"""
    
    print("\n=== 错误处理演示 ===\n")
    
    class ErrorNode(BaseNode):
        def __init__(self, name: str, should_fail: bool = True):
            super().__init__(name, NodeType.CUSTOM)
            self.should_fail = should_fail
        
        async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
            if self.should_fail:
                raise ValueError(f"节点 {self.name} 模拟失败")
            return {"success": True}
    
    async def recovery_handler(error: Exception, state: Dict[str, Any]) -> NodeResult:
        return NodeResult(
            node_name="recovery",
            node_type=NodeType.CUSTOM,
            state_update={"recovered": True, "error": str(error)},
            execution_state=ExecutionState.SUCCESS
        )
    
    graph = StateGraph(name="error_demo")
    graph.add_node("normal_node", ExampleNode("normal_node"))
    graph.add_node("error_node", ErrorNode("error_node", should_fail=True))
    graph.add_node("final_node", ExampleNode("final_node"))
    
    graph.add_edge("normal_node", "error_node")
    graph.add_edge("error_node", "final_node")
    graph.set_entry_point("normal_node")
    
    # 添加错误处理和重试
    graph.add_error_handler("error_node", recovery_handler)
    graph.add_retry_policy("error_node", max_retries=2, retry_delay=0.1)
    
    compiled_graph = graph.compile()
    
    result = await compiled_graph.invoke({"messages": []})
    
    print(f"错误处理结果:")
    print(f"- 是否恢复: {result.get('recovered', False)}")
    print(f"- 错误信息: {result.get('error', 'None')}")


if __name__ == "__main__":
    # 运行所有演示
    asyncio.run(demonstrate_improved_stategraph())
    asyncio.run(demonstrate_parallel_execution())
    asyncio.run(demonstrate_error_handling())