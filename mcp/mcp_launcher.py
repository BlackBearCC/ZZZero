"""
MCP服务启动器
用于启动和管理多个MCP服务的工具
"""

import asyncio
import argparse
import os
from pathlib import Path
import logging
from typing import Optional

try:
    # 尝试相对导入（作为包使用时）
    from .csv_mcp_server import CSVMCPServer
    from .vector_mcp_server import VectorMCPServer
except ImportError:
    # 尝试绝对导入（直接运行时）
    from csv_mcp_server import CSVMCPServer
    from vector_mcp_server import VectorMCPServer


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
        await csv_server.run_server()
    
    async def start_vector_server(self, 
                                chroma_db_path: Optional[str] = None,
                                host: Optional[str] = None,
                                port: Optional[int] = None):
        """启动向量MCP服务器"""
        self.logger.info("启动向量MCP服务器...")
        
        if chroma_db_path and not os.path.exists(chroma_db_path):
            self.logger.error(f"ChromaDB目录不存在: {chroma_db_path}")
            return
        
        vector_server = VectorMCPServer(
            chroma_db_path=chroma_db_path,
            host=host,
            port=port
        )
        await vector_server.run_server()
    
    async def start_combined_server(self,
                                  csv_directory: Optional[str] = None,
                                  chroma_db_path: Optional[str] = None,
                                  host: Optional[str] = None,
                                  port: Optional[int] = None):
        """启动组合服务器（同时提供CSV和向量查询功能）"""
        self.logger.info("启动组合MCP服务器...")
        
        # 创建组合服务器
        combined_server = CombinedMCPServer(
            csv_directory=csv_directory,
            chroma_db_path=chroma_db_path,
            host=host,
            port=port
        )
        await combined_server.run_server()


class CombinedMCPServer:
    """组合MCP服务器 - 同时提供CSV和向量查询功能"""
    
    def __init__(self,
                 csv_directory: Optional[str] = None,
                 chroma_db_path: Optional[str] = None,
                 host: Optional[str] = None,
                 port: Optional[int] = None):
        """
        初始化组合MCP服务器
        
        Args:
            csv_directory: CSV文件目录
            chroma_db_path: ChromaDB数据库路径
            host: ChromaDB远程主机
            port: ChromaDB远程端口
        """
        from mcp.server import Server
        import mcp.types as types
        
        self.server = Server("combined-data-server")
        
        # 初始化子服务器
        self.csv_server = CSVMCPServer(csv_directory=csv_directory)
        self.vector_server = VectorMCPServer(
            chroma_db_path=chroma_db_path,
            host=host,
            port=port
        )
        
        # 注册组合工具
        self._register_tools()
        
    
    def _register_tools(self):
        """注册组合工具"""
        import mcp.types as types
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """返回所有可用工具列表"""
            # 获取CSV工具
            csv_tools = []
            try:
                # 直接调用子服务器注册的工具处理函数
                csv_handler = self.csv_server.server.list_tools
                if csv_handler:
                    csv_tools = await csv_handler()
            except:
                pass
            
            # 获取向量工具
            vector_tools = []
            try:
                # 直接调用子服务器注册的工具处理函数
                vector_handler = self.vector_server.server.list_tools
                if vector_handler:
                    vector_tools = await vector_handler()
            except:
                pass
            
            # 添加组合工具
            combined_tools = [
                types.Tool(
                    name="data_cross_reference",
                    description="在CSV数据和向量数据库之间进行交叉引用查询",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "csv_file_path": {
                                "type": "string",
                                "description": "CSV文件路径"
                            },
                            "collection_name": {
                                "type": "string",
                                "description": "向量集合名称"
                            },
                            "query_text": {
                                "type": "string",
                                "description": "查询文本"
                            },
                            "csv_key_column": {
                                "type": "string",
                                "description": "CSV中的关键列名（用于匹配）"
                            },
                            "vector_metadata_key": {
                                "type": "string",
                                "description": "向量数据库中的元数据键（用于匹配）"
                            }
                        },
                        "required": ["csv_file_path", "collection_name", "query_text"]
                    }
                )
            ]
            
            return csv_tools + vector_tools + combined_tools
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict):
            """处理工具调用"""
            import mcp.types as types
            
            # 如果是CSV工具，转发给CSV服务器
            if name.startswith("csv_"):
                try:
                    csv_handler = self.csv_server.server._handlers.get('tools/call')
                    if csv_handler:
                        return await csv_handler(name, arguments)
                    else:
                        raise ValueError("CSV工具处理器未找到")
                except Exception as e:
                    return [types.TextContent(
                        type="text",
                        text=f"CSV工具调用失败: {str(e)}"
                    )]
            
            # 如果是向量工具，转发给向量服务器
            elif name.startswith("vector_"):
                try:
                    vector_handler = self.vector_server.server._handlers.get('tools/call')
                    if vector_handler:
                        return await vector_handler(name, arguments)
                    else:
                        raise ValueError("向量工具处理器未找到")
                except Exception as e:
                    return [types.TextContent(
                        type="text",
                        text=f"向量工具调用失败: {str(e)}"
                    )]
            
            # 处理组合工具
            elif name == "data_cross_reference":
                return await self._cross_reference_data(arguments)
            
            else:
                return [types.TextContent(
                    type="text",
                    text=f"未知工具: {name}"
                )]
    
    async def _cross_reference_data(self, arguments: dict):
        """执行数据交叉引用"""
        import json
        import mcp.types as types
        
        try:
            csv_file_path = arguments["csv_file_path"]
            collection_name = arguments["collection_name"]
            query_text = arguments["query_text"]
            csv_key_column = arguments.get("csv_key_column", "id")
            vector_metadata_key = arguments.get("vector_metadata_key", "source_id")
            
            # 1. 从向量数据库查询相关文档
            vector_results = await self.vector_server._query_collection({
                "collection_name": collection_name,
                "query_text": query_text,
                "n_results": 10,
                "include": ["documents", "metadatas", "distances"]
            })
            
            if not vector_results or not vector_results[0].text:
                return [types.TextContent(
                    type="text",
                    text="向量查询未返回结果"
                )]
            
            # 解析向量查询结果
            vector_data = json.loads(vector_results[0].text)
            
            if not vector_data.get("results"):
                return [types.TextContent(
                    type="text",
                    text="向量查询未找到匹配结果"
                )]
            
            # 2. 提取向量结果中的关键信息
            vector_keys = []
            for result in vector_data["results"]:
                if result.get("metadata") and vector_metadata_key in result["metadata"]:
                    vector_keys.append(result["metadata"][vector_metadata_key])
            
            if not vector_keys:
                return [types.TextContent(
                    type="text",
                    text=f"向量结果中未找到元数据键: {vector_metadata_key}"
                )]
            
            # 3. 在CSV中查找匹配的行
            csv_query = f"{csv_key_column} in {vector_keys}"
            csv_results = await self.csv_server._query_csv({
                "file_path": csv_file_path,
                "query": csv_query
            })
            
            if not csv_results or not csv_results[0].text:
                return [types.TextContent(
                    type="text",
                    text="CSV查询未返回结果"
                )]
            
            # 解析CSV查询结果
            csv_data = json.loads(csv_results[0].text)
            
            # 4. 合并结果
            combined_results = []
            for vector_result in vector_data["results"]:
                vector_key = vector_result.get("metadata", {}).get(vector_metadata_key)
                
                # 找到对应的CSV数据
                matching_csv_data = None
                for csv_row in csv_data.get("data", []):
                    if str(csv_row.get(csv_key_column)) == str(vector_key):
                        matching_csv_data = csv_row
                        break
                
                combined_item = {
                    "vector_id": vector_result["id"],
                    "vector_document": vector_result["document"],
                    "vector_metadata": vector_result["metadata"],
                    "vector_distance": vector_result["distance"],
                    "csv_data": matching_csv_data,
                    "match_key": vector_key
                }
                combined_results.append(combined_item)
            
            result = {
                "query_text": query_text,
                "csv_file": csv_file_path,
                "vector_collection": collection_name,
                "total_matches": len(combined_results),
                "cross_referenced_data": combined_results
            }
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )]
            
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"交叉引用查询失败: {str(e)}"
            )]
    
    async def run_server(self):
        """运行组合服务器"""
        import mcp.server.stdio
        from mcp.server import NotificationOptions
        from mcp.server.models import InitializationOptions
        
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            init_options = InitializationOptions(
                server_name="combined-data-server",
                server_version="0.1.0",
                capabilities=self.server.get_capabilities(
                    notification_options=NotificationOptions(
                        prompts_changed=True,
                        resources_changed=True,
                        tools_changed=True,
                    ),
                    experimental_capabilities={},
                ),
            )
            
            await self.server.run(
                read_stream,
                write_stream,
                init_options,
            )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MCP服务启动器")
    parser.add_argument("--service", choices=["csv", "vector", "combined"], 
                       default="combined", help="要启动的服务类型")
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
        elif args.service == "combined":
            asyncio.run(launcher.start_combined_server(
                args.csv_dir, args.chroma_db, args.host, args.port
            ))
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"启动服务时发生错误: {e}")


if __name__ == "__main__":
    main() 