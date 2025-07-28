"""
全局向量知识库管理器
支持多集合管理、文本分割、知识库选择等功能
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class KnowledgeDocument:
    """知识文档数据结构"""
    id: str
    content: str
    metadata: Dict[str, Any]
    collection_name: str
    created_at: str = ""
    updated_at: str = ""

@dataclass
class KnowledgeCollection:
    """知识集合信息"""
    name: str
    description: str
    document_count: int
    created_at: str
    metadata: Dict[str, Any]

class GlobalKnowledgeBase:
    """全局向量知识库管理器"""
    
    def __init__(self, workspace_dir: str = "./workspace"):
        """
        初始化全局知识库管理器
        
        Args:
            workspace_dir: 工作空间目录路径
        """
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(exist_ok=True)
        
        # 向量数据库存储路径
        self.vectordb_dir = self.workspace_dir / "vectordb"
        self.vectordb_dir.mkdir(exist_ok=True)
        
        # 知识库配置文件路径
        self.config_file = self.workspace_dir / "knowledge_base_config.json"
        
        # ChromaDB客户端
        self.chroma_client = None
        self.collections_cache: Dict[str, Any] = {}
        
        # 知识库配置
        self.collections_config: Dict[str, KnowledgeCollection] = {}
        
        # 初始化
        self._init_chromadb()
        self._load_config()
        
        logger.info(f"全局知识库管理器初始化完成: {workspace_dir}")
    
    def _init_chromadb(self):
        """初始化ChromaDB客户端"""
        if not CHROMADB_AVAILABLE:
            logger.error("ChromaDB未安装，请运行: pip install chromadb")
            return
        
        try:
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.vectordb_dir),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info("ChromaDB客户端初始化成功")
        except Exception as e:
            logger.error(f"ChromaDB初始化失败: {e}")
            self.chroma_client = None
    
    def _load_config(self):
        """加载知识库配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 重建集合配置对象
                for name, data in config_data.get('collections', {}).items():
                    self.collections_config[name] = KnowledgeCollection(**data)
                
                logger.info(f"已加载知识库配置，共{len(self.collections_config)}个集合")
            except Exception as e:
                logger.error(f"加载知识库配置失败: {e}")
        else:
            # 创建默认配置
            self._save_config()
    
    def _save_config(self):
        """保存知识库配置"""
        config_data = {
            'collections': {
                name: {
                    'name': coll.name,
                    'description': coll.description,
                    'document_count': coll.document_count,
                    'created_at': coll.created_at,
                    'metadata': coll.metadata
                }
                for name, coll in self.collections_config.items()
            },
            'updated_at': datetime.now().isoformat()
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存知识库配置失败: {e}")
    
    def split_text(self, text: str, separator: str = "\n", chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """
        文本分割方法
        
        Args:
            text: 要分割的文本
            separator: 分割符，默认为换行符
            chunk_size: 每个块的最大字符数
            overlap: 块之间的重叠字符数
            
        Returns:
            分割后的文本块列表
        """
        if not text.strip():
            return []
        
        # 首先按分割符分割
        parts = text.split(separator)
        
        chunks = []
        current_chunk = ""
        
        for part in parts:
            # 如果单个部分就超过chunk_size，需要进一步分割
            if len(part) > chunk_size:
                # 先添加当前已有的chunk
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # 对长部分进行字符级分割
                for i in range(0, len(part), chunk_size - overlap):
                    sub_chunk = part[i:i + chunk_size]
                    if sub_chunk.strip():
                        chunks.append(sub_chunk.strip())
            else:
                # 检查添加这部分后是否超过限制
                if len(current_chunk) + len(part) + 1 > chunk_size:
                    # 添加当前chunk并开始新的chunk
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                    current_chunk = part
                else:
                    # 添加到当前chunk
                    if current_chunk:
                        current_chunk += separator + part
                    else:
                        current_chunk = part
        
        # 添加最后的chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def create_collection(self, 
                              name: str, 
                              description: str = "", 
                              metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        创建新的知识集合
        
        Args:
            name: 集合名称
            description: 集合描述
            metadata: 集合元数据
            
        Returns:
            是否创建成功
        """
        if not self.chroma_client:
            logger.error("ChromaDB客户端未初始化")
            return False
        
        try:
            # 检查集合是否已存在
            if name in self.collections_config:
                logger.warning(f"集合 '{name}' 已存在")
                return False
            
            # 创建ChromaDB集合
            collection_metadata = metadata or {}
            collection_metadata.update({
                "description": description,
                "created_at": datetime.now().isoformat()
            })
            
            collection = self.chroma_client.create_collection(
                name=name,
                metadata=collection_metadata
            )
            
            # 缓存集合对象
            self.collections_cache[name] = collection
            
            # 更新配置
            self.collections_config[name] = KnowledgeCollection(
                name=name,
                description=description,
                document_count=0,
                created_at=datetime.now().isoformat(),
                metadata=metadata or {}
            )
            
            self._save_config()
            
            logger.info(f"成功创建知识集合: {name}")
            return True
            
        except Exception as e:
            logger.error(f"创建知识集合失败: {e}")
            return False
    
    async def add_documents(self, 
                           collection_name: str, 
                           documents: List[str], 
                           metadatas: Optional[List[Dict[str, Any]]] = None,
                           ids: Optional[List[str]] = None,
                           auto_split: bool = True,
                           split_separator: str = "\n") -> bool:
        """
        向集合添加文档
        
        Args:
            collection_name: 集合名称
            documents: 文档列表
            metadatas: 元数据列表
            ids: 文档ID列表
            auto_split: 是否自动分割长文档
            split_separator: 分割符
            
        Returns:
            是否添加成功
        """
        if not self.chroma_client:
            logger.error("ChromaDB客户端未初始化")
            return False
        
        try:
            # 获取集合
            collection = await self._get_collection(collection_name)
            if not collection:
                return False
            
            # 处理文档分割
            final_documents = []
            final_metadatas = []
            final_ids = []
            
            for i, doc in enumerate(documents):
                doc_metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                doc_id_prefix = ids[i] if ids and i < len(ids) else f"doc_{i}"
                
                if auto_split and len(doc) > 1000:
                    # 分割长文档
                    chunks = self.split_text(doc, separator=split_separator)
                    for j, chunk in enumerate(chunks):
                        final_documents.append(chunk)
                        chunk_metadata = doc_metadata.copy()
                        chunk_metadata.update({
                            "chunk_index": j,
                            "total_chunks": len(chunks),
                            "original_doc_id": doc_id_prefix
                        })
                        final_metadatas.append(chunk_metadata)
                        final_ids.append(f"{doc_id_prefix}_chunk_{j}")
                else:
                    final_documents.append(doc)
                    final_metadatas.append(doc_metadata)
                    final_ids.append(doc_id_prefix)
            
            # 添加到ChromaDB
            collection.add(
                documents=final_documents,
                metadatas=final_metadatas,
                ids=final_ids
            )
            
            # 更新文档计数
            if collection_name in self.collections_config:
                self.collections_config[collection_name].document_count += len(final_documents)
                self._save_config()
            
            logger.info(f"成功向集合 '{collection_name}' 添加 {len(final_documents)} 个文档")
            return True
            
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            return False
    
    async def query_documents(self, 
                            collection_name: str, 
                            query_text: str, 
                            n_results: int = 5,
                            filter_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        查询文档
        
        Args:
            collection_name: 集合名称
            query_text: 查询文本
            n_results: 返回结果数量
            filter_metadata: 元数据过滤条件
            
        Returns:
            查询结果列表
        """
        if not self.chroma_client:
            logger.error("ChromaDB客户端未初始化")
            return []
        
        try:
            collection = await self._get_collection(collection_name)
            if not collection:
                return []
            
            # 执行查询
            query_kwargs = {
                "query_texts": [query_text],
                "n_results": n_results
            }
            
            if filter_metadata:
                query_kwargs["where"] = filter_metadata
            
            results = collection.query(**query_kwargs)
            
            # 格式化结果
            formatted_results = []
            if results and results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    result_item = {
                        'id': results['ids'][0][i],
                        'document': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i] if results['metadatas'] and results['metadatas'][0] else {},
                        'distance': results['distances'][0][i] if results['distances'] and results['distances'][0] else 0
                    }
                    formatted_results.append(result_item)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"查询文档失败: {e}")
            return []
    
    async def _get_collection(self, name: str):
        """获取集合对象"""
        if name in self.collections_cache:
            return self.collections_cache[name]
        
        try:
            collection = self.chroma_client.get_collection(name)
            self.collections_cache[name] = collection
            return collection
        except Exception as e:
            logger.error(f"获取集合 '{name}' 失败: {e}")
            return None
    
    def list_collections(self) -> List[KnowledgeCollection]:
        """列出所有知识集合"""
        return list(self.collections_config.values())
    
    def get_collection_info(self, name: str) -> Optional[KnowledgeCollection]:
        """获取集合信息"""
        return self.collections_config.get(name)
    
    async def delete_collection(self, name: str) -> bool:
        """删除知识集合"""
        if not self.chroma_client:
            logger.error("ChromaDB客户端未初始化")
            return False
        
        try:
            # 从ChromaDB删除
            self.chroma_client.delete_collection(name)
            
            # 从缓存和配置中移除
            if name in self.collections_cache:
                del self.collections_cache[name]
            
            if name in self.collections_config:
                del self.collections_config[name]
                self._save_config()
            
            logger.info(f"成功删除知识集合: {name}")
            return True
            
        except Exception as e:
            logger.error(f"删除知识集合失败: {e}")
            return False
    
    async def import_from_text_file(self, 
                                   collection_name: str, 
                                   file_path: str, 
                                   separator: str = "\n",
                                   encoding: str = "utf-8") -> bool:
        """
        从文本文件导入知识
        
        Args:
            collection_name: 集合名称
            file_path: 文件路径
            separator: 文本分割符
            encoding: 文件编码
            
        Returns:
            是否导入成功
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"文件不存在: {file_path}")
                return False
            
            # 读取文件内容
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            if not content.strip():
                logger.warning("文件内容为空")
                return False
            
            # 添加文档
            metadata = {
                "source_file": str(file_path),
                "import_time": datetime.now().isoformat()
            }
            
            return await self.add_documents(
                collection_name=collection_name,
                documents=[content],
                metadatas=[metadata],
                ids=[f"file_{file_path.stem}"],
                auto_split=True,
                split_separator=separator
            )
            
        except Exception as e:
            logger.error(f"从文件导入知识失败: {e}")
            return False 
    
    async def get_all_documents(self, collection_name: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """获取集合中的所有文档（支持分页）"""
        try:
            if not hasattr(self, 'chroma_client') or not self.chroma_client:
                raise ValueError("ChromaDB客户端未初始化")
            
            collection = self.chroma_client.get_collection(collection_name)
            
            # 获取所有文档
            results = collection.get(
                limit=limit,
                offset=offset,
                include=['documents', 'metadatas']
            )
            
            documents = []
            for i in range(len(results['ids'])):
                doc = {
                    'id': results['ids'][i],
                    'document': results['documents'][i],
                    'metadata': results['metadatas'][i] if results['metadatas'] else {}
                }
                documents.append(doc)
            
            return documents
            
        except Exception as e:
            logger.error(f"获取文档列表失败: {collection_name} | 错误: {e}")
            return []
    
    async def get_document_by_id(self, collection_name: str, document_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取特定文档"""
        try:
            if not hasattr(self, 'chroma_client') or not self.chroma_client:
                raise ValueError("ChromaDB客户端未初始化")
            
            collection = self.chroma_client.get_collection(collection_name)
            
            # 根据ID获取文档
            results = collection.get(
                ids=[document_id],
                include=['documents', 'metadatas']
            )
            
            if results['ids']:
                return {
                    'id': results['ids'][0],
                    'document': results['documents'][0],
                    'metadata': results['metadatas'][0] if results['metadatas'] else {}
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"获取文档失败: {collection_name}:{document_id} | 错误: {e}")
            return None