"""
ZZZero Agent 主入口
"""
import asyncio
import os
import sys
import socket
import logging
from pathlib import Path
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加src路径
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

from web.app import AgentApp


def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """查找可用端口"""
    for i in range(max_attempts):
        port = start_port + i
        try:
            # 尝试绑定端口
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"无法在 {start_port} 到 {start_port + max_attempts - 1} 范围内找到可用端口")


def main():
    """主函数"""
    try:
        print("=== ZZZero AI Agent 启动 ===")
        
        # 加载环境变量
        load_dotenv()
        print("✅ 环境变量加载完成")
        
        # MCP服务器现在由MCPToolManager在应用初始化时启动
        print("🔧 MCP服务器将在应用初始化时启动...")
        
        # 创建应用
        app = AgentApp(
            title="ZZZero AI Agent",
            description="基于节点编排的AI Agent框架 - 支持多种Agent范式和MCP工具集成"
        )
        print("✅ 应用创建完成")
        
        # 智能查找可用端口
        try:
            port = find_available_port(7860, 20)  # 从7860开始，尝试20个端口
            print(f"🚀 在端口 {port} 启动服务...")
            
            # 设置环境变量，让Gradio使用这个端口
            os.environ['GRADIO_SERVER_PORT'] = str(port)
            
            app.launch(
                server_name="127.0.0.1",
                server_port=port,
                share=False,
                show_error=True,
                debug=False,
                inbrowser=True,  # 自动打开浏览器
                quiet=False,  # 显示启动信息
                prevent_thread_lock=False  # 确保主线程被阻塞
            )
            print(f"✅ 成功在端口 {port} 启动")
            print(f"🌐 访问地址: http://127.0.0.1:{port}")
            
        except RuntimeError as e:
            print(f"❌ 无法找到可用端口: {e}")
            # 最后尝试让Gradio自己选择端口
            print("🔄 让Gradio自动选择端口...")
            app.launch(
                server_name="127.0.0.1",
                share=False,
                show_error=True,
                debug=False,
                inbrowser=True
            )
            
    except KeyboardInterrupt:
        print("\n🔄 正在关闭服务器...")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # MCP服务器清理现在由MCPToolManager处理
        print("👋 程序已退出")


if __name__ == "__main__":
    # 设置Windows异步事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    main() 