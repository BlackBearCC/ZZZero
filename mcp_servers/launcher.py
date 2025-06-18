"""
MCP服务启动器
用于启动和管理MCP服务的工具
"""

import asyncio
import argparse
import os
import sys
import logging
from typing import Optional

# 添加父目录到sys.path以便导入mcp模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csv_mcp_server import CSVMCPServer
from vector_server import VectorMCPServer


class MCPLauncher:
    """MCP服务启动器"""
    
    def __init__(self):
        self.setup_logging()
        
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    async def start_csv_server(self, csv_directory: Optional[str] = None):
        """启动CSV MCP服务器"""
        self.logger.info("启动CSV MCP服务器...")
        
        if csv_directory and not os.path.exists(csv_directory):
            self.logger.error(f"CSV目录不存在: {csv_directory}")
            return
        
        csv_server = CSVMCPServer(csv_directory=csv_directory)
        await csv_server.run()
    
    async def start_vector_server(self, 
                                chroma_db_path: Optional[str] = None,
                                host: Optional[str] = None,
                                port: Optional[int] = None):
        """启动向量MCP服务器"""
        self.logger.info("启动向量MCP服务器...")
        
        if chroma_db_path and not os.path.exists(chroma_db_path):
            self.logger.error(f"ChromaDB目录不存在: {chroma_db_path}")
            return
        
        try:
            vector_server = VectorMCPServer(
                chroma_db_path=chroma_db_path,
                host=host,
                port=port
            )
            await vector_server.run()
        except ImportError as e:
            self.logger.error(f"启动向量服务器失败: {e}")
            print("请安装ChromaDB: pip install chromadb")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MCP服务启动器")
    parser.add_argument("--service", choices=["csv", "vector"], 
                       default="csv", help="要启动的服务类型")
    parser.add_argument("--csv-dir", help="CSV文件目录")
    parser.add_argument("--chroma-db", help="ChromaDB数据库路径")
    parser.add_argument("--host", help="ChromaDB远程主机")
    parser.add_argument("--port", type=int, help="ChromaDB远程端口")
    
    args = parser.parse_args()
    
    launcher = MCPLauncher()
    
    try:
        if args.service == "csv":
            asyncio.run(launcher.start_csv_server(args.csv_dir))
        elif args.service == "vector":
            asyncio.run(launcher.start_vector_server(
                args.chroma_db, args.host, args.port
            ))
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"启动服务时发生错误: {e}")


if __name__ == "__main__":
    main() 