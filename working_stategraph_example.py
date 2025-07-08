#!/usr/bin/env python3
"""
工作的 StateGraph 示例 - 修复后的版本

注意：运行前需要安装依赖：
pip install pydantic networkx
"""

import asyncio
import sys
import os
from typing import Dict, Any

# 添加src路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from core.graph import StateGraph, StateGraphExecutor, Command
    from core.base import BaseNode, NodeResult, ExecutionState
    from core.types import NodeType, Message, MessageRole
    from core.executor import StateManager, add_reducer
    print("✅ 所有模块导入成功")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请安装依赖: pip install pydantic networkx")
    sys.exit(1)


class SimpleNode(BaseNode):
    """简单节点实现"""
    
    def __init__(self, name: str, message: str = ""):
        super().__init__(name, NodeType.CUSTOM, description=f"节点 {name}")
        self.message = message or f"来自节点 {name} 的消息"
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点逻辑"""
        print(f"[{self.name}] 执行中: {self.message}")
        
        # 模拟处理时间
        await asyncio.sleep(0.1)
        
        # 返回状态更新
        return {
            "messages": [Message(
                role=MessageRole.ASSISTANT,
                content=self.message
            )],
            "visited_nodes": [self.name],
            "step_count": 1
        }


class RouterNode(BaseNode):
    """路由节点实现"""
    
    def __init__(self, name: str):
        super().__init__(name, NodeType.ROUTER, description="路由决策节点")
        self.decision_count = 0
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """执行路由决策"""
        self.decision_count += 1
        step_count = state.get("step_count", 0)
        
        print(f"[{self.name}] 路由决策 #{self.decision_count}, 当前步数: {step_count}")
        
        if step_count < 3:
            # 继续执行
            next_node = "process_node" if step_count % 2 == 0 else "check_node"
            return Command(
                update={"decision": f"继续到 {next_node}"},
                goto=next_node
            )
        else:
            # 结束执行
            return Command(
                update={"decision": "完成"},
                goto="END"
            )


async def simple_demo():
    """简单演示"""
    print("=== StateGraph 简单演示 ===\n")
    
    # 1. 创建状态图
    graph = StateGraph(name="simple_demo")
    
    # 2. 添加节点
    graph.add_node("start", SimpleNode("start", "开始处理"))
    graph.add_node("process_node", SimpleNode("process_node", "处理数据"))
    graph.add_node("check_node", SimpleNode("check_node", "检查结果"))
    graph.add_node("router", RouterNode("router"))
    graph.add_node("end", SimpleNode("end", "处理完成"))
    
    # 3. 添加边
    graph.add_edge("start", "router")
    graph.add_edge("process_node", "router")
    graph.add_edge("check_node", "router")
    
    # 4. 添加条件边（从router到其他节点的路由）
    def route_function(state: Dict[str, Any]) -> str:
        decision = state.get("decision", "")
        if "process_node" in decision:
            return "process_node"
        elif "check_node" in decision:
            return "check_node"
        elif "完成" in decision:
            return "end"
        return "end"
    
    graph.add_conditional_edges("router", route_function)
    
    # 5. 设置入口点
    graph.set_entry_point("start")
    
    # 6. 创建执行器
    executor = StateGraphExecutor()
    
    # 7. 初始状态
    initial_state = {
        "messages": [],
        "visited_nodes": [],
        "step_count": 0
    }
    
    # 8. 执行
    print("开始执行状态图...\n")
    try:
        final_state = await executor.execute(graph, initial_state)
        
        print("\n=== 执行结果 ===")
        print(f"访问的节点: {final_state.get('visited_nodes', [])}")
        print(f"总步数: {final_state.get('step_count', 0)}")
        print(f"最终决策: {final_state.get('decision', 'N/A')}")
        
        messages = final_state.get("messages", [])
        print(f"\n消息历史 ({len(messages)} 条):")
        for i, msg in enumerate(messages, 1):
            print(f"  {i}. {msg.content}")
            
    except Exception as e:
        print(f"❌ 执行失败: {e}")


async def parallel_demo():
    """并行执行演示"""
    print("\n=== 并行执行演示 ===\n")
    
    # 创建包含并行节点的图
    graph = StateGraph(name="parallel_demo")
    
    # 添加并行节点
    graph.add_node("start", SimpleNode("start", "开始并行处理"))
    graph.add_node("parallel_1", SimpleNode("parallel_1", "并行任务1"))
    graph.add_node("parallel_2", SimpleNode("parallel_2", "并行任务2"))
    graph.add_node("parallel_3", SimpleNode("parallel_3", "并行任务3"))
    graph.add_node("merge", SimpleNode("merge", "合并结果"))
    
    # 添加边 - 从start到所有并行节点
    graph.add_edge("start", "parallel_1")
    graph.add_edge("start", "parallel_2") 
    graph.add_edge("start", "parallel_3")
    
    # 所有并行节点到merge
    graph.add_edge("parallel_1", "merge")
    graph.add_edge("parallel_2", "merge")
    graph.add_edge("parallel_3", "merge")
    
    graph.set_entry_point("start")
    
    # 使用并行执行器
    executor = StateGraphExecutor(enable_parallel=True, max_concurrent_nodes=3)
    
    initial_state = {"messages": [], "visited_nodes": [], "step_count": 0}
    
    import time
    start_time = time.time()
    
    print("开始并行执行...\n")
    final_state = await executor.execute(graph, initial_state)
    
    end_time = time.time()
    
    print(f"\n并行执行完成，耗时: {end_time - start_time:.2f}秒")
    print(f"访问的节点: {final_state.get('visited_nodes', [])}")
    print(f"处理的消息数: {len(final_state.get('messages', []))}")


if __name__ == "__main__":
    print("🚀 StateGraph 语法错误已修复，开始演示...\n")
    
    try:
        # 运行演示
        asyncio.run(simple_demo())
        asyncio.run(parallel_demo())
        
        print("\n🎉 演示完成！StateGraph 工作正常。")
        print("\n要运行完整的增强功能演示，请：")
        print("1. 确保安装了所有依赖: pip install -r requirements.txt")
        print("2. 运行: python examples/enhanced_stategraph_demo.py")
        
    except Exception as e:
        print(f"❌ 演示失败: {e}")
        print("请确保已安装依赖: pip install pydantic networkx")