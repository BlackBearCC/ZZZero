# -*- coding: utf-8 -*-
"""
ZZZero AI Agent Framework 简化版主入口
用于测试核心功能，跳过复杂的依赖
"""
import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加src路径
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

def setup_environment():
    """设置环境变量"""
    # 加载.env文件
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
        print("[成功] 环境变量加载完成")
    else:
        print("[警告] .env文件不存在，使用默认配置")

async def test_core_components():
    """测试核心组件"""
    try:
        print("=== 测试核心组件 ===")
        
        # 测试基础类型
        from core.types import Message, MessageRole, LLMConfig
        print("[成功] 核心类型模块加载完成")
        
        # 测试基础节点
        from core.base import BaseNode, NodeType
        print("[成功] 基础节点模块加载完成")
        
        # 测试图结构
        from core.graph import StateGraph, GraphBuilder
        print("[成功] 图结构模块加载完成")
        
        # 创建一个简单的测试图
        class TestNode(BaseNode):
            def __init__(self, name: str):
                super().__init__(name, NodeType.CUSTOM, "测试节点")
            
            async def execute(self, state):
                print(f"[执行] 测试节点 {self.name} 正在运行，接收状态: {state}")
                # 返回状态更新
                result = {"test_result": f"节点 {self.name} 执行完成", "processed_by": self.name}
                print(f"[返回] 节点 {self.name} 返回结果: {result}")
                return result
        
        # 构建测试图
        builder = GraphBuilder("test_graph")
        node1 = TestNode("test_node_1")
        node2 = TestNode("test_node_2")
        
        graph = (builder
                .add_node(node1)
                .add_node(node2)
                .connect("test_node_1", "test_node_2")
                .entry("test_node_1")
                .build())
        
        print("[成功] 测试图构建完成")
        print(f"[信息] 图包含节点: {list(graph.nodes.keys())}")
        
        # 编译并执行图
        compiled_graph = graph.compile()
        initial_state = {"input": "测试输入"}
        result = await compiled_graph.invoke(initial_state)
        
        print("[成功] 图执行完成")
        print(f"[结果] 最终状态: {result}")
        
        return True
        
    except Exception as e:
        print(f"[错误] 核心组件测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_llm_modules():
    """测试LLM模块"""
    try:
        print("\n=== 测试LLM模块 ===")
        
        # 测试LLM基类
        from llm.base import BaseLLMProvider, LLMFactory
        print("[成功] LLM基类模块加载完成")
        
        # 测试具体LLM实现
        try:
            from llm.openai import OpenAILLM
            print("[成功] OpenAI模块加载完成")
        except Exception as e:
            print(f"[警告] OpenAI模块加载失败: {e}")
        
        try:
            from llm.doubao import DoubaoLLM
            print("[成功] 豆包模块加载完成")
        except Exception as e:
            print(f"[警告] 豆包模块加载失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"[错误] LLM模块测试失败: {e}")
        return False

async def test_mcp_modules():
    """测试MCP模块"""
    try:
        print("\n=== 测试MCP模块 ===")
        
        # 测试MCP基础类型
        from mcp.types import MCPMethods
        print("[成功] MCP类型模块加载完成")
        
        # 测试MCP客户端
        from mcp.client.base import BaseClient
        print("[成功] MCP客户端基类加载完成")
        
        # 测试MCP服务器
        from mcp.server.base import BaseServer
        print("[成功] MCP服务器基类加载完成")
        
        return True
        
    except Exception as e:
        print(f"[错误] MCP模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函数"""
    try:
        print("=== ZZZero AI Agent 简化版测试 ===")
        
        # 设置环境变量
        setup_environment()
        
        # 测试核心组件
        core_success = await test_core_components()
        
        # 测试LLM模块
        llm_success = await test_llm_modules()
        
        # 测试MCP模块
        mcp_success = await test_mcp_modules()
        
        # 汇总结果
        print("\n=== 测试结果汇总 ===")
        print(f"[结果] 核心组件: {'✓ 通过' if core_success else '✗ 失败'}")
        print(f"[结果] LLM模块: {'✓ 通过' if llm_success else '✗ 失败'}")
        print(f"[结果] MCP模块: {'✓ 通过' if mcp_success else '✗ 失败'}")
        
        if all([core_success, llm_success, mcp_success]):
            print("\n🎉 所有核心组件测试通过！框架基础功能正常。")
            print("💡 提示: 可以尝试安装完整依赖后启动完整版Web界面。")
        else:
            print("\n⚠️  部分组件测试失败，请检查依赖安装。")
        
    except KeyboardInterrupt:
        print("\n🔄 测试被用户中断")
    except Exception as e:
        print(f"\n[错误] 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[退出] 简化版测试完成")

if __name__ == "__main__":
    # 设置Windows异步事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())