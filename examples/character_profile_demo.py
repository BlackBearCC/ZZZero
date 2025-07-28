"""
角色资料生成工作流演示
展示如何使用向量知识库和角色资料生成功能
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.types import LLMConfig
from src.workflow.character_profile_workflow import CharacterProfileWorkflow
from src.tools.knowledge_base_manager import GlobalKnowledgeBase

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def demo_knowledge_base():
    """演示知识库基本功能"""
    print("\n=== 知识库演示 ===")
    
    # 初始化知识库
    kb = GlobalKnowledgeBase("./workspace")
    
    # 创建测试集合
    print("1. 创建测试知识集合...")
    success = await kb.create_collection(
        name="character_knowledge",
        description="角色相关知识库",
        metadata={"type": "character", "version": "1.0"}
    )
    print(f"创建结果: {'成功' if success else '失败'}")
    
    # 添加测试文档
    print("\n2. 添加测试知识...")
    test_documents = [
        """穆昭是一个22岁的神秘电竞高手，代号"J"。
        他有着黑发红瞳，短自来卷发，俊秀的少年脸型。
        性格上外热内冷，表面阳光大男孩，内在破坏欲很强。
        他是异端组织"大阿卡那"的成员，代号"愚者-Joker"。""",
        
        """穆昭的背景故事很复杂。7岁时全家为寻找"荒原弥赛亚"而落入陷阱，
        父母死亡，他被监察大厅捕获投入禁区。
        在禁区遇见女主，两人结伴逃亡10日，从提防到生死相托。
        最后一日，穆昭为救女主而死，被女主复活。""",
        
        """穆昭的技能包括编程、打游戏、赛车、户外运动。
        他有特殊的绝对治愈能力，源于女主权限的逆天修复能力。
        代表物是银手铐，象征立场制裁与生死承诺。
        颜色是暗红色，动物是黑猫，植物是洛丽玛丝玫瑰。"""
    ]
    
    success = await kb.add_documents(
        collection_name="character_knowledge",
        documents=test_documents,
        metadatas=[
            {"type": "basic_info", "character": "穆昭"},
            {"type": "background", "character": "穆昭"},
            {"type": "skills", "character": "穆昭"}
        ],
        auto_split=True
    )
    print(f"添加结果: {'成功' if success else '失败'}")
    
    # 测试查询
    print("\n3. 测试知识查询...")
    results = await kb.query_documents(
        collection_name="character_knowledge",
        query_text="穆昭 性格 特征",
        n_results=3
    )
    
    print(f"查询到 {len(results)} 个相关结果:")
    for i, result in enumerate(results, 1):
        print(f"  结果{i}: {result['document'][:100]}...")
        print(f"    相似度: {1-result['distance']:.3f}")
        print(f"    元数据: {result['metadata']}")
    
    # 列出集合
    print("\n4. 列出所有知识集合...")
    collections = kb.list_collections()
    for coll in collections:
        print(f"  - {coll.name}: {coll.description} ({coll.document_count} 个文档)")
    
    return kb

async def demo_character_profile_generation():
    """演示角色资料生成"""
    print("\n=== 角色资料生成演示 ===")
    
    # 检查是否有LLM配置
    llm_config = None
    try:
        # 尝试使用Doubao LLM
        llm_config = LLMConfig(
            provider="doubao",
            model_name="ep-20241217203540-vqsmc",  # 使用你的模型
            temperature=0.7,
            max_tokens=2000
        )
        print("使用Doubao LLM进行生成")
    except:
        print("未配置LLM，将使用模拟模式")
    
    # 初始化工作流
    workflow = CharacterProfileWorkflow(llm_config=llm_config)
    
    # 获取可用类别
    print("\n1. 获取可用的资料类别...")
    categories = workflow.get_available_categories()
    print(f"可用类别 ({len(categories)} 个): {', '.join(categories[:5])}...")
    
    # 获取可用知识集合
    print("\n2. 获取可用的知识集合...")
    collections = workflow.get_available_collections()
    print(f"可用集合: {collections}")
    
    # 准备角色基础信息
    character_name = "穆昭"
    basic_info = """
    穆昭（Leander），22岁，AB型血，双鱼座，ENFP人格。
    身高182cm，体重70kg。
    表面身份：神秘电竞高手"J"，参与"家园游戏"内测
    隐藏身份：天才黑客，异端组织"大阿卡那"成员，代号"愚者-Joker"
    外貌：黑发红瞳，短自来卷发，俊秀少年脸型带婴儿肥，眉眼锋锐
    性格：白切黑，外热内冷，张扬锋锐但装傻藏拙，占有欲和控制欲强
    """
    
    # 选择几个类别进行测试
    selected_categories = ["基本信息", "外貌特征", "性格特征"]
    selected_collections = ["character_knowledge"] if "character_knowledge" in collections else []
    
    print(f"\n3. 生成角色资料...")
    print(f"角色: {character_name}")
    print(f"选择类别: {selected_categories}")
    print(f"使用知识集合: {selected_collections}")
    
    # 生成角色资料
    result = await workflow.generate_character_profile(
        character_name=character_name,
        basic_info=basic_info,
        selected_categories=selected_categories,
        selected_collections=selected_collections
    )
    
    # 显示结果
    if result.get('success'):
        print(f"\n✅ 角色资料生成成功!")
        print(f"输出文件: {result.get('output_file')}")
        
        profile_data = result.get('generated_profile', {})
        for category, category_data in profile_data.items():
            print(f"\n📋 {category}:")
            for field, content in category_data.items():
                print(f"  • {field}: {content[:100]}{'...' if len(content) > 100 else ''}")
    else:
        print(f"\n❌ 角色资料生成失败: {result.get('error')}")
    
    return result

async def demo_batch_generation():
    """演示批量生成"""
    print("\n=== 批量角色资料生成演示 ===")
    
    # 准备批量数据
    profiles_data = [
        {
            "character_name": "角色A",
            "basic_info": "测试角色A，勇敢的战士，擅长剑术。",
            "selected_categories": ["基本信息", "性格特征"]
        },
        {
            "character_name": "角色B", 
            "basic_info": "测试角色B，聪明的法师，精通魔法。",
            "selected_categories": ["基本信息", "技能能力"]
        }
    ]
    
    # 只在有LLM配置时进行批量生成
    try:
        llm_config = LLMConfig(
            provider="doubao",
            model_name="ep-20241217203540-vqsmc",
            temperature=0.7,
            max_tokens=1000
        )
        
        workflow = CharacterProfileWorkflow(llm_config=llm_config)
        
        print("开始批量生成...")
        results = await workflow.batch_generate_profiles(
            profiles_data=profiles_data,
            selected_collections=["character_knowledge"]
        )
        
        print(f"\n批量生成完成，处理了 {len(results)} 个角色:")
        for result in results:
            character_name = result.get('character_name', '未知')
            success = result.get('success', False)
            print(f"  • {character_name}: {'✅ 成功' if success else '❌ 失败'}")
            if not success:
                print(f"    错误: {result.get('error')}")
        
    except Exception as e:
        print(f"批量生成演示跳过（需要LLM配置）: {e}")

async def demo_file_import():
    """演示从文件导入知识"""
    print("\n=== 文件导入知识演示 ===")
    
    # 检查穆昭语料文件是否存在
    muzhao_file = Path("workspace/input/muzhao/穆昭语料.txt")
    if muzhao_file.exists():
        print(f"发现穆昭语料文件: {muzhao_file}")
        
        workflow = CharacterProfileWorkflow()
        
        # 导入文件到知识库
        print("正在导入文件到知识库...")
        success = await workflow.import_knowledge_from_file(
            collection_name="muzhao_corpus",
            file_path=str(muzhao_file),
            description="穆昭角色语料库"
        )
        
        if success:
            print("✅ 文件导入成功!")
            
            # 测试查询导入的内容
            kb = workflow.knowledge_base
            results = await kb.query_documents(
                collection_name="muzhao_corpus",
                query_text="穆昭 性格",
                n_results=2
            )
            
            print(f"\n从导入的语料中查询到 {len(results)} 个结果:")
            for i, result in enumerate(results, 1):
                print(f"  结果{i}: {result['document'][:150]}...")
        else:
            print("❌ 文件导入失败")
    else:
        print(f"穆昭语料文件不存在: {muzhao_file}")

async def main():
    """主演示函数"""
    print("🎭 角色资料生成工作流演示")
    print("=" * 50)
    
    try:
        # 1. 演示知识库功能
        kb = await demo_knowledge_base()
        
        # 2. 演示角色资料生成
        await demo_character_profile_generation()
        
        # 3. 演示文件导入
        await demo_file_import()
        
        # 4. 演示批量生成
        await demo_batch_generation()
        
        print("\n🎉 演示完成!")
        print("\n💡 使用提示:")
        print("1. 确保已安装 chromadb: pip install chromadb")
        print("2. 配置 .env 文件中的LLM API密钥以启用生成功能")
        print("3. 将知识文件放在 workspace/input/ 目录下进行导入")
        print("4. 生成的角色资料保存在 workspace/output/ 目录下")
        
    except Exception as e:
        logger.error(f"演示执行失败: {e}")
        print(f"\n❌ 演示失败: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 