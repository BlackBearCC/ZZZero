#!/usr/bin/env python3
"""
MCP集成演示启动脚本
"""
import asyncio
import logging
import sys
import os
from pathlib import Path

# 添加src路径
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """主演示函数"""
    try:
        print("=== ZZZero MCP集成演示 ===\n")
        
        # 1. 测试MCP管理器基本功能
        print("1. 正在初始化MCP管理器...")
        from tools.mcp_manager import mcp_manager
        
        servers = mcp_manager.list_servers()
        print(f"   发现 {len(servers)} 个MCP服务器:")
        for server in servers:
            print(f"   - {server['name']} (类型: {server['type']})")
        
        # 2. 启动Web界面
        print("\n2. 正在启动Web界面...")
        from web.app import AgentApp
        
        app = AgentApp(
            title="ZZZero AI Agent - MCP集成版",
            description="支持本地和远程MCP服务器的AI Agent系统"
        )
        
        print("   Web界面已准备就绪!")
        print("   功能包括:")
        print("   - 🔌 MCP服务器管理（本地stdio + 远程HTTP）")
        print("   - 🤖 ReactAgent集成")
        print("   - 🔧 工具统一管理")
        print("   - 📊 实时执行监控")
        
        print(f"\n3. 启动服务器...")
        print("   使用说明:")
        print("   - 在左侧配置LLM和Agent")
        print("   - 在MCP服务器面板中启用需要的服务器")
        print("   - 可以添加远程MCP服务器")
        print("   - 配置完成后在右侧进行对话")
        print("\n   按 Ctrl+C 退出\n")
        
        # 启动Gradio应用
        # 尝试多个端口以避免冲突
        ports = [7860, 7861, 7862, 7863, 7864]
        launched = False
        
        for port in ports:
            try:
                print(f"   尝试在端口 {port} 启动...")
                app.launch(
                    server_name="127.0.0.1",  # 使用本地回环地址
                    server_port=port,
                    share=False,
                    debug=False,
                    show_error=True,
                    prevent_thread_lock=False,
                    quiet=False,
                    inbrowser=True  # 自动打开浏览器
                )
                print(f"✅ 服务器成功启动在端口 {port}")
                print(f"   访问地址: http://127.0.0.1:{port}")
                launched = True
                break
            except Exception as e:
                print(f"   端口 {port} 启动失败: {str(e)}")
                if port == ports[-1]:  # 最后一个端口也失败
                    raise e
                continue
        
        if not launched:
            print("❌ 所有端口都启动失败")
        
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("程序已退出")


if __name__ == "__main__":
    # 设置异步事件循环策略（Windows）
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main()) 