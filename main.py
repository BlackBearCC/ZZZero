"""
ZZZero Agent 主入口
"""
import asyncio
import os
from dotenv import load_dotenv

from src.web.app import AgentApp


def main():
    """主函数"""
    # 加载环境变量
    load_dotenv()
    
    # 创建应用
    app = AgentApp(
        title="ZZZero AI Agent",
        description="基于节点编排的AI Agent框架 - 支持多种Agent范式和MCP工具集成"
    )
    
    # 启动应用
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )


if __name__ == "__main__":
    main() 