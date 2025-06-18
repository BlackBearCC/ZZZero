"""
向量查询 MCP 服务器
提供ChromaDB向量数据库查询、搜索、管理等功能的MCP服务
"""

import asyncio
import os
import sys
import json
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import logging

# 添加父目录到sys.path以便导入mcp模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.stdio_server import StdioMCPServer
from mcp_servers.mcp_types import (
    ServerInfo, ServerCapabilities, ToolsCapability, 
    Tool, ToolInputSchema, ToolContent,
    JSONRPCRequest, JSONRPCResponse, MCPMethods
)

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None


class VectorMCPServer(StdioMCPServer):
    """向量查询MCP服务器类"""
    
    def __init__(self, chroma_db_path: str = None, host: str = None, port: int = None):
        """
        初始化向量MCP服务器
        
        Args:
            chroma_db_path: ChromaDB本地数据库路径
            host: ChromaDB服务器主机地址（用于远程连接）
            port: ChromaDB服务器端口号（用于远程连接）
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB未安装，请运行: pip install chromadb")
            
        # 初始化基类
        server_info = ServerInfo(
            name="vector-query-server",
            version="0.1.0"
        )
        capabilities = ServerCapabilities(
            tools=ToolsCapability(list_changed=True)
        )
        super().__init__(server_info, capabilities)
        
        self.chroma_db_path = chroma_db_path or "./chroma_db"
        self.host = host
        self.port = port
        self.client = None
        self.collections_cache = {}
        
        # 初始化ChromaDB客户端
        self._init_chroma_client()
        
        # 注册工具
        self._register_tools()
        
    def _init_chroma_client(self):
        """初始化ChromaDB客户端"""
        try:
            if self.host and self.port:
                # 远程连接
                self.client = chromadb.HttpClient(host=self.host, port=self.port)
            else:
                # 本地连接，禁用遥测功能
                settings = Settings()
                settings.anonymized_telemetry = False
                self.client = chromadb.PersistentClient(
                    path=self.chroma_db_path,
                    settings=settings
                )
        except Exception as e:
            logging.error(f"初始化ChromaDB客户端失败: {e}")
            self.client = None
    
    def _register_tools(self):
        """注册MCP工具"""
        
        # 注册工具列表处理器
        async def handle_list_tools(request: JSONRPCRequest) -> JSONRPCResponse:
            """返回可用的向量查询工具列表"""
            tools = [
                Tool(
                    name="vector_list_collections",
                    description="列出所有可用的向量集合",
                    inputSchema=ToolInputSchema(
                        type="object",
                        properties={}
                    )
                ),
                Tool(
                    name="vector_query",
                    description="在指定集合中执行向量相似性搜索",
                    inputSchema=ToolInputSchema(
                        type="object",
                        properties={
                            "collection_name": {
                                "type": "string",
                                "description": "集合名称"
                            },
                            "query_text": {
                                "type": "string",
                                "description": "查询文本"
                            },
                            "n_results": {
                                "type": "integer",
                                "description": "返回结果数量（默认5）"
                            }
                        },
                        required=["collection_name", "query_text"]
                    )
                )
            ]
            
            return JSONRPCResponse(
                id=request.id,
                result={"tools": [tool.dict() for tool in tools]}
            )
        
        # 注册工具调用处理器
        async def handle_call_tool(request: JSONRPCRequest) -> JSONRPCResponse:
            """处理工具调用"""
            if not self.client:
                content = [ToolContent(
                    type="text",
                    text="ChromaDB客户端未初始化，请检查配置"
                )]
                return JSONRPCResponse(
                    id=request.id,
                    result={"content": [c.dict() for c in content]}
                )
            
            try:
                params = request.params or {}
                name = params.get("name")
                arguments = params.get("arguments", {})
                
                if name == "vector_list_collections":
                    content = await self._list_collections(arguments)
                elif name == "vector_query":
                    content = await self._query_collection(arguments)
                else:
                    raise ValueError(f"未知工具: {name}")
                
                return JSONRPCResponse(
                    id=request.id,
                    result={"content": [c.dict() for c in content]}
                )
            except Exception as e:
                content = [ToolContent(
                    type="text",
                    text=f"执行工具 {name} 时发生错误: {str(e)}"
                )]
                return JSONRPCResponse(
                    id=request.id,
                    result={"content": [c.dict() for c in content]}
                )
        
        # 注册处理器
        self.register_handler(MCPMethods.TOOLS_LIST, handle_list_tools)
        self.register_handler(MCPMethods.TOOLS_CALL, handle_call_tool)
    
    async def _list_collections(self, arguments: dict) -> list[ToolContent]:
        """列出所有集合"""
        try:
            collections = self.client.list_collections()
            
            collection_info = []
            for collection in collections:
                info = {
                    "name": collection.name,
                    "id": str(collection.id),
                    "count": collection.count()
                }
                collection_info.append(info)
            
            result = {
                "total_collections": len(collection_info),
                "collections": collection_info
            }
            
            return [ToolContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )]
        except Exception as e:
            return [ToolContent(
                type="text",
                text=f"列出集合时发生错误: {str(e)}"
            )]
    
    async def _query_collection(self, arguments: dict) -> list[ToolContent]:
        """查询集合"""
        collection_name = arguments["collection_name"]
        query_text = arguments["query_text"]
        n_results = arguments.get("n_results", 5)
        
        try:
            collection = self.client.get_collection(name=collection_name)
            
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            # 格式化结果
            formatted_results = []
            if results["ids"] and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    item = {
                        "id": results["ids"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else None,
                        "document": results["documents"][0][i] if "documents" in results else None,
                        "metadata": results["metadatas"][0][i] if "metadatas" in results else None
                    }
                    formatted_results.append(item)
            
            result = {
                "collection_name": collection_name,
                "query_text": query_text,
                "total_results": len(formatted_results),
                "results": formatted_results
            }
            
            return [ToolContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )]
        except Exception as e:
            return [ToolContent(
                type="text",
                text=f"查询集合时发生错误: {str(e)}"
            )]


async def main():
    """主函数"""
    print("启动向量MCP服务器...")
    vector_server = VectorMCPServer()
    await vector_server.run()


if __name__ == "__main__":
    # 创建并运行向量MCP服务器
    asyncio.run(main()) 