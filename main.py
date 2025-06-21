"""
ZZZero Agent 主入口
"""
import asyncio
import os
import sys
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
        
        # 使用Gradio的内置端口查找机制
        print("🚀 启动Web服务...")
        
        try:
            # 方法1: 先尝试默认端口7860
            app.launch(
                server_name="127.0.0.1",
                server_port=7860,
                share=False,
                show_error=True,
                debug=False,
                inbrowser=True,  # 自动打开浏览器
                quiet=False,  # 显示启动信息
                prevent_thread_lock=False  # 确保主线程被阻塞
            )
            print("✅ 成功在端口 7860 启动")
            print("🌐 访问地址: http://127.0.0.1:7860")
            
        except OSError as e:
            if "Cannot find empty port" in str(e):
                print("⚠️ 端口 7860 被占用，尝试其他端口...")
                # 方法2: 让Gradio自动选择端口
                app.launch(
                    server_name="127.0.0.1",
                    server_port=None,  # 让Gradio自动选择
                    share=False,
                    show_error=True,
                    debug=False,
                    inbrowser=True,
                    quiet=False
                )
                print("✅ 已在自动选择的端口启动")
            else:
                raise e
            
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