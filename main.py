# -*- coding: utf-8 -*-
"""
ZZZero AI Agent Framework 主入口模块

@author leo
@description ZZZero AI Agent Framework的主启动文件，负责初始化数据库服务和Web应用
@functions 
    - main - 主函数，启动整个应用
    - setup_database - 设置数据库服务
    - setup_environment - 设置环境变量
@example 
    python main.py
@dependencies 
    - web.app.AgentApp - Web应用主类
    - database.db_service - 数据库服务管理
    - dotenv - 环境变量加载
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

# 延迟导入数据库相关模块，避免在环境变量加载前初始化





async def setup_database():
    """设置和启动数据库服务"""
    try:
        print("=== 启动数据库服务 ===")
        
        # 在环境变量加载后导入数据库模块
        from database.db_service import ensure_database_running, get_database_service
        
        # 启动PostgreSQL数据库
        success = await ensure_database_running()
        if success:
            print("[成功] PostgreSQL数据库启动成功")
            
            # 获取数据库状态
            db_service = get_database_service()
            status = await db_service.get_database_status()
            print(f"[状态] 数据库状态: {status}")
            
            return True
        else:
            print("[错误] PostgreSQL数据库启动失败")
            return False
            
    except Exception as e:
        print(f"[错误] 数据库服务启动异常: {e}")
        logging.error(f"数据库服务启动异常: {e}")
        return False

def setup_environment():
    """设置环境变量"""
    # 加载.env文件
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
        print("[成功] 环境变量加载完成")
    else:
        print("[警告] .env文件不存在，使用默认配置")
    
    # 设置PostgreSQL连接环境变量（如果未设置）
    postgres_defaults = {
        'POSTGRES_HOST': 'localhost',
        'POSTGRES_PORT': '5432',
        'POSTGRES_DB': 'zzzero',
        'POSTGRES_USER': 'zzzero_user',
        'POSTGRES_PASSWORD': 'zzzero_pass'
    }
    
    for key, default_value in postgres_defaults.items():
        if not os.getenv(key):
            os.environ[key] = default_value
            print(f"[配置] 设置默认环境变量: {key}={default_value}")

async def main():
    """主函数"""
    try:
        print("=== ZZZero AI Agent 启动 ===")
        
        # 设置环境变量
        setup_environment()
        
        # 启动数据库服务
        db_success = await setup_database()
        if not db_success:
            print("[警告] 数据库服务启动失败，但应用将继续启动（降级模式）")
        
        # MCP服务器现在由MCPToolManager在应用初始化时启动
        print("[配置] MCP服务器将在应用初始化时启动...")
        
        # 在环境变量加载后导入Web应用
        from web.app import AgentApp
        
        # 创建应用
        app = AgentApp(
            title="ZZZero AI Agent",
            description="基于节点编排的AI Agent框架 - 支持多种Agent范式和MCP工具集成"
        )
        print("[成功] 应用创建完成")
        
        # 使用Gradio的内置端口查找机制
        print("[启动] 启动Web服务...")
        
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
            print("[成功] 成功在端口 7860 启动")
            print("[地址] 访问地址: http://127.0.0.1:7860")
            
        except OSError as e:
            if "Cannot find empty port" in str(e):
                print("[警告] 端口 7860 被占用，尝试其他端口...")
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
                print("[成功] 已在自动选择的端口启动")
            else:
                raise e
            
    except KeyboardInterrupt:
        print("\n🔄 正在关闭服务器...")
    except Exception as e:
        print(f"[错误] 启动失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # MCP服务器清理现在由MCPToolManager处理
        print("[退出] 程序已退出")


if __name__ == "__main__":
    # 设置Windows异步事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main()) 