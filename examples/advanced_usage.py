"""
高级用法示例 - 展示路由节点、并行节点和流程可视化
"""
import asyncio
from src.core.graph import GraphBuilder
from src.core.types import GraphContext
from src.llm import create_llm_provider
from src.nodes import (
    ThinkNode, ActNode, ObserveNode, FinalizeNode,
    RouterNode, ParallelNode,
    create_conditional_route, create_loop_route
)
from src.tools import MCPToolManager


async def example_with_router():
    """使用路由节点的示例"""
    print("=== 路由节点示例 ===")
    
    # 创建LLM
    llm = create_llm_provider("doubao")
    
    # 创建工具管理器
    tool_manager = MCPToolManager()
    await tool_manager.initialize()
    
    # 创建节点
    think_node = ThinkNode("think", llm)
    act_node = ActNode("act", llm, tool_manager)
    observe_node = ObserveNode("observe", llm)
    finalize_node = FinalizeNode("finalize", llm)
    
    # 创建路由节点 - 根据是否需要更多信息决定继续循环还是结束
    router = RouterNode(
        "router",
        routes=[
            # 如果需要更多信息，回到思考节点
            create_loop_route(
                target="think",
                while_condition="len(messages) < 10 and not has_result",
                max_loops=5,
                fallback="finalize"
            ),
            # 如果已经有足够信息，进入最终化
            create_conditional_route(
                condition="has_result or len(messages) >= 10",
                target="finalize"
            )
        ],
        default_route="finalize"
    )
    
    # 构建图
    builder = GraphBuilder()
    builder.add_node(think_node)
    builder.add_node(act_node)
    builder.add_node(observe_node)
    builder.add_node(router)
    builder.add_node(finalize_node)
    
    # 添加边
    builder.add_edge("think", "act")
    builder.add_edge("act", "observe")
    builder.add_edge("observe", "router")  # 观察后进入路由
    builder.add_edge("router", None)  # 路由节点自己决定下一个节点
    
    # 创建执行器
    graph = builder.build()
    executor = graph.create_executor()
    
    # 执行
    context = GraphContext()
    query = "Python中如何实现单例模式？给出多种实现方式。"
    result = await executor.execute(query, context, start_node="think")
    
    print(f"\n最终答案：{result.result}")
    print(f"执行步骤数：{len(result.execution_trace)}")


async def example_with_parallel():
    """使用并行节点的示例"""
    print("\n=== 并行节点示例 ===")
    
    # 创建LLM
    llm = create_llm_provider("doubao")
    
    # 创建工具管理器
    tool_manager = MCPToolManager()
    await tool_manager.initialize()
    
    # 创建多个搜索节点（模拟从不同来源获取信息）
    search_nodes = [
        ActNode(f"search_{i}", llm, tool_manager)
        for i in range(3)
    ]
    
    # 创建并行节点
    parallel_search = ParallelNode(
        "parallel_search",
        sub_nodes=search_nodes,
        aggregation_strategy="all",  # 等待所有搜索完成
        timeout=10.0  # 10秒超时
    )
    
    # 创建其他节点
    think_node = ThinkNode("think", llm)
    observe_node = ObserveNode("observe", llm)
    finalize_node = FinalizeNode("finalize", llm)
    
    # 构建图
    builder = GraphBuilder()
    builder.add_node(think_node)
    builder.add_node(parallel_search)
    builder.add_node(observe_node)
    builder.add_node(finalize_node)
    
    # 添加边
    builder.add_edge("think", "parallel_search")
    builder.add_edge("parallel_search", "observe")
    builder.add_edge("observe", "finalize")
    
    # 创建执行器
    graph = builder.build()
    executor = graph.create_executor()
    
    # 执行
    context = GraphContext()
    query = "比较Python、JavaScript和Go语言的特点"
    result = await executor.execute(query, context, start_node="think")
    
    print(f"\n最终答案：{result.result}")
    print(f"并行执行的节点数：3")
    print(f"总执行时间：{result.metrics.get('total_duration', 0):.2f}秒")


async def example_complex_workflow():
    """复杂工作流示例 - 结合路由和并行"""
    print("\n=== 复杂工作流示例 ===")
    
    # 创建LLM
    llm = create_llm_provider("doubao")
    
    # 创建工具管理器
    tool_manager = MCPToolManager()
    await tool_manager.initialize()
    
    # 创建节点
    think_node = ThinkNode("think", llm)
    
    # 创建并行搜索节点
    parallel_search = ParallelNode(
        "parallel_search",
        sub_nodes=[
            ActNode(f"search_{i}", llm, tool_manager)
            for i in range(2)
        ],
        aggregation_strategy="first",  # 使用第一个完成的结果
        timeout=5.0
    )
    
    # 创建验证节点
    verify_node = ActNode("verify", llm, tool_manager)
    
    # 创建路由节点 - 根据搜索结果决定是否需要验证
    router = RouterNode(
        "quality_check",
        routes=[
            # 如果置信度高，直接最终化
            create_conditional_route(
                condition="success_rate > 0.8",
                target="finalize"
            ),
            # 如果置信度低，需要验证
            create_conditional_route(
                condition="success_rate <= 0.8",
                target="verify"
            )
        ]
    )
    
    observe_node = ObserveNode("observe", llm)
    finalize_node = FinalizeNode("finalize", llm)
    
    # 构建图
    builder = GraphBuilder()
    
    # 添加所有节点
    for node in [think_node, parallel_search, router, verify_node, observe_node, finalize_node]:
        builder.add_node(node)
    
    # 添加边
    builder.add_edge("think", "parallel_search")
    builder.add_edge("parallel_search", "quality_check")
    builder.add_edge("quality_check", None)  # 路由自决定
    builder.add_edge("verify", "observe")
    builder.add_edge("observe", "finalize")
    
    # 创建执行器
    graph = builder.build()
    executor = graph.create_executor()
    
    # 执行
    context = GraphContext()
    query = "如何优化Python代码的性能？"
    result = await executor.execute(query, context, start_node="think")
    
    print(f"\n最终答案：{result.result}")
    print(f"\n执行轨迹：")
    for i, step in enumerate(result.execution_trace):
        print(f"{i+1}. {step['node']} ({step['type']}) - {step['state']}")


async def main():
    """运行所有示例"""
    # 运行路由节点示例
    await example_with_router()
    
    # 运行并行节点示例
    await example_with_parallel()
    
    # 运行复杂工作流示例
    await example_complex_workflow()


if __name__ == "__main__":
    # 设置环境变量（如果需要）
    import os
    os.environ["ARK_BASE_URL"] = "https://ark.cn-beijing.volces.com/api/v3"
    
    # 运行示例
    asyncio.run(main()) 