"""
ZZZero Agent 主入口
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

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
        
        # 创建应用
        app = AgentApp(
            title="ZZZero AI Agent",
            description="基于节点编排的AI Agent框架 - 支持多种Agent范式和MCP工具集成"
        )
        print("✅ 应用创建完成")
        
        # 尝试多个端口启动
        ports = [7868, 7860, 7861, 7862, 7863]
        launched = False
        
        for port in ports:
            try:
                print(f"🚀 尝试在端口 {port} 启动...")
                app.launch(
                    server_name="127.0.0.1",  # 使用本地回环地址
                    server_port=port,
                    share=False,
                    show_error=True,
                    debug=False,
                    inbrowser=True  # 自动打开浏览器
                )
                print(f"✅ 成功在端口 {port} 启动")
                print(f"🌐 访问地址: http://127.0.0.1:{port}")
                launched = True
                break
            except Exception as e:
                print(f"❌ 端口 {port} 启动失败: {str(e)}")
                if port == ports[-1]:  # 最后一个端口也失败
                    raise e
                continue
        
        if not launched:
            print("❌ 所有端口都启动失败")
            
    except KeyboardInterrupt:
        print("\n🔄 正在关闭服务器...")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("👋 程序已退出")


if __name__ == "__main__":
    # 设置Windows异步事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    main() 