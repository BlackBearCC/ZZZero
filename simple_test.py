#!/usr/bin/env python3
"""
简化测试：角色插件自动注入功能
"""
import asyncio
import sys
import os

# 添加src到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

async def test_injection():
    try:
        print("🧪 开始测试角色插件注入...")
        
        # 1. 测试插件管理器
        from core.plugins import get_role_plugin_manager
        plugin_manager = get_role_plugin_manager("./workspace")
        
        # 配置角色资料
        plugin_manager.configure_profile(
            name="艾莉丝",
            content="25岁独立艺术家和咖啡店店主，温柔创意",
            enabled=True
        )
        
        # 创建知识库文件
        os.makedirs("./workspace", exist_ok=True)
        with open("./workspace/test_kb.txt", 'w', encoding='utf-8') as f:
            f.write("艾莉丝擅长绘画和咖啡制作。\n她喜欢园艺和烘焙。")
        
        plugin_manager.configure_knowledge_base(
            name="测试知识库",
            source_file="./workspace/test_kb.txt",
            enabled=True
        )
        
        status = plugin_manager.get_status()
        print(f"✅ 角色资料: {status['profile_plugin']['available']}")
        print(f"✅ 知识库: {status['knowledge_base_plugin']['available']}")
        
        # 2. 测试MCP工具管理器
        from tools.mcp_tools import MCPToolManager
        tool_manager = MCPToolManager()
        await tool_manager.initialize()
        
        # 测试权限
        has_permission = tool_manager.has_role_plugin_permission("roleplay")
        print(f"✅ 角色扮演权限: {has_permission}")
        
        # 3. 测试参数注入
        test_args = {
            "requirements": "生成关于绘画和咖啡的日程"
        }
        
        enhanced_args = await tool_manager.inject_role_context_to_arguments(
            "roleplay", "generate_schedule_plan", test_args
        )
        
        print(f"原始参数: {test_args}")
        print(f"包含角色描述: {'character_description' in enhanced_args}")
        print(f"需求参数增强: {len(enhanced_args.get('requirements', '')) > len(test_args.get('requirements', ''))}")
        
        if 'character_description' in enhanced_args:
            print(f"✅ 角色资料已注入！长度: {len(enhanced_args['character_description'])}")
            
        if len(enhanced_args.get('requirements', '')) > len(test_args.get('requirements', '')):
            print("✅ 知识库内容已注入！")
        
        print("🎉 测试成功完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_injection()) 