#!/usr/bin/env python3
"""
修复后的 StateGraph 示例 - 解决无限循环和执行问题
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


class ConditionalNode(BaseNode):
    """条件节点实现 - 修复路由逻辑"""
    
    def __init__(self, name: str):
        super().__init__(name, NodeType.ROUTER)
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """执行条件判断"""
        processing_count = state.get("processing_count", 0)
        
        print(f"[{self.name}] 当前处理次数: {processing_count}")
        
        if processing_count < 2:  # 减少循环次数
            # 发送到并行节点
            return Command(
                update={"decision": "parallel"},
                goto=["parallel_node_1", "parallel_node_2"]  # 直接指定并行节点
            )
        else:
            # 结束处理
            return Command(
                update={"decision": "finish"},
                goto="final_node"
            )


class ErrorNode(BaseNode):
    """错误测试节点"""
    def __init__(self, name: str, should_fail: bool = True):
        super().__init__(name, NodeType.CUSTOM)
        self.should_fail = should_fail
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        print(f"[{self.name}] 执行中，should_fail={self.should_fail}")
        if self.should_fail:
            raise ValueError(f"节点 {self.name} 模拟失败")
        return {"success": True}


async def error_handler(error: Exception, state: Dict[str, Any]) -> NodeResult:
    """错误处理器示例"""
    print(f"🛡️ 处理错误: {error}")
    return NodeResult(
        node_name="error_handler",
        node_type=NodeType.CUSTOM,
        state_update={"error_handled": True, "error_message": str(error)},
        execution_state=ExecutionState.SUCCESS
    )


async def demonstrate_fixed_stategraph():
    """演示修复后的 StateGraph"""
    
    print("=== 修复后的 StateGraph 演示 ===\n")
    
    # 1. 创建状态图
    graph = StateGraph(name="fixed_example")
    
    # 2. 添加节点
    graph.add_node("start_node", ExampleNode("start_node", 0.5))
    graph.add_node("conditional_node", ConditionalNode("conditional_node"))
    graph.add_node("parallel_node_1", ExampleNode("parallel_node_1", 1.0))
    graph.add_node("parallel_node_2", ExampleNode("parallel_node_2", 1.5))
    graph.add_node("final_node", ExampleNode("final_node", 0.3))
    
    # 3. 设置状态合并策略
    state_manager = StateManager({
        "messages": add_reducer,
        "processing_count": count_reducer,
        "processed_by": merge_reducer
    })
    
    # 4. 添加边 - 修复路由逻辑
    graph.add_edge("start_node", "conditional_node")
    graph.add_edge("parallel_node_1", "final_node")
    graph.add_edge("parallel_node_2", "final_node")
    
    # 5. 设置入口点
    graph.set_entry_point("start_node")
    
    # 6. 编译图
    print("编译图...")
    compiled_graph = graph.compile(
        max_iterations=10,
        enable_parallel=True
    )
    
    # 7. 初始状态
    initial_state = {
        "messages": [],
        "processing_count": 0,
        "processed_by": set()
    }
    
    # 8. 执行
    print(f"\n=== 开始执行 ===")
    try:
        final_state = await compiled_graph.invoke(initial_state)
        
        print(f"\n=== 执行结果 ===")
        print(f"最终状态键: {list(final_state.keys())}")
        print(f"处理次数: {final_state.get('processing_count', 0)}")
        print(f"处理节点: {final_state.get('processed_by', set())}")
        
        messages = final_state.get("messages", [])
        print(f"\n处理的消息数量: {len(messages)}")
        for i, msg in enumerate(messages, 1):
            print(f"  {i}. {msg.content}")
            
    except Exception as e:
        print(f"❌ 执行失败: {e}")


async def demonstrate_simple_parallel():
    """演示简单的并行执行"""
    
    print("\n=== 简单并行执行演示 ===\n")
    
    # 创建简单的并行图
    graph = StateGraph(name="simple_parallel")
    
    # 添加节点
    graph.add_node("start", ExampleNode("start", 0.2))
    graph.add_node("task1", ExampleNode("task1", 1.0))
    graph.add_node("task2", ExampleNode("task2", 1.5))
    graph.add_node("task3", ExampleNode("task3", 0.8))
    graph.add_node("finish", ExampleNode("finish", 0.3))
    
    # 连接 - start连接到所有任务，所有任务连接到finish
    graph.add_edge("start", "task1")
    graph.add_edge("start", "task2")
    graph.add_edge("start", "task3")
    graph.add_edge("task1", "finish")
    graph.add_edge("task2", "finish")
    graph.add_edge("task3", "finish")
    
    graph.set_entry_point("start")
    
    # 编译并执行
    compiled_graph = graph.compile(enable_parallel=True)
    
    initial_state = {"messages": [], "processing_count": 0}
    
    import time
    start_time = time.time()
    
    print("开始执行...")
    result = await compiled_graph.invoke(initial_state)
    
    end_time = time.time()
    
    print(f"执行完成，耗时: {end_time - start_time:.2f}秒")
    print(f"处理次数: {result.get('processing_count', 0)}")
    print(f"消息数量: {len(result.get('messages', []))}")


async def demonstrate_error_handling():
    """演示错误处理"""
    
    print("\n=== 错误处理演示 ===\n")
    
    graph = StateGraph(name="error_demo")
    graph.add_node("normal_node", ExampleNode("normal_node"))
    graph.add_node("error_node", ErrorNode("error_node", should_fail=True))
    graph.add_node("final_node", ExampleNode("final_node"))
    
    graph.add_edge("normal_node", "error_node")
    graph.add_edge("error_node", "final_node")
    graph.set_entry_point("normal_node")
    
    # 添加错误处理
    if hasattr(graph, 'add_error_handler'):
        graph.add_error_handler("error_node", error_handler)
    if hasattr(graph, 'add_retry_policy'):
        graph.add_retry_policy("error_node", max_retries=2, retry_delay=0.1)
    
    compiled_graph = graph.compile()
    
    try:
        result = await compiled_graph.invoke({"messages": []})
        
        print(f"错误处理结果:")
        print(f"- 是否恢复: {result.get('error_handled', False)}")
        print(f"- 错误信息: {result.get('error_message', 'None')}")
        
    except Exception as e:
        print(f"⚠️ 执行中的异常: {e}")


if __name__ == "__main__":
    print("🚀 运行修复后的 StateGraph 演示...\n")
    
    # 运行所有演示
    asyncio.run(demonstrate_fixed_stategraph())
    asyncio.run(demonstrate_simple_parallel())
    asyncio.run(demonstrate_error_handling())
    
    print("\n🎉 演示完成！")
    print("\n📋 修复的问题:")
    print("1. ✅ 修复了无限循环问题")
    print("2. ✅ 改进了并行执行逻辑")
    print("3. ✅ 简化了路由函数")
    print("4. ✅ 添加了更多调试信息")