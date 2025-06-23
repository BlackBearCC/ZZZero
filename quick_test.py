import sys
import os
sys.path.append('src')

try:
    from core.plugins import get_role_plugin_manager
    print("✅ 角色插件系统导入成功")
    
    # 测试创建管理器
    manager = get_role_plugin_manager()
    print("✅ 角色插件管理器创建成功")
    
    # 测试配置
    manager.configure_profile(
        name="测试角色",
        content="这是一个测试角色",
        enabled=True
    )
    print("✅ 角色资料配置成功")
    
    # 获取状态
    status = manager.get_status()
    print(f"✅ 插件状态获取成功: {status['profile_plugin']['enabled']}")
    
    print("\n🎉 角色插件系统基础功能测试通过！")
    
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc() 