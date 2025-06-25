#!/usr/bin/env python3
"""
高级ChromaDB向量数据库服务器 - 基于MCP服务基类实现CRUD操作
支持向量存储、语义搜索、集合管理、文档嵌入等功能
"""
import os
import json
import uuid
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import asyncio
import logging

# ChromaDB相关导入
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# 导入MCP基类和类型
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from mcp.server.stdio_server import StdioMCPServer
from mcp.types import Tool, Resource, JSONSchema, ToolInputSchema

logger = logging.getLogger(__name__)


class ChromaDBManager:
    """ChromaDB管理器 - 提供高级向量数据库操作"""
    
    def __init__(self, data_dir: str = "./workspace/vectordb"):
        """
        初始化ChromaDB管理器
        
        Args:
            data_dir: ChromaDB数据存储目录，默认存储到workspace/vectordb
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB未安装，请运行: pip install chromadb")
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化ChromaDB客户端
        self.client = chromadb.PersistentClient(
            path=str(self.data_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 嵌入函数选择
        self.embedding_functions = {
            'default': embedding_functions.DefaultEmbeddingFunction(),
            'sentence_transformers': self._get_sentence_transformer_ef(),
            'openai': self._get_openai_ef(),
            'huggingface': self._get_huggingface_ef()
        }
        
        self._collections_cache = {}
        logger.info(f"ChromaDB管理器初始化完成: {data_dir}")
    
    def _get_sentence_transformer_ef(self):
        """获取Sentence Transformer嵌入函数（使用BGE中文模型）"""
        try:
            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="BAAI/bge-small-zh-v1.5"
            )
        except Exception as e:
            logger.warning(f"BGE Sentence Transformer不可用，尝试使用默认模型: {e}")
            try:
                # 回退到默认模型
                return embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="all-MiniLM-L6-v2"
                )
            except Exception as e2:
                logger.warning(f"默认Sentence Transformer也不可用: {e2}")
                return None
    
    def _get_openai_ef(self):
        """获取OpenAI嵌入函数"""
        try:
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if openai_api_key:
                return embedding_functions.OpenAIEmbeddingFunction(
                    api_key=openai_api_key,
                    model_name="text-embedding-ada-002"
                )
        except Exception as e:
            logger.warning(f"OpenAI嵌入函数不可用: {e}")
        return None
    
    def _get_huggingface_ef(self):
        """获取HuggingFace嵌入函数（使用BGE中文模型）"""
        try:
            return embedding_functions.HuggingFaceEmbeddingFunction(
                model_name="BAAI/bge-small-zh-v1.5"
            )
        except Exception as e:
            logger.warning(f"BGE HuggingFace嵌入函数不可用，尝试使用默认模型: {e}")
            try:
                # 回退到默认模型
                return embedding_functions.HuggingFaceEmbeddingFunction(
                    model_name="sentence-transformers/all-MiniLM-L6-v2"
                )
            except Exception as e2:
                logger.warning(f"默认HuggingFace嵌入函数也不可用: {e2}")
                return None
    
    def create_collection(self, name: str, 
                         embedding_function: str = 'default',
                         metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建新的集合"""
        try:
            # 选择嵌入函数
            ef = self.embedding_functions.get(embedding_function)
            if ef is None:
                ef = self.embedding_functions['default']
                logger.warning(f"嵌入函数 '{embedding_function}' 不可用，使用默认函数")
            
            # 处理metadata - 某些版本的ChromaDB不接受空的metadata
            collection_metadata = metadata or {"created_by": "mcp_server"}
            
            collection = self.client.create_collection(
                name=name,
                embedding_function=ef,
                metadata=collection_metadata
            )
            
            self._collections_cache[name] = collection
            
            return {
                'collection_name': name,
                'embedding_function': embedding_function,
                'metadata': metadata or {},
                'created_at': datetime.now().isoformat(),
                'count': 0
            }
            
        except Exception as e:
            if "already exists" in str(e):
                raise ValueError(f"集合 '{name}' 已存在")
            raise ValueError(f"创建集合失败: {e}")
    
    def get_collection(self, name: str):
        """获取集合对象"""
        if name in self._collections_cache:
            return self._collections_cache[name]
        
        try:
            collection = self.client.get_collection(name)
            self._collections_cache[name] = collection
            return collection
        except Exception as e:
            raise ValueError(f"集合 '{name}' 不存在: {e}")
    
    def add_documents(self, collection_name: str,
                     documents: List[str],
                     ids: Optional[List[str]] = None,
                     metadatas: Optional[List[Dict[str, Any]]] = None,
                     embeddings: Optional[List[List[float]]] = None) -> Dict[str, Any]:
        """向集合添加文档"""
        collection = self.get_collection(collection_name)
        
        # 生成ID（如果未提供）
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        
        # 验证长度匹配
        if len(ids) != len(documents):
            raise ValueError("IDs数量必须与文档数量匹配")
        
        if metadatas and len(metadatas) != len(documents):
            raise ValueError("元数据数量必须与文档数量匹配")
        
        if embeddings and len(embeddings) != len(documents):
            raise ValueError("嵌入向量数量必须与文档数量匹配")
        
        try:
            collection.add(
                documents=documents,
                ids=ids,
                metadatas=metadatas,
                embeddings=embeddings
            )
            
            return {
                'collection_name': collection_name,
                'documents_added': len(documents),
                'ids': ids,
                'total_count': collection.count(),
                'added_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise ValueError(f"添加文档失败: {e}")
    
    def query_documents(self, collection_name: str,
                       query_texts: Optional[List[str]] = None,
                       query_embeddings: Optional[List[List[float]]] = None,
                       n_results: int = 10,
                       where: Optional[Dict[str, Any]] = None,
                       where_document: Optional[Dict[str, Any]] = None,
                       include: Optional[List[str]] = None) -> Dict[str, Any]:
        """查询文档"""
        collection = self.get_collection(collection_name)
        
        if not query_texts and not query_embeddings:
            raise ValueError("必须提供查询文本或查询嵌入向量")
        
        try:
            results = collection.query(
                query_texts=query_texts,
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=include or ["documents", "metadatas", "distances"]
            )
            
            return {
                'collection_name': collection_name,
                'query_texts': query_texts,
                'n_results': n_results,
                'results': results,
                'queried_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise ValueError(f"查询文档失败: {e}")
    
    def update_documents(self, collection_name: str,
                        ids: List[str],
                        documents: Optional[List[str]] = None,
                        metadatas: Optional[List[Dict[str, Any]]] = None,
                        embeddings: Optional[List[List[float]]] = None) -> Dict[str, Any]:
        """更新文档"""
        collection = self.get_collection(collection_name)
        
        try:
            collection.update(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings
            )
            
            return {
                'collection_name': collection_name,
                'documents_updated': len(ids),
                'ids': ids,
                'updated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise ValueError(f"更新文档失败: {e}")
    
    def delete_documents(self, collection_name: str,
                        ids: Optional[List[str]] = None,
                        where: Optional[Dict[str, Any]] = None,
                        where_document: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """删除文档"""
        collection = self.get_collection(collection_name)
        
        if not ids and not where and not where_document:
            raise ValueError("必须提供删除条件")
        
        try:
            # 获取删除前的数量
            before_count = collection.count()
            
            collection.delete(
                ids=ids,
                where=where,
                where_document=where_document
            )
            
            after_count = collection.count()
            deleted_count = before_count - after_count
            
            return {
                'collection_name': collection_name,
                'documents_deleted': deleted_count,
                'remaining_count': after_count,
                'deleted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise ValueError(f"删除文档失败: {e}")
    
    def get_documents(self, collection_name: str,
                     ids: Optional[List[str]] = None,
                     where: Optional[Dict[str, Any]] = None,
                     where_document: Optional[Dict[str, Any]] = None,
                     include: Optional[List[str]] = None,
                     limit: Optional[int] = None,
                     offset: Optional[int] = None) -> Dict[str, Any]:
        """获取文档"""
        collection = self.get_collection(collection_name)
        
        try:
            results = collection.get(
                ids=ids,
                where=where,
                where_document=where_document,
                include=include or ["documents", "metadatas"],
                limit=limit,
                offset=offset
            )
            
            return {
                'collection_name': collection_name,
                'results': results,
                'total_count': collection.count(),
                'returned_count': len(results.get('ids', [])),
                'retrieved_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise ValueError(f"获取文档失败: {e}")
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """获取集合信息"""
        collection = self.get_collection(collection_name)
        
        try:
            count = collection.count()
            metadata = collection.metadata or {}
            
            # 获取一些示例文档来分析
            sample = collection.peek(limit=5)
            
            return {
                'collection_name': collection_name,
                'document_count': count,
                'metadata': metadata,
                'sample_documents': sample,
                'embedding_function': str(collection._embedding_function),
                'retrieved_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise ValueError(f"获取集合信息失败: {e}")
    
    def list_collections(self) -> List[Dict[str, Any]]:
        """列出所有集合"""
        try:
            collections = self.client.list_collections()
            
            result = []
            for collection in collections:
                try:
                    info = {
                        'name': collection.name,
                        'count': collection.count(),
                        'metadata': collection.metadata or {}
                    }
                    result.append(info)
                except Exception as e:
                    result.append({
                        'name': collection.name,
                        'error': str(e)
                    })
            
            return result
            
        except Exception as e:
            raise ValueError(f"列出集合失败: {e}")
    
    def delete_collection(self, collection_name: str) -> Dict[str, Any]:
        """删除集合"""
        try:
            # 获取删除前的信息
            collection = self.get_collection(collection_name)
            count = collection.count()
            
            # 删除集合
            self.client.delete_collection(collection_name)
            
            # 从缓存中移除
            if collection_name in self._collections_cache:
                del self._collections_cache[collection_name]
            
            return {
                'collection_name': collection_name,
                'documents_deleted': count,
                'deleted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise ValueError(f"删除集合失败: {e}")
    
    def create_embeddings(self, texts: List[str], 
                         embedding_function: str = 'default') -> Dict[str, Any]:
        """为文本创建嵌入向量"""
        ef = self.embedding_functions.get(embedding_function)
        if ef is None:
            ef = self.embedding_functions['default']
        
        try:
            embeddings = ef(texts)
            
            return {
                'texts': texts,
                'embeddings': embeddings,
                'embedding_function': embedding_function,
                'dimensions': len(embeddings[0]) if embeddings else 0,
                'created_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise ValueError(f"创建嵌入向量失败: {e}")


class ChromaDBCRUDServer(StdioMCPServer):
    """ChromaDB向量数据库MCP服务器"""
    
    def __init__(self, data_dir: str = "./workspace/vectordb"):
        """
        初始化ChromaDB CRUD服务器
        
        Args:
            data_dir: ChromaDB数据存储目录，默认存储到workspace/vectordb
        """
        super().__init__(
            name="chromadb_crud_server",
            version="1.0.0"
        )
        
        self.db = ChromaDBManager(data_dir)
        self._register_chromadb_tools()
    
    def _register_chromadb_tools(self):
        """注册ChromaDB操作工具"""
        
        # 创建集合工具
        create_collection_tool = Tool(
            name="create_collection",
            description="创建新的ChromaDB集合",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "name": {"type": "string", "description": "集合名称"},
                    "embedding_function": {
                        "type": "string",
                        "enum": ["default", "sentence_transformers", "openai", "huggingface"],
                        "default": "default",
                        "description": "嵌入函数类型"
                    },
                    "metadata": {"type": "object", "description": "集合元数据"}
                },
                required=["name"]
            )
        )
        self.register_tool(create_collection_tool)
        
        # 添加文档工具
        add_documents_tool = Tool(
            name="add_documents",
            description="向集合添加文档",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "collection_name": {"type": "string", "description": "集合名称"},
                    "documents": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "文档文本列表"
                    },
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "文档ID列表（可选）"
                    },
                    "metadatas": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "文档元数据列表（可选）"
                    }
                },
                required=["collection_name", "documents"]
            )
        )
        self.register_tool(add_documents_tool)
        
        # 查询文档工具
        query_documents_tool = Tool(
            name="query_documents",
            description="查询相似文档",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "collection_name": {"type": "string", "description": "集合名称"},
                    "query_texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "查询文本列表"
                    },
                    "n_results": {"type": "integer", "default": 10, "description": "返回结果数量"},
                    "where": {"type": "object", "description": "元数据过滤条件"},
                    "where_document": {"type": "object", "description": "文档内容过滤条件"}
                },
                required=["collection_name", "query_texts"]
            )
        )
        self.register_tool(query_documents_tool)
        
        # 更新文档工具
        update_documents_tool = Tool(
            name="update_documents",
            description="更新文档",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "collection_name": {"type": "string", "description": "集合名称"},
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要更新的文档ID列表"
                    },
                    "documents": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "新的文档文本列表（可选）"
                    },
                    "metadatas": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "新的元数据列表（可选）"
                    }
                },
                required=["collection_name", "ids"]
            )
        )
        self.register_tool(update_documents_tool)
        
        # 删除文档工具
        delete_documents_tool = Tool(
            name="delete_documents",
            description="删除文档",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "collection_name": {"type": "string", "description": "集合名称"},
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要删除的文档ID列表（可选）"
                    },
                    "where": {"type": "object", "description": "元数据删除条件（可选）"},
                    "where_document": {"type": "object", "description": "文档内容删除条件（可选）"}
                },
                required=["collection_name"]
            )
        )
        self.register_tool(delete_documents_tool)
        
        # 获取文档工具
        get_documents_tool = Tool(
            name="get_documents",
            description="获取文档",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "collection_name": {"type": "string", "description": "集合名称"},
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "文档ID列表（可选）"
                    },
                    "where": {"type": "object", "description": "元数据过滤条件（可选）"},
                    "limit": {"type": "integer", "description": "返回数量限制"},
                    "offset": {"type": "integer", "description": "偏移量"}
                },
                required=["collection_name"]
            )
        )
        self.register_tool(get_documents_tool)
        
        # 获取集合信息工具
        get_collection_info_tool = Tool(
            name="get_collection_info",
            description="获取集合详细信息",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "collection_name": {"type": "string", "description": "集合名称"}
                },
                required=["collection_name"]
            )
        )
        self.register_tool(get_collection_info_tool)
        
        # 列出集合工具
        list_collections_tool = Tool(
            name="list_collections",
            description="列出所有集合",
            inputSchema=ToolInputSchema(
                type="object",
                properties={}
            )
        )
        self.register_tool(list_collections_tool)
        
        # 删除集合工具
        delete_collection_tool = Tool(
            name="delete_collection",
            description="删除集合",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "collection_name": {"type": "string", "description": "集合名称"}
                },
                required=["collection_name"]
            )
        )
        self.register_tool(delete_collection_tool)
        
        # 创建嵌入向量工具
        create_embeddings_tool = Tool(
            name="create_embeddings",
            description="为文本创建嵌入向量",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "texts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要处理的文本列表"
                    },
                    "embedding_function": {
                        "type": "string",
                        "enum": ["default", "sentence_transformers", "openai", "huggingface"],
                        "default": "default",
                        "description": "嵌入函数类型"
                    }
                },
                required=["texts"]
            )
        )
        self.register_tool(create_embeddings_tool)
    
    async def _call_tool(self, name: str, arguments: Dict[str, Any], context) -> Dict[str, Any]:
        """处理工具调用"""
        try:
            if name == "create_collection":
                # 支持两种参数名称：name 和 collection_name（向后兼容）
                collection_name = arguments.get("name") or arguments.get("collection_name")
                if not collection_name:
                    raise ValueError("缺少必需参数：name 或 collection_name")
                
                result = self.db.create_collection(
                    collection_name,
                    arguments.get("embedding_function", "default"),
                    arguments.get("metadata")
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "add_documents":
                result = self.db.add_documents(
                    arguments["collection_name"],
                    arguments["documents"],
                    arguments.get("ids"),
                    arguments.get("metadatas")
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "query_documents":
                result = self.db.query_documents(
                    arguments["collection_name"],
                    arguments["query_texts"],
                    n_results=arguments.get("n_results", 10),
                    where=arguments.get("where"),
                    where_document=arguments.get("where_document")
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "update_documents":
                result = self.db.update_documents(
                    arguments["collection_name"],
                    arguments["ids"],
                    arguments.get("documents"),
                    arguments.get("metadatas")
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "delete_documents":
                result = self.db.delete_documents(
                    arguments["collection_name"],
                    arguments.get("ids"),
                    arguments.get("where"),
                    arguments.get("where_document")
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "get_documents":
                result = self.db.get_documents(
                    arguments["collection_name"],
                    arguments.get("ids"),
                    arguments.get("where"),
                    limit=arguments.get("limit"),
                    offset=arguments.get("offset")
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "get_collection_info":
                result = self.db.get_collection_info(arguments["collection_name"])
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "list_collections":
                result = self.db.list_collections()
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "delete_collection":
                result = self.db.delete_collection(arguments["collection_name"])
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "create_embeddings":
                result = self.db.create_embeddings(
                    arguments["texts"],
                    arguments.get("embedding_function", "default")
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            else:
                raise ValueError(f"未知工具: {name}")
        
        except Exception as e:
            logger.error(f"工具调用失败 {name}: {e}")
            return {
                "content": [{"type": "text", "text": f"错误: {str(e)}"}],
                "isError": True
            }


async def main():
    """启动ChromaDB CRUD服务器"""
    server = ChromaDBCRUDServer("./workspace/vectordb")
    
    try:
        logger.info("启动ChromaDB CRUD服务器...")
        await server.start()
    except KeyboardInterrupt:
        logger.info("接收到停止信号")
    except Exception as e:
        logger.error(f"服务器错误: {e}")
    finally:
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())