#!/usr/bin/env python3
"""
安装SSE流式功能依赖
如果系统不允许直接pip install，此脚本会尝试其他方式
"""

import subprocess
import sys
import os

def install_flask():
    """尝试安装Flask"""
    print("🔄 正在尝试安装Flask...")
    
    # 方法1: 尝试标准pip安装
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'flask>=2.3.0'], 
                               capture_output=True, text=True, check=True)
        print("✅ Flask安装成功！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 标准pip安装失败: {e}")
        
    # 方法2: 尝试--user安装
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--user', 'flask>=2.3.0'], 
                               capture_output=True, text=True, check=True)
        print("✅ Flask用户级安装成功！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 用户级安装失败: {e}")
    
    # 方法3: 尝试--break-system-packages（谨慎使用）
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--break-system-packages', 'flask>=2.3.0'], 
                               capture_output=True, text=True, check=True)
        print("⚠️  Flask系统级安装成功（使用了--break-system-packages）")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 系统级安装也失败: {e}")
    
    return False

def check_flask():
    """检查Flask是否已安装"""
    try:
        import flask
        print(f"✅ Flask已安装，版本: {flask.__version__}")
        return True
    except ImportError:
        print("❌ Flask未安装")
        return False

def main():
    print("🚀 ZZZero SSE流式功能依赖检查")
    print("=" * 50)
    
    # 检查当前Flask状态
    if check_flask():
        print("✅ 所有依赖已满足，SSE流式功能可用！")
        return
    
    print("\n📦 开始安装依赖...")
    
    # 尝试安装Flask
    if install_flask():
        print("\n🎉 安装完成！")
        print("📝 提示：")
        print("   - SSE流式功能现在应该可用了")
        print("   - 重新启动应用以启用流式界面")
        print("   - Flask服务器将在端口5001上运行")
    else:
        print("\n❌ 自动安装失败")
        print("📝 手动解决方案：")
        print("   1. 创建虚拟环境: python3 -m venv venv")
        print("   2. 激活虚拟环境: source venv/bin/activate (Linux/Mac)")
        print("   3. 安装依赖: pip install flask>=2.3.0")
        print("   4. 或者使用系统包管理器: sudo apt install python3-flask")

if __name__ == "__main__":
    main()