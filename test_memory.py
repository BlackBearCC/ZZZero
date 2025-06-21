"""
记忆系统测试脚本
测试记忆的保存、检索、压缩等功能
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.memory import MemoryManager, SQLiteMemoryStore
from core.types import LLMConfig
from llm.base import LLMFactory

async def test_memory_system():
    """测试记忆系统"""
    print("🧠 开始测试记忆系统...")
    
    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # 1. 初始化组件
        print("\n📋 初始化测试组件...")
        
        # 创建LLM配置
        llm_config = LLMConfig(
            provider="doubao",
            model_name="ep-20250221154410-vh78x",
            temperature=0.7
        )
        
        # 创建LLM实例
        llm = LLMFactory.create(llm_config)
        await llm.initialize()
        print("✅ LLM初始化完成")
        
        # 创建记忆存储
        memory_store = SQLiteMemoryStore(db_path)
        print("✅ 记忆存储初始化完成")
        
        # 创建记忆管理器
        memory_manager = MemoryManager(
            llm=llm,
            store=memory_store,
            short_term_limit=500,  # 设置较小的限制以便测试压缩
            session_id="test_session_001"
        )
        print("✅ 记忆管理器初始化完成")
        
        # 2. 测试对话保存
        print("\n💬 测试对话保存...")
        
        conversations = [
            ("你好，我是张三，今年25岁", "你好张三！很高兴认识你。有什么我可以帮助你的吗？"),
            ("我想学习Python编程", "Python是一门很棒的编程语言！我可以为你推荐一些学习路径。"),
            ("我之前学过Java", "有Java基础对学习Python很有帮助，因为它们都是面向对象的语言。"),
            ("Python和Java有什么区别？", "Python语法更简洁，动态类型，而Java是静态类型，语法相对复杂一些。"),
            ("我想做数据分析", "Python在数据分析方面非常强大，有pandas、numpy等优秀的库。"),
            ("推荐一些学习资源", "我推荐《Python数据分析》这本书，还有Kaggle上的实战项目。"),
        ]
        
        for i, (user_msg, agent_msg) in enumerate(conversations, 1):
            success = await memory_manager.add_conversation(user_msg, agent_msg)
            print(f"  对话 {i}: {'✅ 保存成功' if success else '❌ 保存失败'}")
            
            # 获取当前统计
            stats = await memory_manager.get_stats()
            print(f"    短期记忆: {stats['short_term']['current_size']}/{stats['short_term']['limit']} 字符")
        
        # 3. 测试记忆检索
        print("\n🔍 测试记忆检索...")
        
        queries = [
            "张三的年龄",
            "Python学习",
            "数据分析",
            "Java和Python的区别"
        ]
        
        for query in queries:
            context = await memory_manager.get_context_for_query(query)
            print(f"  查询: {query}")
            if context:
                print(f"    找到相关记忆: {len(context)} 字符")
                # 只显示前100字符
                preview = context[:100].replace('\n', ' ')
                print(f"    预览: {preview}...")
            else:
                print(f"    未找到相关记忆")
        
        # 4. 测试记忆统计
        print("\n📊 记忆统计信息:")
        final_stats = await memory_manager.get_stats()
        print(f"  会话ID: {final_stats['session_id']}")
        print(f"  短期记忆: {final_stats['short_term']['current_size']}/{final_stats['short_term']['limit']} 字符")
        print(f"  长期记忆: {final_stats['long_term']['total_memories']} 条记录")
        print(f"  总字符数: {final_stats['total_characters']}")
        
        if final_stats['long_term']['total_memories'] > 0:
            print(f"  对话记忆: {final_stats['long_term']['conversation_memories']} 条")
            print(f"  事实记忆: {final_stats['long_term']['fact_memories']} 条") 
            print(f"  压缩记忆: {final_stats['long_term']['compressed_memories']} 条")
            print(f"  平均重要性: {final_stats['long_term']['average_importance']:.2f}")
        
        # 5. 测试记忆导出
        print("\n📤 测试记忆导出...")
        export_data = await memory_manager.export_data()
        if export_data:
            print(f"  导出成功: {len(export_data['short_term_memory'])} 条短期记忆")
            print(f"            {len(export_data['long_term_memory'])} 条长期记忆")
            
            # 保存导出数据到文件
            import json
            export_file = "memory_export_test.json"
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            print(f"  导出数据已保存到: {export_file}")
        
        # 6. 测试记忆清空
        print("\n🗑️  测试记忆清空...")
        clear_success = await memory_manager.clear_all()
        print(f"  清空结果: {'✅ 成功' if clear_success else '❌ 失败'}")
        
        # 验证清空结果
        final_stats_after_clear = await memory_manager.get_stats()
        print(f"  清空后统计: 短期{final_stats_after_clear['short_term']['current_size']}字符, " +
              f"长期{final_stats_after_clear['long_term']['total_memories']}条记录")
        
        print("\n🎉 记忆系统测试完成！")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 清理临时文件
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
                print(f"🧹 已清理临时数据库: {db_path}")
        except Exception as e:
            print(f"⚠️  清理临时文件失败: {e}")

async def test_compression_mechanism():
    """专门测试压缩机制"""
    print("\n🗜️  测试记忆压缩机制...")
    
    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # 初始化组件
        llm_config = LLMConfig(
            provider="doubao",
            model_name="ep-20250221154410-vh78x",
            temperature=0.7
        )
        
        llm = LLMFactory.create(llm_config)
        await llm.initialize()
        
        memory_store = SQLiteMemoryStore(db_path)
        memory_manager = MemoryManager(
            llm=llm,
            store=memory_store,
            short_term_limit=300,  # 更小的限制，强制触发压缩
            session_id="compression_test_session"
        )
        
        print("✅ 压缩测试环境初始化完成")
        
        # 添加足够多的对话以触发压缩
        long_conversations = [
            ("请详细介绍一下人工智能的发展历史", "人工智能的发展可以追溯到1950年代，当时图灵提出了著名的图灵测试..."),
            ("机器学习和深度学习有什么区别？", "机器学习是人工智能的一个分支，而深度学习是机器学习的一个子集..."),
            ("什么是神经网络？", "神经网络是模仿人脑神经元工作方式的计算模型，由多个相互连接的节点组成..."),
            ("卷积神经网络的原理是什么？", "卷积神经网络(CNN)特别适用于图像处理，通过卷积层、池化层等结构提取特征..."),
            ("自然语言处理的主要任务有哪些？", "自然语言处理包括文本分类、情感分析、机器翻译、问答系统等多个任务..."),
        ]
        
        print("\n📝 添加对话以触发压缩...")
        for i, (user_msg, agent_msg) in enumerate(long_conversations, 1):
            print(f"  添加对话 {i}...")
            success = await memory_manager.add_conversation(user_msg, agent_msg)
            
            stats = await memory_manager.get_stats()
            print(f"    短期记忆: {stats['short_term']['current_size']}/{stats['short_term']['limit']} 字符")
            print(f"    长期记忆: {stats['long_term']['total_memories']} 条")
            
            if stats['long_term']['compressed_memories'] > 0:
                print(f"    🗜️  检测到压缩记忆: {stats['long_term']['compressed_memories']} 条")
        
        # 最终统计
        final_stats = await memory_manager.get_stats()
        print(f"\n📊 压缩测试最终统计:")
        print(f"  压缩记忆: {final_stats['long_term']['compressed_memories']} 条")
        print(f"  事实记忆: {final_stats['long_term']['fact_memories']} 条")
        print(f"  对话记忆: {final_stats['long_term']['conversation_memories']} 条")
        
        # 测试压缩后的检索
        print(f"\n🔍 测试压缩后的记忆检索...")
        test_queries = ["人工智能发展", "神经网络", "机器学习"]
        
        for query in test_queries:
            context = await memory_manager.get_context_for_query(query)
            if context:
                print(f"  查询 '{query}': 找到 {len(context)} 字符的相关记忆")
            else:
                print(f"  查询 '{query}': 未找到相关记忆")
        
        print("✅ 压缩机制测试完成")
        
    except Exception as e:
        print(f"❌ 压缩测试失败: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 清理
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass

if __name__ == "__main__":
    print("🚀 启动记忆系统测试...")
    
    # 运行基础测试
    asyncio.run(test_memory_system())
    
    # 运行压缩测试
    asyncio.run(test_compression_mechanism())
    
    print("\n✨ 所有测试完成！") 