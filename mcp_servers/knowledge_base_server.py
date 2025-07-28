"""
知识库MCP服务器
为全局向量知识库管理器提供MCP工具接口
"""

import json
import asyncio
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mcp.server.base import StdioMCPServer
from mcp.types import Tool, ToolInputSchema
from src.tools.knowledge_base_manager import GlobalKnowledgeBase

logger = logging.getLogger(__name__)

class KnowledgeBaseServer(StdioMCPServer):
    """知识库MCP服务器"""
    
    def __init__(self, workspace_dir: str = "./workspace"):
        super().__init__("knowledge-base-server")
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(exist_ok=True)
        
        # 初始化知识库管理器
        self.knowledge_base = GlobalKnowledgeBase(str(self.workspace_dir))
        
        self._register_tools()
        
        logger.info("知识库MCP服务器初始化完成")
    
    def _register_tools(self):
        """注册知识库相关工具"""
        
        # 创建集合工具
        create_collection_tool = Tool(
            name="create_knowledge_collection",
            description="创建新的知识集合",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "name": {"type": "string", "description": "集合名称"},
                    "description": {"type": "string", "description": "集合描述"},
                    "metadata": {"type": "object", "description": "集合元数据"}
                },
                required=["name"]
            )
        )
        self.register_tool(create_collection_tool)
        
        # 添加文档工具
        add_documents_tool = Tool(
            name="add_knowledge_documents",
            description="向知识集合添加文档",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "collection_name": {"type": "string", "description": "集合名称"},
                    "documents": {"type": "array", "items": {"type": "string"}, "description": "文档内容列表"},
                    "metadatas": {"type": "array", "items": {"type": "object"}, "description": "文档元数据列表"},
                    "ids": {"type": "array", "items": {"type": "string"}, "description": "文档ID列表"},
                    "auto_split": {"type": "boolean", "default": True, "description": "是否自动分割长文档"},
                    "split_separator": {"type": "string", "default": "\n", "description": "文本分割符"}
                },
                required=["collection_name", "documents"]
            )
        )
        self.register_tool(add_documents_tool)
        
        # 查询文档工具
        query_documents_tool = Tool(
            name="query_knowledge_documents",
            description="查询知识库文档",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "collection_name": {"type": "string", "description": "集合名称"},
                    "query_text": {"type": "string", "description": "查询文本"},
                    "n_results": {"type": "integer", "default": 5, "description": "返回结果数量"},
                    "filter_metadata": {"type": "object", "description": "元数据过滤条件"}
                },
                required=["collection_name", "query_text"]
            )
        )
        self.register_tool(query_documents_tool)
        
        # 列出集合工具
        list_collections_tool = Tool(
            name="list_knowledge_collections",
            description="列出所有知识集合",
            inputSchema=ToolInputSchema(
                type="object",
                properties={}
            )
        )
        self.register_tool(list_collections_tool)
        
        # 获取集合信息工具
        get_collection_info_tool = Tool(
            name="get_knowledge_collection_info",
            description="获取知识集合详细信息",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "name": {"type": "string", "description": "集合名称"}
                },
                required=["name"]
            )
        )
        self.register_tool(get_collection_info_tool)
        
        # 删除集合工具
        delete_collection_tool = Tool(
            name="delete_knowledge_collection",
            description="删除知识集合",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "name": {"type": "string", "description": "集合名称"}
                },
                required=["name"]
            )
        )
        self.register_tool(delete_collection_tool)
        
        # 从文件导入知识工具
        import_from_file_tool = Tool(
            name="import_knowledge_from_file",
            description="从文本文件导入知识到指定集合",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "collection_name": {"type": "string", "description": "集合名称"},
                    "file_path": {"type": "string", "description": "文件路径"},
                    "separator": {"type": "string", "default": "\n", "description": "文本分割符"},
                    "encoding": {"type": "string", "default": "utf-8", "description": "文件编码"}
                },
                required=["collection_name", "file_path"]
            )
        )
        self.register_tool(import_from_file_tool)
        
        # 文本分割工具
        split_text_tool = Tool(
            name="split_knowledge_text",
            description="分割长文本为小块",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "text": {"type": "string", "description": "要分割的文本"},
                    "separator": {"type": "string", "default": "\n", "description": "分割符"},
                    "chunk_size": {"type": "integer", "default": 1000, "description": "每个块的最大字符数"},
                    "overlap": {"type": "integer", "default": 100, "description": "块之间的重叠字符数"}
                },
                required=["text"]
            )
        )
        self.register_tool(split_text_tool)
    
    async def _call_tool(self, name: str, arguments: Dict[str, Any], context) -> Dict[str, Any]:
        """处理工具调用"""
        try:
            if name == "create_knowledge_collection":
                return await self._create_collection(arguments)
            elif name == "add_knowledge_documents":
                return await self._add_documents(arguments)
            elif name == "query_knowledge_documents":
                return await self._query_documents(arguments)
            elif name == "list_knowledge_collections":
                return await self._list_collections(arguments)
            elif name == "get_knowledge_collection_info":
                return await self._get_collection_info(arguments)
            elif name == "delete_knowledge_collection":
                return await self._delete_collection(arguments)
            elif name == "import_knowledge_from_file":
                return await self._import_from_file(arguments)
            elif name == "split_knowledge_text":
                return await self._split_text(arguments)
            else:
                return {"error": f"未知工具: {name}"}
                
        except Exception as e:
            logger.error(f"工具调用失败 {name}: {e}")
            return {"error": str(e)}
    
    async def _create_collection(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """创建知识集合"""
        name = args.get("name")
        description = args.get("description", "")
        metadata = args.get("metadata", {})
        
        success = await self.knowledge_base.create_collection(
            name=name,
            description=description,
            metadata=metadata
        )
        
        if success:
            return {
                "success": True,
                "message": f"成功创建知识集合: {name}",
                "collection_name": name
            }
        else:
            return {
                "success": False,
                "error": f"创建知识集合失败: {name}"
            }
    
    async def _add_documents(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """添加文档到知识集合"""
        collection_name = args.get("collection_name")
        documents = args.get("documents", [])
        metadatas = args.get("metadatas")
        ids = args.get("ids")
        auto_split = args.get("auto_split", True)
        split_separator = args.get("split_separator", "\n")
        
        success = await self.knowledge_base.add_documents(
            collection_name=collection_name,
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            auto_split=auto_split,
            split_separator=split_separator
        )
        
        if success:
            return {
                "success": True,
                "message": f"成功添加 {len(documents)} 个文档到集合 {collection_name}",
                "added_count": len(documents)
            }
        else:
            return {
                "success": False,
                "error": f"添加文档到集合 {collection_name} 失败"
            }
    
    async def _query_documents(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """查询知识库文档"""
        collection_name = args.get("collection_name")
        query_text = args.get("query_text")
        n_results = args.get("n_results", 5)
        filter_metadata = args.get("filter_metadata")
        
        results = await self.knowledge_base.query_documents(
            collection_name=collection_name,
            query_text=query_text,
            n_results=n_results,
            filter_metadata=filter_metadata
        )
        
        return {
            "success": True,
            "results": results,
            "query_text": query_text,
            "collection_name": collection_name,
            "result_count": len(results)
        }
    
    async def _list_collections(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """列出所有知识集合"""
        collections = self.knowledge_base.list_collections()
        
        collections_data = []
        for coll in collections:
            collections_data.append({
                "name": coll.name,
                "description": coll.description,
                "document_count": coll.document_count,
                "created_at": coll.created_at,
                "metadata": coll.metadata
            })
        
        return {
            "success": True,
            "collections": collections_data,
            "total_count": len(collections_data)
        }
    
    async def _get_collection_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """获取集合详细信息"""
        name = args.get("name")
        
        collection_info = self.knowledge_base.get_collection_info(name)
        
        if collection_info:
            return {
                "success": True,
                "collection": {
                    "name": collection_info.name,
                    "description": collection_info.description,
                    "document_count": collection_info.document_count,
                    "created_at": collection_info.created_at,
                    "metadata": collection_info.metadata
                }
            }
        else:
            return {
                "success": False,
                "error": f"集合 {name} 不存在"
            }
    
    async def _delete_collection(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """删除知识集合"""
        name = args.get("name")
        
        success = await self.knowledge_base.delete_collection(name)
        
        if success:
            return {
                "success": True,
                "message": f"成功删除知识集合: {name}"
            }
        else:
            return {
                "success": False,
                "error": f"删除知识集合失败: {name}"
            }
    
    async def _import_from_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """从文件导入知识"""
        collection_name = args.get("collection_name")
        file_path = args.get("file_path")
        separator = args.get("separator", "\n")
        encoding = args.get("encoding", "utf-8")
        
        success = await self.knowledge_base.import_from_text_file(
            collection_name=collection_name,
            file_path=file_path,
            separator=separator,
            encoding=encoding
        )
        
        if success:
            return {
                "success": True,
                "message": f"成功从文件 {file_path} 导入知识到集合 {collection_name}"
            }
        else:
            return {
                "success": False,
                "error": f"从文件 {file_path} 导入知识失败"
            }
    
    async def _split_text(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """分割文本"""
        text = args.get("text")
        separator = args.get("separator", "\n")
        chunk_size = args.get("chunk_size", 1000)
        overlap = args.get("overlap", 100)
        
        chunks = self.knowledge_base.split_text(
            text=text,
            separator=separator,
            chunk_size=chunk_size,
            overlap=overlap
        )
        
        return {
            "success": True,
            "chunks": chunks,
            "chunk_count": len(chunks),
            "original_length": len(text)
        }

# 如果直接运行此文件，启动服务器
if __name__ == "__main__":
    import asyncio
    
    async def main():
        server = KnowledgeBaseServer()
        await server.run()
    
    asyncio.run(main()) 