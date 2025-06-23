#!/usr/bin/env python3
"""
测试角色插件修复效果
"""
import asyncio
import os
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.plugins import get_role_plugin_manager

async def test_role_plugins():
    """测试角色插件功能"""
    print("🎭 开始测试角色插件...")
    
    # 获取插件管理器
    plugin_manager = get_role_plugin_manager("./workspace")
    
    # 1. 测试角色资料插件
    print("\n📝 测试角色资料插件...")
    plugin_manager.configure_profile(
        name="测试角色",
        content="这是一个用于测试的角色，性格温柔，善于交流。",
        tags=["温柔", "善良", "测试"],
        enabled=True
    )
    
    # 获取状态
    status = plugin_manager.get_status()
    print(f"角色资料状态: {status['profile_plugin']}")
    
    # 2. 创建测试知识库文件
    print("\n📚 创建测试知识库文件...")
    test_kb_content = """这是第一段测试知识，关于角色的基本信息。

这是第二段测试知识，描述角色的技能和能力。

这是第三段测试知识，介绍角色的背景故事。"""
    
    kb_file_path = "./workspace/test_knowledge.txt"
    with open(kb_file_path, 'w', encoding='utf-8') as f:
        f.write(test_kb_content)
    
    # 配置知识库插件
    plugin_manager.configure_knowledge_base(
        name="测试知识库",
        source_file=kb_file_path,
        description="用于测试的角色知识库",
        search_limit=3,
        enabled=True
    )
    
    # 获取知识库状态
    status = plugin_manager.get_status()
    print(f"知识库状态: {status['knowledge_base_plugin']}")
    
    # 3. 测试知识库搜索
    print("\n🔍 测试知识库搜索...")
    keywords = ["角色", "技能", "背景"]
    search_results = await plugin_manager.knowledge_base_plugin.search_knowledge(keywords)
    print(f"搜索结果 (关键词: {keywords}):")
    for result in search_results:
        print(f"  - {result['keyword']}: {result['content'][:50]}...")
    
    # 4. 测试综合上下文获取
    print("\n🎯 测试综合上下文获取...")
    context = await plugin_manager.get_role_context(keywords=["角色", "测试"])
    print("获取的角色上下文:")
    if 'profile' in context:
        print(f"  角色资料: {context['profile'][:50]}...")
    if 'knowledge' in context:
        print(f"  知识库结果: {len(context['knowledge'])} 条")
    
    # 5. 验证配置持久化
    print("\n💾 测试配置持久化...")
    print(f"配置文件路径: {plugin_manager.config_file}")
    print(f"配置文件存在: {plugin_manager.config_file.exists()}")
    
    if plugin_manager.config_file.exists():
        import json
        with open(plugin_manager.config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("保存的配置:")
        for key, value in config.items():
            print(f"  {key}: {value.get('enabled', False)} ({'有数据' if value.get('enabled') else '无数据'})")
    
    print("\n✅ 角色插件测试完成！")

if __name__ == "__main__":
    asyncio.run(test_role_plugins()) 