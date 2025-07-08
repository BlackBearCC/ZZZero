#!/usr/bin/env python3
"""
演示修复后的逻辑 - 不依赖外部库
"""

import asyncio
from typing import Dict, Any, List, Union
from dataclasses import dataclass
from enum import Enum


class NodeType(Enum):
    CUSTOM = "custom"
    ROUTER = "router"


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    role: MessageRole
    content: str


class Command:
    def __init__(self, update: Dict[str, Any] = None, goto: Union[str, List[str]] = None):
        self.update = update or {}
        self.goto = goto


class MockNode:
    """模拟节点类"""
    def __init__(self, name: str, node_type: NodeType):
        self.name = name
        self.node_type = node_type


class ExampleNode(MockNode):
    """示例节点实现"""
    
    def __init__(self, name: str, processing_time: float = 1.0):
        super().__init__(name, NodeType.CUSTOM)
        self.processing_time = processing_time
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行节点逻辑"""
        print(f"[{self.name}] 开始处理，processing_time={self.processing_time}s")
        
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


class ConditionalNode(MockNode):
    """条件节点实现 - 修复后的版本"""
    
    def __init__(self, name: str):
        super().__init__(name, NodeType.ROUTER)
        self.call_count = 0
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """执行条件判断"""
        self.call_count += 1
        processing_count = state.get("processing_count", 0)
        
        print(f"[{self.name}] 调用次数: {self.call_count}, 当前处理次数: {processing_count}")
        
        if processing_count < 2:
            # 发送到并行节点
            print(f"[{self.name}] 决策: 发送到并行节点")
            return Command(
                update={"decision": "parallel"},
                goto=["parallel_node_1", "parallel_node_2"]
            )
        else:
            # 结束处理
            print(f"[{self.name}] 决策: 发送到最终节点")
            return Command(
                update={"decision": "finish"},
                goto="final_node"
            )


class OldConditionalNode(MockNode):
    """原始有问题的条件节点"""
    
    def __init__(self, name: str):
        super().__init__(name, NodeType.ROUTER)
        self.call_count = 0
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """原始的有问题的执行逻辑"""
        self.call_count += 1
        processing_count = state.get("processing_count", 0)
        
        print(f"[旧版本-{self.name}] 调用次数: {self.call_count}, 处理次数: {processing_count}")
        
        if processing_count < 3:
            # 问题：总是返回到自己，造成无限循环
            print(f"[旧版本-{self.name}] 决策: 继续处理 (会导致无限循环)")
            return Command(
                update={"decision": "continue"},
                goto=["parallel_node_1", "parallel_node_2"]  # 这里的逻辑有问题
            )
        else:
            print(f"[旧版本-{self.name}] 决策: 结束")
            return Command(
                update={"decision": "finish"},
                goto="END"
            )


def old_route_function(state: Dict[str, Any]) -> str:
    """原始有问题的路由函数"""
    decision = state.get("decision", "continue")
    print(f"[旧路由函数] decision={decision}")
    if decision == "continue":
        return "conditional_node"  # 问题：总是返回到conditional_node，造成循环
    else:
        return "END"


def new_route_function(state: Dict[str, Any]) -> str:
    """修复后的路由函数"""
    decision = state.get("decision", "continue")
    print(f"[新路由函数] decision={decision}")
    if decision == "parallel":
        return "parallel_nodes"  # 去并行节点
    elif decision == "finish":
        return "final_node"      # 去最终节点
    else:
        return "END"


async def demonstrate_problem():
    """演示原始问题"""
    print("=== 🐛 演示原始问题 ===\n")
    
    # 模拟原始的有问题的执行流程
    old_node = OldConditionalNode("conditional_node")
    
    state = {"processing_count": 0}
    
    print("模拟原始问题的执行流程:")
    for i in range(5):  # 模拟5次循环
        print(f"\n--- 迭代 {i+1} ---")
        
        command = await old_node.execute(state)
        print(f"返回的命令: goto={command.goto}")
        
        # 模拟路由函数
        route_result = old_route_function(command.update)
        print(f"路由结果: {route_result}")
        
        if route_result == "conditional_node":
            print("❌ 又回到了conditional_node - 形成无限循环！")
        else:
            print("✅ 正常退出")
            break
        
        # 更新状态（但没有真正处理，所以processing_count不变）
        state.update(command.update)


async def demonstrate_fix():
    """演示修复后的版本"""
    print("\n=== ✅ 演示修复后的版本 ===\n")
    
    # 创建修复后的节点
    new_node = ConditionalNode("conditional_node")
    
    state = {"processing_count": 0}
    
    print("修复后的执行流程:")
    for i in range(5):
        print(f"\n--- 迭代 {i+1} ---")
        
        command = await new_node.execute(state)
        print(f"返回的命令: goto={command.goto}")
        
        # 模拟路由
        route_result = new_route_function(command.update)
        print(f"路由结果: {route_result}")
        
        if route_result == "parallel_nodes":
            print("✅ 正确路由到并行节点")
            # 模拟并行节点处理
            state["processing_count"] += 1
            print(f"模拟并行处理完成，processing_count={state['processing_count']}")
        elif route_result == "final_node":
            print("✅ 正确路由到最终节点，流程结束")
            break
        else:
            print("✅ 流程结束")
            break
        
        # 更新状态
        state.update(command.update)


async def demonstrate_parallel_structure():
    """演示并行结构"""
    print("\n=== ⚡ 演示并行执行结构 ===\n")
    
    # 创建并行节点
    nodes = [
        ExampleNode("parallel_1", 1.0),
        ExampleNode("parallel_2", 1.5), 
        ExampleNode("parallel_3", 0.8)
    ]
    
    print("串行执行时间:")
    start_time = asyncio.get_event_loop().time()
    for node in nodes:
        await node.execute({})
    serial_time = asyncio.get_event_loop().time() - start_time
    print(f"串行总时间: {serial_time:.2f}秒")
    
    print("\n并行执行时间:")
    start_time = asyncio.get_event_loop().time()
    
    # 模拟并行执行
    tasks = [node.execute({}) for node in nodes]
    await asyncio.gather(*tasks)
    
    parallel_time = asyncio.get_event_loop().time() - start_time
    print(f"并行总时间: {parallel_time:.2f}秒")
    
    print(f"\n性能提升: {(serial_time - parallel_time) / serial_time * 100:.1f}%")


async def main():
    """主演示函数"""
    print("🚀 StateGraph 问题修复演示\n")
    print("=" * 50)
    
    await demonstrate_problem()
    await demonstrate_fix()
    await demonstrate_parallel_structure()
    
    print("\n" + "=" * 50)
    print("🎉 演示完成！")
    print("\n📋 修复总结:")
    print("1. ✅ 修复了无限循环 - 改进路由逻辑")
    print("2. ✅ 优化了状态流转 - 正确的节点跳转")
    print("3. ✅ 提升了并行性能 - 真正的并行执行")
    print("4. ✅ 增强了可调试性 - 更清晰的日志")


if __name__ == "__main__":
    asyncio.run(main())