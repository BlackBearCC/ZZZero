#!/usr/bin/env python3
import sys
import os

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def main():
    print("🚀 简单调试测试")
    
    # 测试导入
    try:
        from llm.doubao import DoubaoLLM
        print("✅ DoubaoLLM导入成功")
    except Exception as e:
        print(f"❌ DoubaoLLM导入失败: {e}")
        return
    
    try:
        from core.types import LLMConfig
        print("✅ LLMConfig导入成功")
    except Exception as e:
        print(f"❌ LLMConfig导入失败: {e}")
        return
    
    # 测试LLM创建
    try:
        config = LLMConfig(
            provider="doubao",
            model_name="test",
            api_key="test_key"
        )
        llm = DoubaoLLM(config)
        print("✅ LLM实例创建成功")
        print(f"   - LLM类型: {type(llm)}")
        print(f"   - 有think方法: {hasattr(llm, 'think')}")
        print(f"   - 有stream_think方法: {hasattr(llm, 'stream_think')}")
        
        # 检查think方法的具体情况
        if hasattr(llm, 'think'):
            think_method = getattr(llm, 'think')
            print(f"   - think方法类型: {type(think_method)}")
            print(f"   - think方法可调用: {callable(think_method)}")
        
        if hasattr(llm, 'stream_think'):
            stream_think_method = getattr(llm, 'stream_think')
            print(f"   - stream_think方法类型: {type(stream_think_method)}")
            print(f"   - stream_think方法可调用: {callable(stream_think_method)}")
            
    except Exception as e:
        print(f"❌ LLM实例创建失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 测试StreamReactAgentNode导入
    try:
        from nodes.stream_react_agent_node import StreamReactAgentNode
        print("✅ StreamReactAgentNode导入成功")
        
        # 创建节点实例
        node = StreamReactAgentNode("test_node", llm)
        print("✅ StreamReactAgentNode实例创建成功")
        print(f"   - 节点名称: {node.name}")
        print(f"   - 节点LLM支持推理: {hasattr(node.llm, 'stream_think')}")
        
    except Exception as e:
        print(f"❌ StreamReactAgentNode测试失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 测试环境变量
    print("\n🔍 检查环境变量:")
    api_key = os.getenv('ARK_API_KEY') or os.getenv('DOUBAO_API_KEY')
    if api_key:
        print(f"✅ API密钥已设置: {'*' * 10}...{api_key[-4:]}")
    else:
        print("❌ API密钥未设置")
    
    deepseek_model = os.getenv('DOUBAO_MODEL_DEEPSEEKR1', 'deepseek-reasoner')
    print(f"✅ DeepSeek模型: {deepseek_model}")
    
    print("🎉 基本组件都正常！")

if __name__ == "__main__":
    main() 