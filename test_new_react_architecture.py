"""
测试新的ReAct分离式架构
"""
import asyncio
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'src'))

from src.agents.react_agent import ReactAgent
from src.llm.doubao import DoubaoLLM
from src.tools.mcp_tools import MCPToolManager


async def test_new_react_architecture():
    """测试新的ReAct分离式架构"""
    print("=" * 60)
    print("测试新的ReAct分离式架构")
    print("=" * 60)
    
    # 初始化LLM
    from src.core.types import LLMConfig
    config = LLMConfig(provider="doubao", model_name="ep-20250221154410-vh78x", timeout=60)
    llm = DoubaoLLM(config)
    await llm.initialize()
    
    # 初始化工具管理器（可选）
    tool_manager = None
    try:
        tool_manager = MCPToolManager()
        await tool_manager.initialize()
        print(f"✅ 工具管理器初始化成功，可用工具: {tool_manager.list_tools()}")
    except Exception as e:
        print(f"⚠️ 工具管理器初始化失败: {e}")
        print("将使用无工具模式进行测试")
    
    # 创建ReactAgent
    agent = ReactAgent(
        llm=llm,
        tool_manager=tool_manager,
        max_iterations=3,
        memory_enabled=False  # 暂时禁用记忆以简化测试
    )
    
    # 测试查询
    test_queries = [
        "你好，请介绍一下你自己",
        "2+3等于多少？请解释计算过程",
    ]
    
    # 如果有工具可用，添加需要工具的测试
    if tool_manager and tool_manager.list_tools():
        test_queries.append("请帮我搜索一些角色信息")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- 测试 {i}: {query} ---")
        
        try:
            # 测试标准模式（使用新的分离式架构）
            print("\n🔍 使用新的分离式ReAct架构:")
            result = await agent.run(query)
            
            print(f"✅ 执行成功: {result.success}")
            print(f"📊 指标: {result.metrics}")
            print(f"🔄 执行轨迹: {len(result.execution_trace)} 个节点")
            
            # 显示执行轨迹
            for j, trace in enumerate(result.execution_trace):
                print(f"  {j+1}. {trace['node']} ({trace['type']}) - {trace['state']} - {trace['duration']:.2f}s")
            
            print(f"📝 最终回答:")
            print(f"{result.result}")
            
            # 测试流式模式（使用原有的流式节点）
            print(f"\n🌊 使用流式模式:")
            chunks = []
            async for chunk in agent.stream_run(query):
                chunks.append(chunk)
                if chunk["type"] in ["text_chunk", "final_result"]:
                    print(f"  [{chunk['type']}] {chunk['content'][:100]}...")
            
            print(f"📊 流式块数: {len(chunks)}")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 清理资源
    try:
        await agent.cleanup()
        print("\n✅ 资源清理完成")
    except Exception as e:
        print(f"⚠️ 清理失败: {e}")


async def test_individual_nodes():
    """测试各个独立节点"""
    print("\n" + "=" * 60)
    print("测试各个独立节点")
    print("=" * 60)
    
    from src.llm.doubao import DoubaoLLM
    from src.nodes.thought_node import ThoughtNode
    from src.nodes.action_node import ActionNode
    from src.nodes.observation_node import ObservationNode
    from src.nodes.final_answer_node import FinalAnswerNode
    from src.core.types import NodeInput, ExecutionContext, Message, MessageRole
    
    # 初始化LLM
    from src.core.types import LLMConfig
    config = LLMConfig(provider="doubao", model_name="ep-20250221154410-vh78x", timeout=60)
    llm = DoubaoLLM(config)
    await llm.initialize()
    
    # 创建测试上下文
    context = ExecutionContext(
        task_id="test_task",
        agent_type="react",
        available_tools=[],
        messages=[
            Message(role=MessageRole.USER, content="2+3等于多少？请详细解释")
        ],
        variables={}
    )
    
    # 测试思考节点
    print("\n🧠 测试思考节点:")
    thought_node = ThoughtNode("thought_test", llm)
    node_input = NodeInput(context=context, previous_output=None, parameters={})
    
    try:
        thought_output = await thought_node.execute(node_input)
        print(f"✅ 思考节点执行成功")
        print(f"📝 思考内容: {thought_output.data.get('thought', '')[:200]}...")
        print(f"🔧 需要工具: {thought_output.data.get('needs_tools', False)}")
        print(f"➡️ 下一个节点: {thought_output.next_node}")
    except Exception as e:
        print(f"❌ 思考节点失败: {e}")
    
    # 测试最终答案节点
    print("\n📋 测试最终答案节点:")
    final_node = FinalAnswerNode("final_test", llm)
    
    # 添加一些思考历史到上下文
    context.messages.append(Message(
        role=MessageRole.ASSISTANT,
        content="思考：这是一个简单的数学计算问题，2+3=5",
        metadata={"node_type": "thought"}
    ))
    
    try:
        final_output = await final_node.execute(node_input)
        print(f"✅ 最终答案节点执行成功")
        print(f"📝 最终答案: {final_output.data.get('final_answer', '')}")
        print(f"🔚 是否完成: {final_output.data.get('is_complete', False)}")
        print(f"➡️ 下一个节点: {final_output.next_node}")
    except Exception as e:
        print(f"❌ 最终答案节点失败: {e}")
    
    await llm.cleanup()


if __name__ == "__main__":
    asyncio.run(test_new_react_architecture())
    asyncio.run(test_individual_nodes()) 