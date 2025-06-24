#!/usr/bin/env python3
"""
角色扮演数据生成服务启动脚本
"""
import sys
import os
import asyncio
import subprocess
from pathlib import Path

def check_environment():
    """检查环境配置"""
    print("🔍 检查环境配置...")
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ Python版本过低，需要Python 3.8或更高版本")
        return False
    
    print(f"✅ Python版本: {sys.version}")
    
    # 检查必要的环境变量
    llm_provider = os.getenv("LLM_PROVIDER", "doubao")
    api_key = os.getenv("ARK_API_KEY") or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ 未找到API密钥，请设置以下环境变量之一：")
        print("   - ARK_API_KEY (豆包)")
        print("   - OPENAI_API_KEY (OpenAI)")
        return False
    
    print(f"✅ LLM提供商: {llm_provider}")
    print(f"✅ API密钥: {'*' * 8}{api_key[-4:] if len(api_key) > 4 else '****'}")
    
    # 检查必要的文件
    server_file = Path("mcp_servers/roleplay_data_server.py")
    if not server_file.exists():
        print(f"❌ 服务器文件不存在: {server_file}")
        return False
    
    readme_file = Path("mcp_servers/roleplay_data_README.md")
    if not readme_file.exists():
        print(f"⚠️ README文件不存在: {readme_file}")
        print("   知识库将无法自动初始化")
    
    print("✅ 环境检查完成")
    return True

def show_menu():
    """显示菜单"""
    print("\n" + "="*60)
    print("🎭 角色扮演数据生成服务")
    print("="*60)
    print("1. 🧪 本地测试模式 (推荐)")
    print("2. 🚀 MCP服务器模式")
    print("3. 🔧 环境检查")
    print("4. 📖 查看使用说明")
    print("0. 退出")
    print("="*60)

def show_usage():
    """显示使用说明"""
    usage_file = Path("mcp_servers/USAGE.md")
    if usage_file.exists():
        try:
            with open(usage_file, 'r', encoding='utf-8') as f:
                print(f.read())
        except Exception as e:
            print(f"❌ 无法读取使用说明: {e}")
    else:
        print("📖 基本使用说明:")
        print("1. 本地测试模式：演示完整的日程生成流程")
        print("2. MCP服务器模式：启动MCP协议服务器")
        print("3. 确保设置了正确的API密钥环境变量")

async def run_test_mode():
    """运行测试模式"""
    print("\n🧪 启动本地测试模式...")
    print("这将演示完整的角色扮演数据生成流程")
    print("-" * 40)
    
    try:
        # 切换到正确的目录
        os.chdir(Path(__file__).parent)
        
        # 运行测试
        process = await asyncio.create_subprocess_exec(
            sys.executable, "mcp_servers/roleplay_data_server.py", "--test",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        # 实时显示输出
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            print(line.decode('utf-8', errors='ignore').rstrip())
        
        await process.wait()
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断测试")
    except Exception as e:
        print(f"❌ 测试模式启动失败: {e}")

async def run_server_mode():
    """运行服务器模式"""
    print("\n🚀 启动MCP服务器模式...")
    print("服务器将在stdio模式下运行，等待MCP客户端连接")
    print("按Ctrl+C停止服务器")
    print("-" * 40)
    
    try:
        # 切换到正确的目录
        os.chdir(Path(__file__).parent)
        
        # 运行服务器
        process = await asyncio.create_subprocess_exec(
            sys.executable, "mcp_servers/roleplay_data_server.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        # 实时显示输出
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            print(line.decode('utf-8', errors='ignore').rstrip())
        
        await process.wait()
        
    except KeyboardInterrupt:
        print("\n⏹️ 服务器已停止")
    except Exception as e:
        print(f"❌ 服务器启动失败: {e}")

async def main():
    """主函数"""
    print("🎭 角色扮演数据生成服务启动器")
    
    while True:
        show_menu()
        
        try:
            choice = input("\n请选择操作 (0-4): ").strip()
            
            if choice == "0":
                print("👋 再见！")
                break
            elif choice == "1":
                if check_environment():
                    await run_test_mode()
                input("\n按回车键继续...")
            elif choice == "2":
                if check_environment():
                    await run_server_mode()
                input("\n按回车键继续...")
            elif choice == "3":
                check_environment()
                input("\n按回车键继续...")
            elif choice == "4":
                show_usage()
                input("\n按回车键继续...")
            else:
                print("❌ 无效选择，请输入0-4之间的数字")
                
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except EOFError:
            print("\n👋 再见！")
            break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再见！") 