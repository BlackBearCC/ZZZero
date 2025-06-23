#!/usr/bin/env python3
"""
角色插件系统测试脚本
演示如何使用角色资料和角色知识库插件
"""
import asyncio
import sys
import os

# 添加src路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.plugins import get_role_plugin_manager


async def test_role_plugins():
    """测试角色插件系统"""
    print("🎭 开始测试角色插件系统...")
    
    # 获取角色插件管理器
    plugin_manager = get_role_plugin_manager()
    
    print("\n📝 测试角色资料插件...")
    
    # 配置角色资料
    role_profile = """
    角色名称：艾莉丝·薇拉诺瓦
    
    基本信息：
    - 年龄：25岁
    - 职业：独立艺术家和咖啡店店主
    - 性格：温柔、创意十足、细心周到
    - 爱好：绘画、阅读、园艺、烘焙
    
    背景故事：
    艾莉丝是一位充满创意的年轻女性，在市中心经营着一家名为"月光画廊"的艺术咖啡店。
    她将自己的绘画作品展示在咖啡店里，同时为顾客提供手工制作的咖啡和甜点。
    艾莉丝热爱生活中的美好细节，总是能在平凡的日常中发现灵感。
    
    性格特点：
    - 对艺术充满热情，善于从生活中汲取创作灵感
    - 性格温和友善，善于倾听他人的想法
    - 注重细节，追求完美的生活品质
    - 喜欢通过艺术和美食与他人建立连接
    """
    
    plugin_manager.configure_profile(
        name="艾莉丝·薇拉诺瓦",
        content=role_profile,
        tags=["艺术家", "咖啡店主", "温柔", "创意"],
        enabled=True
    )
    
    print("✅ 角色资料配置完成")
    
    print("\n📚 测试角色知识库插件...")
    
    # 配置角色知识库
    plugin_manager.configure_knowledge_base(
        name="艾莉丝专属知识库",
        path="./workspace/vectordb/alice_knowledge",
        description="包含艺术技巧、咖啡制作、园艺知识等艾莉丝相关的专业知识",
        search_limit=3,
        enabled=True
    )
    
    print("✅ 角色知识库配置完成")
    
    print("\n📊 查看插件状态...")
    status = plugin_manager.get_status()
    
    for plugin_name, plugin_info in status.items():
        print(f"\n{plugin_name}:")
        print(f"  - 启用状态: {plugin_info['enabled']}")
        print(f"  - 可用状态: {plugin_info['available']}")
        if plugin_info['info']:
            print(f"  - 详细信息: {plugin_info['info']}")
    
    print("\n🔍 测试角色上下文获取...")
    
    # 测试获取角色上下文
    keywords = ["绘画", "咖啡", "创作"]
    context = await plugin_manager.get_role_context(keywords)
    
    print(f"获取到的角色上下文:")
    if "profile" in context:
        print(f"  - 角色资料: {len(context['profile'])} 字符")
    if "knowledge" in context:
        print(f"  - 知识库结果: {len(context['knowledge'])} 条")
        for item in context['knowledge']:
            print(f"    * {item['keyword']}: {item['content'][:50]}...")
    
    print("\n🧪 测试MCP工具调用（模拟）...")
    
    # 模拟测试工具管理器的角色插件集成
    try:
        from tools.mcp_tools import MCPToolManager
        
        tool_manager = MCPToolManager()
        
        # 测试权限检查
        has_permission = tool_manager.has_role_plugin_permission("roleplay")
        print(f"角色扮演服务器的插件权限: {has_permission}")
        
        # 测试参数注入
        original_args = {
            "requirements": "生成一个关于绘画创作的日程安排"
        }
        
        enhanced_args = await tool_manager.inject_role_context_to_arguments(
            "roleplay", "generate_schedule_plan", original_args
        )
        
        print(f"原始参数: {original_args}")
        print(f"增强参数包含角色信息: {'character_description' in enhanced_args}")
        if 'character_description' in enhanced_args:
            print(f"角色描述长度: {len(enhanced_args['character_description'])} 字符")
        
    except ImportError as e:
        print(f"⚠️ 无法导入MCP工具管理器: {e}")
    
    print("\n✨ 角色插件系统测试完成！")
    
    return plugin_manager


async def test_plugin_persistence():
    """测试插件配置持久化"""
    print("\n💾 测试配置持久化...")
    
    # 创建新的管理器实例（模拟重启）
    new_manager = get_role_plugin_manager()
    
    # 检查配置是否被正确加载
    status = new_manager.get_status()
    
    profile_loaded = status['profile_plugin']['enabled'] and status['profile_plugin']['available']
    kb_loaded = status['knowledge_base_plugin']['enabled'] and status['knowledge_base_plugin']['available']
    
    print(f"角色资料配置加载: {'✅' if profile_loaded else '❌'}")
    print(f"知识库配置加载: {'✅' if kb_loaded else '❌'}")
    
    if profile_loaded:
        profile_info = status['profile_plugin']['info']
        print(f"加载的角色名称: {profile_info['name']}")
        print(f"角色标签: {', '.join(profile_info['tags'])}")
    
    return new_manager


def main():
    """主函数"""
    print("🚀 角色插件系统演示开始...")
    
    try:
        # 运行测试
        plugin_manager = asyncio.run(test_role_plugins())
        
        # 测试持久化
        asyncio.run(test_plugin_persistence())
        
        print("\n🎉 所有测试完成！")
        print("\n📋 使用说明:")
        print("1. 角色插件已配置完成，可以在Web界面中查看")
        print("2. 启动Web应用后，角色扮演工具将自动使用这些插件")
        print("3. 调用角色扮演工具时，角色信息会自动注入，无需手动输入")
        print("4. 可以通过Web界面修改或清空角色配置")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 