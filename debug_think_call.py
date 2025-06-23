#!/usr/bin/env python3
"""
调试DeepSeek R1推理功能调用问题
"""
import asyncio
import os
import sys
import traceback

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_basic_imports():
    """测试基础导入"""
    print("🔍 测试基础导入...")
    try:
        from llm.doubao import DoubaoLLM
        from core.types import LLMConfig, Message, MessageRole
        print("✅ 基础导入成功")
        return True
    except Exception as e:
        print(f"❌ 基础导入失败: {e}")
        traceback.print_exc()
        return False

def test_llm_creation():
    """测试LLM实例创建"""
    print("\n🔍 测试LLM实例创建...")
    try:
        from llm.doubao import DoubaoLLM
        from core.types import LLMConfig
        
        config = LLMConfig(
            provider="doubao",
            model_name="test",
            api_key="test_key",
            temperature=0.6,
            max_tokens=1000
        )
        
        llm = DoubaoLLM(config)
        print("✅ LLM实例创建成功")
        print(f"   - 配置: {config}")
        print(f"   - LLM类型: {type(llm)}")
        print(f"   - 有think方法: {hasattr(llm, 'think')}")
        print(f"   - 有stream_think方法: {hasattr(llm, 'stream_think')}")
        return llm
    except Exception as e:
        print(f"❌ LLM实例创建失败: {e}")
        traceback.print_exc()
        return None

async def test_think_method_signature(llm):
    """测试think方法签名"""
    print("\n🔍 测试think方法签名...")
    try:
        from core.types import Message, MessageRole
        
        # 创建测试消息
        messages = [Message(role=MessageRole.USER, content="测试消息")]
        print(f"✅ 测试消息创建成功: {messages}")
        
        # 检查think方法
        think_method = getattr(llm, 'think', None)
        if think_method:
            print(f"✅ think方法存在: {think_method}")
            print(f"   - 方法类型: {type(think_method)}")
            print(f"   - 是否可调用: {callable(think_method)}")
            
            # 尝试获取方法签名
            import inspect
            sig = inspect.signature(think_method)
            print(f"   - 方法签名: {sig}")
            
            return True
        else:
            print("❌ think方法不存在")
            return False
            
    except Exception as e:
        print(f"❌ think方法签名测试失败: {e}")
        traceback.print_exc()
        return False

async def test_mock_think_call(llm):
    """测试模拟think调用（不需要真实API）"""
    print("\n🔍 测试模拟think调用...")
    try:
        from core.types import Message, MessageRole
        
        # 创建测试消息
        messages = [Message(role=MessageRole.USER, content="测试消息")]
        
        # 尝试调用think方法（会因为没有API密钥而失败，但可以检查调用路径）
        print("📞 尝试调用think方法...")
        try:
            result = await llm.think(messages)
            print(f"✅ think调用成功（意外）: {result}")
            return True
        except ValueError as ve:
            if "API密钥" in str(ve):
                print(f"✅ think调用路径正常（预期的API密钥错误）: {ve}")
                return True
            else:
                print(f"❌ think调用失败（非预期错误）: {ve}")
                return False
        except Exception as e:
            print(f"❌ think调用失败（其他错误）: {e}")
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ 模拟think调用测试失败: {e}")
        traceback.print_exc()
        return False

async def test_stream_react_node():
    """测试StreamReactAgentNode"""
    print("\n🔍 测试StreamReactAgentNode...")
    try:
        from nodes.stream_react_agent_node import StreamReactAgentNode
        from llm.doubao import DoubaoLLM
        from core.types import LLMConfig
        
        # 创建LLM配置
        config = LLMConfig(
            provider="doubao",
            model_name="test",
            api_key="test_key"
        )
        llm = DoubaoLLM(config)
        
        # 创建节点
        node = StreamReactAgentNode("test_node", llm)
        print("✅ StreamReactAgentNode创建成功")
        print(f"   - 节点名称: {node.name}")
        print(f"   - 节点类型: {node.node_type}")
        print(f"   - LLM类型: {type(node.llm)}")
        print(f"   - LLM支持推理: {hasattr(node.llm, 'stream_think')}")
        
        return True
        
    except Exception as e:
        print(f"❌ StreamReactAgentNode测试失败: {e}")
        traceback.print_exc()
        return False

async def test_react_agent():
    """测试ReactAgent"""
    print("\n🔍 测试ReactAgent...")
    try:
        from agents.react_agent import ReactAgent
        from llm.doubao import DoubaoLLM
        from core.types import LLMConfig
        
        # 创建LLM配置
        config = LLMConfig(
            provider="doubao",
            model_name="test",
            api_key="test_key"
        )
        llm = DoubaoLLM(config)
        
        # 创建Agent
        agent = ReactAgent(llm=llm)
        print("✅ ReactAgent创建成功")
        print(f"   - Agent类型: {agent.agent_type}")
        print(f"   - LLM类型: {type(agent.llm)}")
        
        # 测试图构建
        graph = agent.build_graph(use_stream=True)
        print(f"✅ 流式图构建成功")
        print(f"   - 节点数量: {len(graph.nodes)}")
        print(f"   - 节点列表: {list(graph.nodes.keys())}")
        
        # 检查流式节点
        if "agent" in graph.nodes:
            stream_node = graph.nodes["agent"]
            print(f"   - 流式节点类型: {type(stream_node)}")
            print(f"   - 支持推理: {hasattr(stream_node.llm, 'stream_think')}")
        
        return True
        
    except Exception as e:
        print(f"❌ ReactAgent测试失败: {e}")
        traceback.print_exc()
        return False

def test_environment_variables():
    """测试环境变量"""
    print("\n🔍 测试环境变量...")
    
    env_vars = {
        "ARK_API_KEY": os.getenv('ARK_API_KEY'),
        "DOUBAO_API_KEY": os.getenv('DOUBAO_API_KEY'),
        "DOUBAO_MODEL_DEEPSEEKR1": os.getenv('DOUBAO_MODEL_DEEPSEEKR1', 'deepseek-reasoner (默认)'),
        "DOUBAO_BASE_URL": os.getenv('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3 (默认)')
    }
    
    for key, value in env_vars.items():
        if value:
            if "API_KEY" in key:
                print(f"✅ {key}: {'*' * 10}...{value[-4:] if len(value) > 4 else '****'}")
            else:
                print(f"✅ {key}: {value}")
        else:
            print(f"❌ {key}: 未设置")
    
    has_api_key = bool(env_vars["ARK_API_KEY"] or env_vars["DOUBAO_API_KEY"])
    return has_api_key

async def main():
    """主函数"""
    print("🚀 DeepSeek R1推理功能调用调试")
    print("=" * 60)
    
    # 测试步骤
    steps = [
        ("环境变量检查", test_environment_variables),
        ("基础导入", test_basic_imports),
    ]
    
    # 运行同步测试
    results = []
    llm = None
    
    for step_name, test_func in steps:
        print(f"\n📋 {step_name}:")
        try:
            if step_name == "基础导入":
                result = test_func()
                results.append(result)
                if result:
                    llm = test_llm_creation()
                    results.append(bool(llm))
            else:
                result = test_func()
                results.append(result)
        except Exception as e:
            print(f"❌ {step_name}失败: {e}")
            results.append(False)
    
    # 运行异步测试
    if llm:
        async_tests = [
            ("think方法签名", test_think_method_signature),
            ("模拟think调用", test_mock_think_call),
            ("StreamReactAgentNode", test_stream_react_node),
            ("ReactAgent", test_react_agent),
        ]
        
        for step_name, test_func in async_tests:
            print(f"\n📋 {step_name}:")
            try:
                if step_name in ["think方法签名", "模拟think调用"]:
                    result = await test_func(llm)
                else:
                    result = await test_func()
                results.append(result)
            except Exception as e:
                print(f"❌ {step_name}失败: {e}")
                traceback.print_exc()
                results.append(False)
    
    # 总结结果
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 60)
    print(f"📊 调试结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！推理功能集成正常！")
        print("\n💡 如果调用仍然没有反应，请检查：")
        print("1. API密钥是否正确设置")
        print("2. 网络连接是否正常")
        print("3. 模型名称是否正确（DOUBAO_MODEL_DEEPSEEKR1）")
        print("4. 是否在正确的异步上下文中调用")
    else:
        print("⚠️ 部分测试失败，请检查具体错误信息")
    
    return passed == total

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        traceback.print_exc()
        sys.exit(1) 