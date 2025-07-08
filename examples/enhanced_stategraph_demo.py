"""
增强版StateGraph演示 - 展示所有新功能
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any

# 导入增强版模块
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.graph import StateGraph, StateGraphExecutor, Command
from core.base import BaseNode
from core.types import NodeType, Message, MessageRole
from core.executor import (
    StateManager, add_reducer, priority_reducer, timestamp_reducer,
    CheckpointStorage
)
from core.error_handling import (
    ErrorHandler, RetryPolicy, CircuitBreakerConfig,
    ErrorAction, ErrorContext
)
from core.compiler import GraphCompiler, OptimizationLevel
from core.monitoring import (
    ExecutionMonitor, TraceContext, monitor_node,
    FileExporter, ConsoleExporter
)
from core.visualization import (
    GraphVisualizer, VisualizationConfig, VisualizationFormat
)

class DemoThinkNode(BaseNode):
    """演示思考节点"""
    
    def __init__(self, name: str):
        super().__init__(name, NodeType.THINK, "分析问题并制定策略")
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行思考逻辑"""
        query = state.get("query", "")
        
        # 模拟思考过程
        await asyncio.sleep(0.5)
        
        thought = f"分析问题: {query}. 需要搜索和处理信息。"
        
        return {
            "thought": thought,
            "next_action": "search",
            "confidence": 0.8,
            "messages": [Message(
                role=MessageRole.ASSISTANT,
                content=f"💭 思考: {thought}"
            )]
        }

class DemoActionNode(BaseNode):
    """演示行动节点"""
    
    def __init__(self, name: str):
        super().__init__(name, NodeType.ACT, "执行具体行动")
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行行动逻辑"""
        action = state.get("next_action", "search")
        
        # 模拟行动过程
        await asyncio.sleep(0.3)
        
        if action == "search":
            result = "找到相关信息: AI技术发展迅速，应用广泛。"
        else:
            result = "执行了其他行动"
        
        return {
            "action_result": result,
            "status": "completed",
            "messages": [Message(
                role=MessageRole.ASSISTANT,
                content=f"🔍 行动: {result}"
            )]
        }

class DemoRouterNode(BaseNode):
    """演示路由节点"""
    
    def __init__(self, name: str):
        super().__init__(name, NodeType.ROUTER, "决定下一步行动")
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """执行路由逻辑"""
        confidence = state.get("confidence", 0.5)
        iteration = state.get("iteration", 0)
        
        # 路由决策
        if confidence > 0.9 or iteration > 2:
            next_node = "finalize"
        elif confidence < 0.5:
            next_node = "think"
        else:
            next_node = "act"
        
        return Command(
            update={
                "iteration": iteration + 1,
                "router_decision": f"置信度 {confidence:.2f}, 路由到 {next_node}"
            },
            goto=next_node
        )

class DemoFinalizeNode(BaseNode):
    """演示最终化节点"""
    
    def __init__(self, name: str):
        super().__init__(name, NodeType.FINALIZE, "生成最终回答")
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """生成最终回答"""
        thought = state.get("thought", "")
        action_result = state.get("action_result", "")
        
        final_answer = f"""
基于分析和搜索，我的回答是：

思考过程: {thought}
搜索结果: {action_result}

总结: 这是一个综合考虑多种因素后得出的答案。
        """.strip()
        
        return {
            "final_answer": final_answer,
            "completed": True,
            "messages": [Message(
                role=MessageRole.ASSISTANT,
                content=f"✅ 最终回答: {final_answer}"
            )]
        }

async def demonstrate_enhanced_stategraph():
    """演示增强版StateGraph的所有功能"""
    print("🚀 开始增强版StateGraph演示")
    print("=" * 60)
    
    # 1. 创建增强版StateGraph
    print("\n📊 1. 创建增强版StateGraph")
    graph = StateGraph(name="enhanced_demo_graph")
    
    # 添加节点
    think_node = DemoThinkNode("think")
    act_node = DemoActionNode("act") 
    router_node = DemoRouterNode("router")
    finalize_node = DemoFinalizeNode("finalize")
    
    graph.add_node("think", think_node)
    graph.add_node("act", act_node)
    graph.add_node("router", router_node)
    graph.add_node("finalize", finalize_node)
    
    # 添加边
    graph.add_edge("think", "router")
    graph.add_edge("act", "router")
    
    # 添加条件边
    def route_condition(state: Dict[str, Any]) -> str:
        """路由条件函数"""
        # 这里router节点会通过Command控制路由
        return "router"
    
    graph.add_conditional_edges("router", route_condition, {
        "think": "think",
        "act": "act", 
        "finalize": "finalize"
    })
    
    # 设置入口点
    graph.set_entry_point("think")
    
    print(f"✅ 创建了包含 {len(graph.nodes)} 个节点的图")
    
    # 2. 图编译和优化
    print("\n🔧 2. 图编译和优化")
    from core.compiler import global_compiler
    
    compiler = GraphCompiler(
        optimization_level=OptimizationLevel.BASIC,
        enable_validation=True,
        enable_optimization=True
    )
    
    compilation_result = compiler.compile(graph)
    
    print(f"✅ 编译结果: {'成功' if compilation_result.validation_result.is_valid else '失败'}")
    print(f"   编译时间: {compilation_result.compilation_time:.3f}s")
    
    if compilation_result.validation_result.warnings:
        print(f"   警告: {compilation_result.validation_result.warnings}")
    
    if compilation_result.validation_result.suggestions:
        print(f"   建议: {compilation_result.validation_result.suggestions}")
    
    # 3. 错误处理配置
    print("\n🛡️ 3. 配置错误处理")
    
    error_handler = ErrorHandler()
    
    # 为think节点添加重试策略
    error_handler.add_retry_policy("think", RetryPolicy(
        max_retries=2,
        initial_delay=0.1,
        backoff_multiplier=2.0
    ))
    
    # 为act节点添加断路器
    error_handler.add_circuit_breaker("act", CircuitBreakerConfig(
        failure_threshold=3,
        timeout=10.0
    ))
    
    # 添加自定义错误处理器
    def handle_think_error(context: ErrorContext) -> ErrorAction:
        print(f"⚠️ 处理think节点错误: {context.error}")
        return ErrorAction.RETRY if context.attempt < 2 else ErrorAction.SKIP
    
    error_handler.add_error_handler(ValueError, handle_think_error)
    
    print("✅ 错误处理配置完成")
    
    # 4. 监控配置
    print("\n📈 4. 配置执行监控")
    
    monitor = ExecutionMonitor(
        enable_metrics=True,
        enable_tracing=True,
        export_interval=30
    )
    
    # 添加导出器
    monitor.add_exporter(FileExporter("./workspace/monitoring"))
    monitor.add_exporter(ConsoleExporter())
    
    # 添加事件回调
    def log_important_events(event):
        if event.event_type.value in ["node_error", "graph_complete"]:
            print(f"📝 重要事件: {event.event_type.value} - {event.node_name}")
    
    monitor.add_event_callback(log_important_events)
    
    await monitor.start()
    print("✅ 监控系统已启动")
    
    # 5. 执行配置
    print("\n⚙️ 5. 配置增强版执行器")
    
    executor = StateGraphExecutor(
        max_iterations=10,
        enable_parallel=True,
        max_concurrent_nodes=3,
        enable_error_handling=True,
        enable_state_locking=True
    )
    
    # 设置错误处理器
    executor.error_handler = error_handler
    
    print("✅ 执行器配置完成")
    
    # 6. 状态管理配置
    print("\n🗄️ 6. 配置增强版状态管理")
    
    # 使用高级状态合并器
    state_manager = StateManager(
        reducers={
            "messages": add_reducer,
            "priority_data": priority_reducer,
            "timestamped_data": timestamp_reducer
        },
        enable_versioning=True,
        enable_checkpoints=True,
        checkpoint_storage=CheckpointStorage.FILE,
        checkpoint_path="./workspace/checkpoints"
    )
    
    print("✅ 状态管理配置完成")
    
    # 7. 执行演示
    print("\n🏃 7. 执行增强版StateGraph")
    
    # 创建执行轨迹
    trace_id = str(uuid.uuid4())
    
    async with TraceContext(trace_id, graph.name, monitor):
        # 初始状态
        initial_state = {
            "query": "AI技术的发展趋势是什么？",
            "iteration": 0,
            "confidence": 0.6,
            "messages": [Message(
                role=MessageRole.USER,
                content="AI技术的发展趋势是什么？"
            )]
        }
        
        # 执行配置
        execution_config = {
            "enable_checkpoints": True,
            "enable_versioning": True,
            "checkpoint_storage": CheckpointStorage.FILE
        }
        
        print(f"🎯 开始执行 (轨迹ID: {trace_id[:8]}...)")
        
        try:
            final_state = await executor.execute(
                graph=compilation_result.optimized_graph or graph,
                initial_state=initial_state,
                config=execution_config
            )
            
            print("\n✅ 执行成功完成!")
            print(f"🔄 总迭代次数: {final_state.get('_execution_metadata', {}).get('total_iterations', 'N/A')}")
            print(f"⏱️ 执行时间: {final_state.get('_execution_metadata', {}).get('execution_time', 'N/A'):.2f}s")
            print(f"📝 访问节点: {final_state.get('_execution_metadata', {}).get('visited_nodes', [])}")
            
            # 显示最终答案
            if "final_answer" in final_state:
                print(f"\n💡 最终答案:\n{final_state['final_answer']}")
            
            # 显示消息历史
            messages = final_state.get("messages", [])
            print(f"\n💬 消息历史 ({len(messages)} 条):")
            for i, msg in enumerate(messages[-3:], 1):  # 显示最后3条
                print(f"   {i}. [{msg.role.value}] {msg.content}")
            
        except Exception as e:
            print(f"❌ 执行失败: {e}")
    
    # 8. 可视化演示
    print("\n🎨 8. 生成可视化")
    
    from core.visualization import global_visualizer
    
    # 获取执行轨迹
    trace = monitor.get_trace(trace_id)
    
    # 生成多种格式的可视化
    formats = [
        (VisualizationFormat.MERMAID, "mermaid"),
        (VisualizationFormat.HTML, "html")
    ]
    
    for viz_format, file_ext in formats:
        try:
            config = VisualizationConfig(
                format=viz_format,
                include_metadata=True,
                include_performance=True,
                theme="default",
                width=1000,
                height=600
            )
            
            visualization = global_visualizer.visualize_graph(
                graph, config, trace
            )
            
            # 保存到文件
            output_path = f"./workspace/visualizations/enhanced_demo.{file_ext}"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(visualization)
            
            print(f"✅ {viz_format.value} 可视化已保存到: {output_path}")
            
        except Exception as e:
            print(f"⚠️ 生成 {viz_format.value} 可视化失败: {e}")
    
    # 9. 监控数据展示
    print("\n📊 9. 监控数据摘要")
    
    # 获取监控摘要
    metrics_summary = monitor.get_metrics_summary()
    
    print(f"   活跃轨迹: {metrics_summary.get('active_traces', 0)}")
    print(f"   历史轨迹: {metrics_summary.get('total_traces', 0)}")
    
    # 显示关键指标
    metrics = metrics_summary.get('metrics', {})
    for metric_name, metric_data in metrics.items():
        if 'duration' in metric_name and 'avg' in metric_data:
            print(f"   {metric_name}: 平均 {metric_data['avg']:.2f}s")
    
    # 10. 清理
    print("\n🧹 10. 清理资源")
    
    await monitor.stop()
    error_handler.reset_error_stats()
    
    print("✅ 资源清理完成")
    
    print("\n" + "=" * 60)
    print("🎉 增强版StateGraph演示完成!")
    print("\n📚 新功能总结:")
    print("   ✓ 持久化检查点和状态版本控制")
    print("   ✓ 高级状态合并器 (priority, timestamp)")
    print("   ✓ 真正的并行执行和状态同步")
    print("   ✓ 分级错误处理和重试机制")
    print("   ✓ 图编译优化和验证")
    print("   ✓ 执行监控和性能指标")
    print("   ✓ 多格式可视化支持")
    print("   ✓ 交互式HTML可视化")

async def demonstrate_advanced_features():
    """演示高级功能"""
    print("\n🔬 演示高级功能")
    print("-" * 40)
    
    # 1. 状态合并器演示
    print("\n1. 高级状态合并器演示")
    
    from core.executor import priority_reducer, timestamp_reducer, strategy_reducer
    
    # priority_reducer演示
    old_data = {
        "task1": {"priority": 1, "data": "低优先级任务"},
        "task2": {"priority": 5, "data": "中优先级任务"}
    }
    new_data = {
        "task1": {"priority": 8, "data": "高优先级任务"},
        "task3": {"priority": 3, "data": "新任务"}
    }
    
    merged = priority_reducer(old_data, new_data)
    print(f"   优先级合并结果: {merged}")
    
    # timestamp_reducer演示
    old_time_data = {
        "event1": {"timestamp": datetime(2024, 1, 1), "data": "旧事件"},
        "event2": {"timestamp": datetime(2024, 1, 2), "data": "较新事件"}
    }
    new_time_data = {
        "event1": {"timestamp": datetime(2024, 1, 3), "data": "最新事件"},
        "event3": {"timestamp": datetime(2024, 1, 1), "data": "另一个事件"}
    }
    
    time_merged = timestamp_reducer(old_time_data, new_time_data)
    print(f"   时间戳合并结果: {list(time_merged.keys())}")
    
    # 2. 断路器演示
    print("\n2. 断路器机制演示")
    
    from core.error_handling import CircuitBreaker, CircuitBreakerConfig
    
    breaker = CircuitBreaker(CircuitBreakerConfig(
        failure_threshold=2,
        timeout=1.0
    ))
    
    async def unreliable_function():
        """不可靠的函数"""
        import random
        if random.random() < 0.7:  # 70%失败率
            raise Exception("模拟失败")
        return "成功"
    
    # 测试断路器
    for i in range(5):
        try:
            result = await breaker.call(unreliable_function)
            print(f"   调用 {i+1}: {result}")
        except Exception as e:
            print(f"   调用 {i+1}: 失败 - {e}")
    
    # 3. 检查点系统演示
    print("\n3. 检查点系统演示")
    
    from core.executor import CheckpointManager, CheckpointStorage
    
    checkpoint_mgr = CheckpointManager(
        storage_type=CheckpointStorage.MEMORY,
        max_checkpoints=5
    )
    
    # 创建检查点
    test_state = {"step": 1, "data": "测试数据", "counter": 100}
    cp_id = checkpoint_mgr.save_checkpoint(test_state, "test_node")
    print(f"   创建检查点: {cp_id}")
    
    # 修改状态
    test_state["step"] = 2
    test_state["counter"] = 200
    
    # 恢复检查点
    restored_state = checkpoint_mgr.load_checkpoint(cp_id)
    print(f"   恢复状态: step={restored_state.get('step')}, counter={restored_state.get('counter')}")
    
    print("\n✅ 高级功能演示完成")

if __name__ == "__main__":
    # 确保目录存在
    os.makedirs("./workspace/monitoring", exist_ok=True)
    os.makedirs("./workspace/checkpoints", exist_ok=True)
    os.makedirs("./workspace/visualizations", exist_ok=True)
    
    # 运行主演示
    asyncio.run(demonstrate_enhanced_stategraph())
    
    # 运行高级功能演示
    asyncio.run(demonstrate_advanced_features())