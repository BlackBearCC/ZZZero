#!/usr/bin/env python3
"""
向量数据库功能测试脚本
测试plugins.py中的向量数据库和embedding功能
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# 添加项目路径到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.plugins import RoleKnowledgeBasePlugin, RolePluginManager

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_vector_db():
    """测试向量数据库功能"""
    print("🚀 开始测试向量数据库功能...")
    
    # 创建测试工作空间
    workspace_dir = "./test_workspace"
    os.makedirs(workspace_dir, exist_ok=True)
    
    # 创建测试数据文件
    test_file_path = f"{workspace_dir}/test_knowledge.txt"
    test_content = """
方知衡：基础人设
姓名：方知衡，英文名 Ordinis
性别：男
年龄：28岁
身高/体重：185cm/70kg
血型：A型
生日：1月19日
星座：摩羯座
职业：云枢大学天文系客座教授、博士

角色特征：
方知衡是一个秉持平等理念的人，无论面对伴侣、学生还是小孩，他都主张相互理解与尊重。
他性格温和，善于倾听，总是能够以平静的态度处理各种复杂的人际关系。

专业背景：
作为天文系的客座教授，方知衡在宇宙物理学方面有着深厚的造诣。
他的研究重点是宇宙物质的分布和演化，曾发表多篇高质量的学术论文。

兴趣爱好：
除了学术研究，方知衡还喜欢观星、摄影和阅读古典文学。
他经常在夜晚独自一人到郊外观察星空，这让他感到内心的平静。
    """
    
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"✅ 创建测试数据文件: {test_file_path}")
    
    try:
        # 1. 测试RoleKnowledgeBasePlugin
        print("\n📚 测试RoleKnowledgeBasePlugin...")
        
        plugin = RoleKnowledgeBasePlugin(workspace_dir)
        
        # 设置进度回调
        def progress_callback(progress):
            print(f"📊 {progress.current_step} - {progress.progress_percentage:.1f}% ({progress.processed_chunks}/{progress.total_chunks})")
        
        plugin.set_progress_callback(progress_callback)
        
        # 配置知识库
        await plugin.set_knowledge_base(
            name="测试知识库",
            source_file=test_file_path,
            description="用于测试的角色知识库",
            search_limit=5
        )
        
        print("✅ 知识库配置完成")
        
        # 检查是否可用
        is_available = await plugin.is_available()
        print(f"📋 知识库可用性: {is_available}")
        
        # 获取知识库信息
        info = plugin.get_knowledge_base_info()
        if info:
            print(f"📊 知识库信息:")
            print(f"  - 名称: {info['name']}")
            print(f"  - 数据条数: {info['data_count']}")
            print(f"  - 向量数量: {info.get('vector_count', 'N/A')}")
            print(f"  - 集合名称: {info['collection_name']}")
            print(f"  - Embedding模型: {info['embedding_model']}")
            
            progress_info = info.get('progress', {})
            if progress_info.get('error_message'):
                print(f"  ❌ 错误: {progress_info['error_message']}")
            elif progress_info.get('is_complete'):
                print(f"  ✅ 处理完成")
            else:
                print(f"  ⏳ 进度: {progress_info.get('progress_percentage', 0):.1f}%")
        
        # 2. 测试向量搜索
        print("\n🔍 测试向量搜索...")
        
        test_queries = [
            ["方知衡", "年龄"],
            ["天文", "教授"],
            ["兴趣", "爱好"],
            ["性格", "特征"],
            ["观星", "摄影"]
        ]
        
        for keywords in test_queries:
            print(f"\n🔎 搜索关键词: {keywords}")
            results = await plugin.search_knowledge(keywords, limit=3)
            
            if results:
                for i, result in enumerate(results, 1):
                    print(f"  结果 {i}:")
                    print(f"    相似度: {result['score']:.3f}")
                    print(f"    距离: {result['distance']:.3f}")
                    print(f"    内容: {result['content'][:100]}...")
                    print(f"    来源: {result['source']}")
            else:
                print("  未找到相关结果")
        
        # 3. 测试获取集合内容
        print("\n📄 测试获取集合内容...")
        contents = await plugin.get_collection_contents(limit=10)
        
        if contents:
            print(f"📚 集合包含 {len(contents)} 个文档片段:")
            for i, item in enumerate(contents[:3], 1):  # 只显示前3个
                print(f"  片段 {i}:")
                print(f"    ID: {item['id']}")
                print(f"    预览: {item['preview'][:80]}...")
                if item.get('metadata'):
                    metadata = item['metadata']
                    print(f"    来源索引: {metadata.get('source_index', 'N/A')}")
                    print(f"    块索引: {metadata.get('chunk_index', 'N/A')}")
        else:
            print("  集合为空")
        
        # 4. 测试RolePluginManager
        print("\n🎭 测试RolePluginManager...")
        
        manager = RolePluginManager(workspace_dir)
        
        # 配置知识库
        await manager.configure_knowledge_base(
            name="管理器测试知识库",
            source_file=test_file_path,
            description="通过管理器配置的测试知识库",
            search_limit=3,
            enabled=True
        )
        
        # 获取状态
        status = manager.get_status()
        kb_status = status['knowledge_base_plugin']
        
        print(f"📊 管理器状态:")
        print(f"  - 启用状态: {kb_status['enabled']}")
        print(f"  - 可用状态: {kb_status['available']}")
        
        if kb_status['info']:
            info = kb_status['info']
            print(f"  - 知识库名称: {info['name']}")
            print(f"  - 数据条数: {info['data_count']}")
        
        # 测试获取角色上下文
        print("\n🎯 测试获取角色上下文...")
        context = await manager.get_role_context(keywords=["方知衡", "天文"])
        
        if 'knowledge' in context:
            knowledge_results = context['knowledge']
            print(f"📖 找到 {len(knowledge_results)} 个相关知识:")
            for i, result in enumerate(knowledge_results, 1):
                print(f"  知识 {i}: {result['content'][:60]}...")
        else:
            print("  未找到相关知识")
        
        print("\n🎉 所有测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理测试文件
        try:
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
            print(f"🧹 清理测试文件: {test_file_path}")
        except Exception as e:
            print(f"⚠️ 清理失败: {e}")


if __name__ == "__main__":
    # 检查依赖
    try:
        import chromadb
        import sentence_transformers
        print("✅ 依赖检查通过")
    except ImportError as e:
        print(f"❌ 依赖缺失: {e}")
        print("请运行: pip install chromadb sentence-transformers")
        sys.exit(1)
    
    # 运行测试
    asyncio.run(test_vector_db()) 