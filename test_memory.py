"""
记忆系统全面测试脚本
测试记忆的保存、检索、压缩、事实提取等所有功能
"""
import asyncio
import os
import sys
import tempfile
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.memory import MemoryManager, SQLiteMemoryStore, MemoryCompressor
from core.types import LLMConfig, Message, MessageRole
from llm.base import LLMFactory

async def test_llm_connection():
    """测试LLM连接"""
    print("🔌 测试LLM连接...")
    
    try:
        # 创建LLM配置
        llm_config = LLMConfig(
            provider="doubao",
            model_name="ep-20250221154410-vh78x",
            temperature=0.7
        )
        
        # 创建LLM实例
        llm = LLMFactory.create(llm_config)
        await llm.initialize()
        
        # 测试简单调用
        test_message = Message(role=MessageRole.USER, content="你好，请回复'测试成功'")
        response = await llm.generate([test_message])
        
        print(f"✅ LLM连接成功，响应: {response.content[:50]}...")
        return llm
        
    except Exception as e:
        print(f"❌ LLM连接失败: {e}")
        raise

async def test_memory_compression():
    """专门测试记忆压缩功能"""
    print("\n🗜️  测试记忆压缩功能...")
    
    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # 初始化LLM
        llm = await test_llm_connection()
        
        # 创建压缩器
        compressor = MemoryCompressor(llm)
        
        # 准备测试对话
        test_conversations = [
            "用户: 你好，我叫李明，今年28岁，是一名软件工程师\n助手: 你好李明！很高兴认识你。作为软件工程师，你主要使用什么编程语言呢？",
            "用户: 我主要用Python和JavaScript，最近在学习机器学习\n助手: 很好的选择！Python在机器学习领域确实很强大，有pandas、scikit-learn等优秀库。",
            "用户: 对，我正在做一个推荐系统项目\n助手: 推荐系统很有意思！你是打算用协同过滤还是基于内容的推荐算法？",
            "用户: 我想试试深度学习的方法，用神经网络\n助手: 深度学习推荐系统确实效果不错，可以考虑使用嵌入层和多层感知机的组合。",
            "用户: 我最近在研究自然语言处理，想了解一些最新的技术\n助手: 自然语言处理是AI领域的热门方向，BERT、GPT等模型都很值得学习。",
            "用户: 是的，我也在关注这些\n助手: 对，BERT在NLP任务中表现很好，可以试试迁移学习的方法。"

        ]
        
        print(f"  原始对话数量: {len(test_conversations)}")
        original_length = sum(len(conv) for conv in test_conversations)
        print(f"  原始总长度: {original_length} 字符")
        
        # 执行压缩
        compressed_summary, facts = await compressor.compress_conversations(test_conversations)
        
        print(f"  压缩后摘要长度: {len(compressed_summary)} 字符")
        print(f"  压缩比: {len(compressed_summary)/original_length:.2%}")
        print(f"  提取事实数量: {len(facts)}")
        
        print("\n📝 压缩摘要:")
        print(f"  {compressed_summary}")
        
        print("\n📋 提取的事实:")
        for i, fact in enumerate(facts, 1):
            print(f"  {i}. {fact}")
        
        print("✅ 压缩功能测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 压缩功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # 清理临时文件
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass

async def test_memory_system_comprehensive():
    """全面测试记忆系统"""
    print("\n🧠 开始全面记忆系统测试...")
    
    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # 1. 初始化组件
        print("\n📋 初始化测试组件...")
        
        # 创建LLM实例
        llm = await test_llm_connection()
        
        # 创建记忆存储
        memory_store = SQLiteMemoryStore(db_path)
        print("✅ 记忆存储初始化完成")
        
        # 创建记忆管理器 - 设置更小的限制以触发压缩
        memory_manager = MemoryManager(
            llm=llm,
            store=memory_store,
            short_term_limit=200,  # 设置很小的限制，确保触发压缩
            session_id="comprehensive_test_session"
        )
        print("✅ 记忆管理器初始化完成")
        
        # 2. 测试逐步添加对话直到触发压缩
        print("\n💬 测试对话添加和压缩触发...")
        
        long_conversations = [
            ("你好，我是张三，今年25岁，在北京工作", "你好张三！很高兴认识你。在北京工作感觉怎么样？"),
            ("我在一家互联网公司做产品经理，工作很忙但很充实", "产品经理确实是个很有挑战性的职位，需要协调各方面的需求。"),
            ("是的，我每天要和开发、设计、运营等多个团队沟通", "跨团队协作确实需要很强的沟通能力，你是如何处理不同团队间的分歧的？"),
            ("我通常会先了解各方的核心关切，然后寻找平衡点", "这是很好的方法，理解各方需求是解决冲突的关键。"),
            ("对了，我最近在学习数据分析，想要更好地理解用户行为", "数据分析对产品经理来说确实很重要，可以帮助做出更科学的决策。"),
            ("你能推荐一些学习资源吗？", "我推荐《精益数据分析》这本书，还有Google Analytics的官方教程。"),
        ]
        
        for i, (user_msg, agent_msg) in enumerate(long_conversations, 1):
            print(f"\n  添加对话 {i}...")
            success = await memory_manager.add_conversation(user_msg, agent_msg)
            
            # 获取当前统计
            stats = await memory_manager.get_stats()
            print(f"    保存结果: {'✅ 成功' if success else '❌ 失败'}")
            print(f"    短期记忆: {stats['short_term']['current_size']}/{stats['short_term']['limit']} 字符")
            print(f"    长期记忆: {stats['long_term']['total_memories']} 条")
            
            if stats['long_term']['total_memories'] > 0:
                print(f"    🎉 检测到压缩触发！")
                print(f"    压缩记忆: {stats['long_term']['compressed_memories']} 条")
                print(f"    事实记忆: {stats['long_term']['fact_memories']} 条")
                break
        
        # 3. 测试记忆检索功能
        print("\n🔍 测试记忆检索功能...")
        
        queries = [
            "张三的个人信息",
            "产品经理工作",
            "数据分析学习",
            "团队协作方法"
        ]
        
        for query in queries:
            context = await memory_manager.get_context_for_query(query)
            print(f"  查询: {query}")
            if context:
                print(f"    找到相关记忆: {len(context)} 字符")
                # 显示前150字符
                preview = context[:150].replace('\n', ' ')
                print(f"    预览: {preview}...")
            else:
                print(f"    未找到相关记忆")
        
        # 4. 测试统计信息
        print("\n📊 最终记忆统计:")
        final_stats = await memory_manager.get_stats()
        print(f"  会话ID: {final_stats['session_id']}")
        print(f"  短期记忆: {final_stats['short_term']['current_size']}/{final_stats['short_term']['limit']} 字符")
        print(f"  长期记忆总数: {final_stats['long_term']['total_memories']} 条")
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
            
            # 保存详细导出数据
            import json
            export_file = "memory_comprehensive_test.json"
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            print(f"  详细导出数据已保存到: {export_file}")
        
        print("\n🎉 全面记忆系统测试完成！")
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # 清理临时文件
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
                print(f"🧹 已清理临时数据库: {db_path}")
        except Exception as e:
            print(f"⚠️  清理临时文件失败: {e}")

async def test_edge_cases():
    """测试边界情况"""
    print("\n🧪 测试边界情况...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        llm = await test_llm_connection()
        memory_store = SQLiteMemoryStore(db_path)
        memory_manager = MemoryManager(
            llm=llm,
            store=memory_store,
            short_term_limit=50,  # 极小的限制
            session_id="edge_case_test"
        )
        
        # 测试1: 空对话
        print("  测试空对话...")
        success = await memory_manager.add_conversation("", "")
        print(f"    空对话添加: {'✅ 成功' if success else '❌ 失败'}")
        
        # 测试2: 超长对话（预期失败）
        print("  测试超长对话...")
        long_user_msg = "这是一个非常长的用户消息，" * 20  # 约360字符
        long_agent_msg = "这是一个非常长的助手回复，" * 20  # 约360字符
        total_length = len(f"用户: {long_user_msg}\n助手: {long_agent_msg}")
        print(f"    超长对话长度: {total_length} 字符，限制: {memory_manager.short_term.limit} 字符")
        
        success = await memory_manager.add_conversation(long_user_msg, long_agent_msg)
        if total_length > memory_manager.short_term.limit:
            print(f"    超长对话添加: {'⚠️ 预期失败' if not success else '❌ 意外成功'}（单条对话超过容量限制）")
        else:
            print(f"    超长对话添加: {'✅ 成功' if success else '❌ 失败'}")
        
        # 测试2.1: 适中长度对话（应该成功）
        print("  测试适中长度对话...")
        medium_user_msg = "这是适中长度的消息"
        medium_agent_msg = "这是适中长度的回复"
        success = await memory_manager.add_conversation(medium_user_msg, medium_agent_msg)
        print(f"    适中对话添加: {'✅ 成功' if success else '❌ 失败'}")
        
        # 测试3: 特殊字符
        print("  测试特殊字符...")
        special_msg = "测试特殊字符：@#$%^&*(){}[]|\\:;\"'<>,.?/~`"
        success = await memory_manager.add_conversation(special_msg, "收到特殊字符")
        print(f"    特殊字符添加: {'✅ 成功' if success else '❌ 失败'}")
        
        # 测试4: 连续添加触发多次压缩
        print("  测试连续添加触发多次压缩...")
        for i in range(3):
            msg = f"连续测试消息{i+1}"
            success = await memory_manager.add_conversation(msg, f"收到消息{i+1}")
            print(f"    消息{i+1}添加: {'✅ 成功' if success else '❌ 失败'}")
        
        # 检查最终状态
        stats = await memory_manager.get_stats()
        print(f"  边界测试后统计: 短期{stats['short_term']['current_size']}字符, " +
              f"长期{stats['long_term']['total_memories']}条")
        
        print("✅ 边界情况测试完成")
        
    except Exception as e:
        print(f"❌ 边界测试失败: {e}")
        
    finally:
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass

if __name__ == "__main__":
    print("🚀 启动记忆系统全面测试...")
    
    async def run_all_tests():
        """运行所有测试"""
        # 测试1: LLM连接
        try:
            await test_llm_connection()
        except Exception as e:
            print(f"❌ LLM连接测试失败，跳过后续测试: {e}")
            return
        
        # 测试2: 压缩功能
        compression_success = await test_memory_compression()
        
        # 测试3: 全面系统测试
        system_success = await test_memory_system_comprehensive()
        
        # 测试4: 边界情况
        await test_edge_cases()
        
        # 总结
        print(f"\n✨ 测试总结:")
        print(f"  压缩功能: {'✅ 通过' if compression_success else '❌ 失败'}")
        print(f"  系统功能: {'✅ 通过' if system_success else '❌ 失败'}")
        print(f"  边界测试: ✅ 完成")
    
    # 运行所有测试
    asyncio.run(run_all_tests())
    
    print("\n🎯 所有测试完成！") 