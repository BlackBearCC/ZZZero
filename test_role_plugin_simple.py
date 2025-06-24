#!/usr/bin/env python3
"""
简单的角色插件测试脚本
"""
import os
import sys

# 添加src到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_role_plugin_basic():
    """测试角色插件基础功能"""
    try:
        print("🧪 开始测试角色插件基础功能...")
        
        # 1. 导入并创建插件管理器
        from core.plugins import get_role_plugin_manager
        plugin_manager = get_role_plugin_manager("./workspace")
        print("✅ 插件管理器创建成功")
        
        # 2. 配置角色资料
        plugin_manager.configure_profile(
            name="测试角色",
            content="这是一个用于测试的角色，性格温柔善良，擅长沟通。",
            tags=["温柔", "善良", "测试"],
            enabled=True
        )
        print("✅ 角色资料配置成功")
        
        # 3. 创建测试知识库文件
        os.makedirs("./workspace", exist_ok=True)
        with open("./workspace/test_kb.txt", 'w', encoding='utf-8') as f:
            f.write("测试角色擅长编程和设计。\n")
            f.write("测试角色喜欢阅读和学习新技术。\n")
            f.write("测试角色具有良好的团队协作能力。")
        
        plugin_manager.configure_knowledge_base(
            name="测试知识库",
            source_file="./workspace/test_kb.txt",
            description="用于测试的角色知识库",
            search_limit=3,
            enabled=True
        )
        print("✅ 知识库配置成功")
        
        # 4. 检查插件状态
        status = plugin_manager.get_status()
        profile_available = status['profile_plugin']['available']
        kb_available = status['knowledge_base_plugin']['available']
        
        print(f"✅ 角色资料插件可用: {profile_available}")
        print(f"✅ 知识库插件可用: {kb_available}")
        
        # 5. 测试插件信息获取
        if profile_available:
            profile_info = status['profile_plugin']['info']
            print(f"   - 角色名称: {profile_info['name']}")
            print(f"   - 内容长度: {profile_info['content_length']} 字符")
            print(f"   - 标签: {', '.join(profile_info['tags'])}")
        
        if kb_available:
            kb_info = status['knowledge_base_plugin']['info']
            print(f"   - 知识库名称: {kb_info['name']}")
            print(f"   - 源文件: {kb_info['source_file']}")
            print(f"   - 数据条数: {kb_info['data_count']} 条")
        
        print("\n🎉 角色插件基础功能测试成功！")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_role_plugin_basic()
    if success:
        print("\n💡 现在你可以在Web界面中看到角色插件已经正常工作了！")
        print("💡 刷新Web界面的角色插件状态，应该能看到配置的角色信息。")
    else:
        print("\n❌ 测试失败，请检查错误信息并修复问题。") 