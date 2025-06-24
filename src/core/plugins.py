"""
角色插件系统 - 提供角色资料和角色知识库的全局配置管理
"""
import os
import json
import asyncio
import logging
import uuid
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union, Callable
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

# ChromaDB相关导入
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# Sentence Transformers用于生成512维embedding
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ProcessingProgress:
    """处理进度数据类"""
    total_chunks: int = 0
    processed_chunks: int = 0
    current_step: str = ""
    is_complete: bool = False
    error_message: str = ""
    
    @property
    def progress_percentage(self) -> float:
        """获取进度百分比"""
        if self.total_chunks == 0:
            return 0.0
        return (self.processed_chunks / self.total_chunks) * 100


@dataclass
class RoleProfile:
    """角色资料数据类"""
    name: str  # 角色名称
    content: str  # 角色资料内容
    created_at: str  # 创建时间
    updated_at: str  # 更新时间
    tags: List[str] = None  # 标签
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass 
class RoleKnowledgeBase:
    """角色知识库数据类"""
    name: str  # 知识库名称
    source_file: str  # 源文件路径（txt或csv）
    description: str  # 描述
    created_at: str  # 创建时间
    enabled: bool = True  # 是否启用
    search_limit: int = 3  # 搜索结果数量限制
    processed_data: List[str] = field(default_factory=list)  # 处理后的文本数据
    collection_name: str = ""  # ChromaDB集合名称
    embedding_model: str = "BAAI/bge-small-zh-v1.5"  # embedding模型名称（BGE中文模型，512维）
    chunk_size: int = 512  # 文本块大小
    chunk_overlap: int = 50  # 文本块重叠大小
    
    def __post_init__(self):
        if not self.processed_data:
            self.processed_data = []
        if not self.collection_name:
            # 生成符合ChromaDB规范的集合名称（只使用英文字母、数字、下划线）
            import re
            # 移除非ASCII字符，只保留字母、数字、下划线
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', self.name)
            # 确保以字母或数字开头和结尾
            safe_name = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', safe_name)
            if not safe_name:
                safe_name = "knowledge_base"
            self.collection_name = f"kb_{safe_name}_{uuid.uuid4().hex[:8]}"


class BaseRolePlugin(ABC):
    """角色插件基类"""
    
    def __init__(self, plugin_id: str, name: str, description: str = ""):
        self.plugin_id = plugin_id
        self.name = name
        self.description = description
        self.enabled = False
    
    @abstractmethod
    async def get_data(self, **kwargs) -> Any:
        """获取插件数据"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """检查插件是否可用"""
        pass
    
    def enable(self):
        """启用插件"""
        self.enabled = True
        
    def disable(self):
        """禁用插件"""
        self.enabled = False


class RoleProfilePlugin(BaseRolePlugin):
    """角色资料插件"""
    
    def __init__(self):
        super().__init__(
            plugin_id="role_profile",
            name="角色资料",
            description="提供角色的详细资料信息"
        )
        self.profile: Optional[RoleProfile] = None
    
    def set_profile(self, name: str, content: str, tags: List[str] = None):
        """设置角色资料"""
        now = datetime.now().isoformat()
        if self.profile and self.profile.name == name:
            # 更新现有资料
            self.profile.content = content
            self.profile.updated_at = now
            if tags:
                self.profile.tags = tags
        else:
            # 创建新资料
            self.profile = RoleProfile(
                name=name,
                content=content,
                created_at=now,
                updated_at=now,
                tags=tags or []
            )
        logger.info(f"角色资料已设置: {name}")
    
    async def get_data(self, **kwargs) -> Optional[str]:
        """获取角色资料内容"""
        if not self.enabled or not self.profile:
            return None
        return self.profile.content
    
    async def is_available(self) -> bool:
        """检查是否有可用的角色资料"""
        return self.enabled and self.profile is not None and bool(self.profile.content.strip())
    
    def get_profile_info(self) -> Optional[Dict[str, Any]]:
        """获取角色资料信息"""
        if not self.profile:
            return None
        return {
            "name": self.profile.name,
            "content_length": len(self.profile.content),
            "tags": self.profile.tags,
            "created_at": self.profile.created_at,
            "updated_at": self.profile.updated_at
        }
    
    def clear_profile(self):
        """清空角色资料"""
        self.profile = None
        logger.info("角色资料已清空")


class RoleKnowledgeBasePlugin(BaseRolePlugin):
    """角色知识库插件 - 基于ChromaDB向量数据库"""
    
    def __init__(self, workspace_dir: str = "./workspace"):
        super().__init__(
            plugin_id="role_knowledge_base",
            name="角色知识库",
            description="提供基于ChromaDB向量搜索的角色知识库"
        )
        self.knowledge_base: Optional[RoleKnowledgeBase] = None
        self.workspace_dir = Path(workspace_dir)
        self.vectordb_dir = self.workspace_dir / "vectordb"
        self.vectordb_dir.mkdir(exist_ok=True)
        
        # ChromaDB客户端和集合
        self._chroma_client = None
        self._collection = None
        
        # embedding模型
        self._embedding_model = None
        
        # 处理进度回调
        self.progress_callback: Optional[Callable[[ProcessingProgress], None]] = None
        self.current_progress = ProcessingProgress()
    
    def set_progress_callback(self, callback: Callable[[ProcessingProgress], None]):
        """设置进度回调函数"""
        self.progress_callback = callback
    
    def _update_progress(self, step: str = "", processed: int = 0, total: int = 0, error: str = ""):
        """更新处理进度"""
        if total > 0:
            self.current_progress.total_chunks = total
        if processed >= 0:
            self.current_progress.processed_chunks = processed
        if step:
            self.current_progress.current_step = step
        if error:
            self.current_progress.error_message = error
        
        self.current_progress.is_complete = (
            self.current_progress.processed_chunks >= self.current_progress.total_chunks 
            and self.current_progress.total_chunks > 0
        )
        
        if self.progress_callback:
            self.progress_callback(self.current_progress)
    
    async def _init_chroma_client(self):
        """初始化ChromaDB客户端"""
        if self._chroma_client is not None:
            return
        
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB未安装，请运行: pip install chromadb")
        
        try:
            self._chroma_client = chromadb.PersistentClient(
                path=str(self.vectordb_dir),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info(f"ChromaDB客户端初始化完成: {self.vectordb_dir}")
        except Exception as e:
            logger.error(f"初始化ChromaDB客户端失败: {e}")
            raise
    
    async def _init_embedding_model(self):
        """初始化embedding模型"""
        if self._embedding_model is not None:
            return
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("Sentence Transformers未安装，使用ChromaDB默认embedding")
            return
        
        try:
            model_name = self.knowledge_base.embedding_model if self.knowledge_base else "all-MiniLM-L6-v2"
            self._embedding_model = SentenceTransformer(model_name)
            logger.info(f"Embedding模型加载完成: {model_name}")
        except Exception as e:
            logger.error(f"加载embedding模型失败: {e}")
            self._embedding_model = None
    
    def _create_custom_embedding_function(self):
        """创建自定义512维embedding函数"""
        if not self._embedding_model:
            # 使用ChromaDB默认embedding函数
            return embedding_functions.DefaultEmbeddingFunction()
        
        class Custom512EmbeddingFunction:
            def __init__(self, model):
                self.model = model
            
            def __call__(self, input: List[str]) -> List[List[float]]:
                """
                生成512维embedding向量
                
                Args:
                    input: 输入文本列表（新版ChromaDB使用input参数而不是texts）
                    
                Returns:
                    List[List[float]]: 512维embedding向量列表
                """
                # 兼容处理：支持旧版本的texts参数名
                texts = input
                
                try:
                    # 生成embedding
                    embeddings = self.model.encode(texts, convert_to_numpy=True)
                    
                    # 确保是512维度
                    if embeddings.shape[1] != 512:
                        # 如果不是512维，进行维度调整
                        if embeddings.shape[1] > 512:
                            # 降维：取前512维
                            embeddings = embeddings[:, :512]
                        else:
                            # 升维：用零填充
                            padding = np.zeros((embeddings.shape[0], 512 - embeddings.shape[1]))
                            embeddings = np.concatenate([embeddings, padding], axis=1)
                    
                    # 归一化
                    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                    embeddings = embeddings / (norms + 1e-8)
                    
                    return embeddings.tolist()
                
                except Exception as e:
                    logger.error(f"生成embedding失败: {e}")
                    # 返回随机512维向量作为fallback
                    return [np.random.normal(0, 0.1, 512).tolist() for _ in texts]
        
        return Custom512EmbeddingFunction(self._embedding_model)
    
    def _split_text_into_chunks(self, text: str) -> List[str]:
        """将文本分割成块"""
        if not text.strip():
            return []
        
        chunk_size = self.knowledge_base.chunk_size if self.knowledge_base else 512
        chunk_overlap = self.knowledge_base.chunk_overlap if self.knowledge_base else 50
        
        # 简单的文本分割策略
        words = text.split()
        chunks = []
        
        i = 0
        while i < len(words):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            
            if chunk_text.strip():
                chunks.append(chunk_text.strip())
            
            # 移动到下一个块，考虑重叠
            i += max(1, chunk_size - chunk_overlap)
        
        return chunks
    
    async def set_knowledge_base(self, name: str, source_file: str, description: str = "", 
                               search_limit: int = 3, process_immediately: bool = True):
        """设置角色知识库"""
        now = datetime.now().isoformat()
        self.knowledge_base = RoleKnowledgeBase(
            name=name,
            source_file=source_file,
            description=description,
            created_at=now,
            search_limit=search_limit
        )
        
        if process_immediately:
            await self.process_knowledge_base()
        
        logger.info(f"角色知识库已设置: {name} -> {source_file}")
    
    async def process_knowledge_base(self):
        """处理知识库文件并创建向量数据库"""
        if not self.knowledge_base:
            raise ValueError("知识库未设置")
        
        try:
            self._update_progress("初始化向量数据库...")
            
            # 初始化ChromaDB客户端和embedding模型
            await self._init_chroma_client()
            await self._init_embedding_model()
            
            # 处理源文件
            self._update_progress("读取源文件...")
            await self._process_source_file()
            
            if not self.knowledge_base.processed_data:
                raise ValueError("没有可处理的数据")
            
            # 创建或获取集合
            self._update_progress("创建向量集合...")
            await self._create_or_get_collection()
            
            # 分割文本并生成embedding
            self._update_progress("分割文本块...")
            all_chunks = []
            chunk_metadata = []
            
            for i, text in enumerate(self.knowledge_base.processed_data):
                chunks = self._split_text_into_chunks(text)
                for j, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    chunk_metadata.append({
                        "source_index": i,
                        "chunk_index": j,
                        "source_text": text[:100] + "..." if len(text) > 100 else text
                    })
            
            if not all_chunks:
                raise ValueError("文本分割后没有有效块")
            
            # 批量处理embedding和存储
            batch_size = 50  # 批处理大小
            total_batches = (len(all_chunks) + batch_size - 1) // batch_size
            
            self._update_progress("生成embedding向量...", 0, len(all_chunks))
            
            for batch_idx in range(total_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(all_chunks))
                
                batch_chunks = all_chunks[start_idx:end_idx]
                batch_metadata = chunk_metadata[start_idx:end_idx]
                batch_ids = [f"chunk_{start_idx + i}" for i in range(len(batch_chunks))]
                
                # 添加到集合
                self._collection.add(
                    documents=batch_chunks,
                    metadatas=batch_metadata,
                    ids=batch_ids
                )
                
                self._update_progress(
                    f"处理批次 {batch_idx + 1}/{total_batches}",
                    end_idx,
                    len(all_chunks)
                )
            
            self._update_progress("向量数据库创建完成", len(all_chunks), len(all_chunks))
            logger.info(f"知识库向量化完成: {len(all_chunks)} 个文本块")
            
        except Exception as e:
            error_msg = f"处理知识库失败: {str(e)}"
            self._update_progress(error=error_msg)
            logger.error(error_msg)
            raise
    
    async def _process_source_file(self):
        """处理源文件（txt或csv）为知识库数据"""
        if not self.knowledge_base or not self.knowledge_base.source_file:
            return
        
        source_path = Path(self.knowledge_base.source_file)
        if not source_path.exists():
            raise FileNotFoundError(f"知识库源文件不存在: {source_path}")
        
        try:
            self.knowledge_base.processed_data = []
            
            if source_path.suffix.lower() == '.txt':
                # 处理txt文件
                encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030']
                content = None
                
                for encoding in encodings:
                    try:
                        with open(source_path, 'r', encoding=encoding) as f:
                            content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue
                
                if content is None:
                    raise ValueError("无法读取文件，请检查文件编码")
                
                # 按段落分割，保留更多上下文
                paragraphs = []
                current_paragraph = []
                
                for line in content.split('\n'):
                    line = line.strip()
                    if line:
                        current_paragraph.append(line)
                    else:
                        if current_paragraph:
                            paragraphs.append(' '.join(current_paragraph))
                            current_paragraph = []
                
                if current_paragraph:
                    paragraphs.append(' '.join(current_paragraph))
                
                self.knowledge_base.processed_data = [p for p in paragraphs if p.strip()]
                
            elif source_path.suffix.lower() == '.csv':
                # 处理csv文件
                import csv
                encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030']
                
                for encoding in encodings:
                    try:
                        with open(source_path, 'r', encoding=encoding) as f:
                            reader = csv.reader(f)
                            headers = next(reader, None)
                            
                            for row in reader:
                                if row:  # 跳过空行
                                    # 将每行组合成一个文本片段
                                    if headers:
                                        text_parts = []
                                        for i, value in enumerate(row):
                                            if i < len(headers) and value.strip():
                                                text_parts.append(f"{headers[i]}: {value.strip()}")
                                        text = "; ".join(text_parts)
                                    else:
                                        text = "; ".join([v.strip() for v in row if v.strip()])
                                    
                                    if text:
                                        self.knowledge_base.processed_data.append(text)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise ValueError("无法读取CSV文件，请检查文件编码")
            
            else:
                raise ValueError(f"不支持的文件格式: {source_path.suffix}")
            
            logger.info(f"知识库数据处理完成: {len(self.knowledge_base.processed_data)} 条")
            
        except Exception as e:
            logger.error(f"处理知识库源文件失败: {e}")
            self.knowledge_base.processed_data = []
            raise
    
    async def _create_or_get_collection(self):
        """创建或获取ChromaDB集合"""
        if not self._chroma_client or not self.knowledge_base:
            raise ValueError("ChromaDB客户端或知识库未初始化")
        
        try:
            # 创建自定义embedding函数
            embedding_fn = self._create_custom_embedding_function()
            
            # 尝试获取现有集合
            try:
                self._collection = self._chroma_client.get_collection(
                    name=self.knowledge_base.collection_name
                )
                logger.info(f"使用现有集合: {self.knowledge_base.collection_name}")
            except Exception:
                # 创建新集合
                self._collection = self._chroma_client.create_collection(
                    name=self.knowledge_base.collection_name,
                    embedding_function=embedding_fn,
                    metadata={
                        "name": self.knowledge_base.name,
                        "description": self.knowledge_base.description,
                        "created_at": self.knowledge_base.created_at,
                        "embedding_model": self.knowledge_base.embedding_model,
                        "dimensions": 512
                    }
                )
                logger.info(f"创建新集合: {self.knowledge_base.collection_name}")
        
        except Exception as e:
            logger.error(f"创建或获取集合失败: {e}")
            raise
    
    async def search_knowledge(self, keywords: List[str], limit: int = None) -> List[Dict[str, Any]]:
        """基于向量相似度搜索知识库"""
        if not self.enabled or not self.knowledge_base or not self._collection:
            return []
        
        search_limit = limit or self.knowledge_base.search_limit
        
        try:
            # 将关键词组合成查询文本
            query_text = " ".join(keywords)
            
            # 执行向量搜索
            results = self._collection.query(
                query_texts=[query_text],
                n_results=search_limit,
                include=["documents", "metadatas", "distances"]
            )
            
            # 格式化搜索结果
            formatted_results = []
            
            if results['documents'] and results['documents'][0]:
                documents = results['documents'][0]
                metadatas = results['metadatas'][0] if results['metadatas'] else [{}] * len(documents)
                distances = results['distances'][0] if results['distances'] else [0.0] * len(documents)
                
                for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
                    # 计算相似度分数 (1 - distance)
                    similarity_score = max(0.0, 1.0 - distance)
                    
                    formatted_results.append({
                        "content": doc,
                        "score": similarity_score,
                        "distance": distance,
                        "source": f"chunk_{metadata.get('source_index', i)}",
                        "metadata": metadata,
                        "keywords": keywords
                    })
            
            logger.info(f"向量搜索完成: '{query_text}' -> {len(formatted_results)} 个结果")
            return formatted_results
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    async def get_data(self, keywords: List[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """获取知识库数据"""
        if not keywords:
            return []
        return await self.search_knowledge(keywords)
    
    async def is_available(self) -> bool:
        """检查知识库是否可用"""
        if not self.enabled or not self.knowledge_base:
            return False
        
        try:
            await self._init_chroma_client()
            if self._chroma_client and self.knowledge_base.collection_name:
                # 检查集合是否存在
                collections = self._chroma_client.list_collections()
                collection_names = [c.name for c in collections]
                return self.knowledge_base.collection_name in collection_names
        except Exception as e:
            logger.error(f"检查知识库可用性失败: {e}")
        
        return False
    
    def get_knowledge_base_info(self) -> Optional[Dict[str, Any]]:
        """获取知识库信息"""
        if not self.knowledge_base:
            return None
        
        info = {
            "name": self.knowledge_base.name,
            "source_file": self.knowledge_base.source_file,
            "description": self.knowledge_base.description,
            "enabled": self.knowledge_base.enabled,
            "search_limit": self.knowledge_base.search_limit,
            "created_at": self.knowledge_base.created_at,
            "data_count": len(self.knowledge_base.processed_data) if self.knowledge_base.processed_data else 0,
            "collection_name": self.knowledge_base.collection_name,
            "embedding_model": self.knowledge_base.embedding_model,
            "chunk_size": self.knowledge_base.chunk_size,
            "progress": {
                "total_chunks": self.current_progress.total_chunks,
                "processed_chunks": self.current_progress.processed_chunks,
                "current_step": self.current_progress.current_step,
                "progress_percentage": self.current_progress.progress_percentage,
                "is_complete": self.current_progress.is_complete,
                "error_message": self.current_progress.error_message
            }
        }
        
        # 如果集合存在，获取集合统计信息
        try:
            if self._collection:
                collection_count = self._collection.count()
                info["vector_count"] = collection_count
        except Exception as e:
            logger.warning(f"获取集合统计信息失败: {e}")
            info["vector_count"] = 0
        
        return info
    
    async def get_collection_contents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取集合中的所有内容"""
        if not self._collection:
            return []
        
        try:
            # 获取集合中的所有文档
            results = self._collection.get(
                limit=limit,
                include=["documents", "metadatas"]
            )
            
            contents = []
            if results['documents']:
                documents = results['documents']
                metadatas = results['metadatas'] if results['metadatas'] else [{}] * len(documents)
                ids = results['ids'] if results['ids'] else [f"doc_{i}" for i in range(len(documents))]
                
                for doc_id, doc, metadata in zip(ids, documents, metadatas):
                    contents.append({
                        "id": doc_id,
                        "content": doc,
                        "metadata": metadata,
                        "preview": doc[:200] + "..." if len(doc) > 200 else doc
                    })
            
            return contents
            
        except Exception as e:
            logger.error(f"获取集合内容失败: {e}")
            return []
    
    def clear_knowledge_base(self):
        """清空知识库配置"""
        try:
            # 删除ChromaDB集合
            if self._chroma_client and self.knowledge_base and self.knowledge_base.collection_name:
                try:
                    self._chroma_client.delete_collection(self.knowledge_base.collection_name)
                    logger.info(f"已删除集合: {self.knowledge_base.collection_name}")
                except Exception as e:
                    logger.warning(f"删除集合失败: {e}")
        except Exception as e:
            logger.error(f"清理知识库失败: {e}")
        
        # 清空配置
        self.knowledge_base = None
        self._collection = None
        self.current_progress = ProcessingProgress()
        logger.info("角色知识库配置已清空")


class RolePluginManager:
    """角色插件管理器"""
    
    def __init__(self, workspace_dir: str = "./workspace"):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(exist_ok=True)
        
        # 初始化插件
        self.profile_plugin = RoleProfilePlugin()
        self.knowledge_base_plugin = RoleKnowledgeBasePlugin(workspace_dir)
        
        # 插件注册表
        self.plugins: Dict[str, BaseRolePlugin] = {
            "role_profile": self.profile_plugin,
            "role_knowledge_base": self.knowledge_base_plugin
        }
        
        # 配置文件路径
        self.config_file = self.workspace_dir / "role_plugins_config.json"
        
        # 加载配置
        self._load_config()
        
        logger.info("角色插件管理器初始化完成")
    
    def _load_config(self):
        """加载插件配置"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 加载角色资料配置
                profile_config = config.get("role_profile", {})
                if profile_config.get("enabled", False) and "content" in profile_config:
                    self.profile_plugin.set_profile(
                        name=profile_config.get("name", "默认角色"),
                        content=profile_config["content"],
                        tags=profile_config.get("tags", [])
                    )
                    if profile_config.get("enabled", False):
                        self.profile_plugin.enable()
                
                # 加载知识库配置
                kb_config = config.get("role_knowledge_base", {})
                if kb_config.get("enabled", False) and "source_file" in kb_config:
                    # 兼容旧配置中的path字段
                    source_file = kb_config.get("source_file") or kb_config.get("path")
                    if source_file:
                        # 创建知识库配置但不立即处理
                        now = datetime.now().isoformat()
                        self.knowledge_base_plugin.knowledge_base = RoleKnowledgeBase(
                            name=kb_config.get("name", "默认知识库"),
                            source_file=source_file,
                            description=kb_config.get("description", ""),
                            created_at=kb_config.get("created_at", now),
                            search_limit=kb_config.get("search_limit", 3),
                            collection_name=kb_config.get("collection_name", ""),
                            embedding_model=kb_config.get("embedding_model", "BAAI/bge-small-zh-v1.5"),
                            chunk_size=kb_config.get("chunk_size", 512),
                            chunk_overlap=kb_config.get("chunk_overlap", 50)
                        )
                        
                        # 如果有保存的处理数据，直接加载
                        if "processed_data" in kb_config:
                            self.knowledge_base_plugin.knowledge_base.processed_data = kb_config["processed_data"]
                        
                        if kb_config.get("enabled", False):
                            self.knowledge_base_plugin.enable()
                
                logger.info("角色插件配置加载完成")
        except Exception as e:
            logger.error(f"加载角色插件配置失败: {e}")
    
    def _save_config(self):
        """保存插件配置"""
        try:
            config = {}
            
            # 保存角色资料配置
            if self.profile_plugin.profile:
                config["role_profile"] = {
                    "enabled": self.profile_plugin.enabled,
                    "name": self.profile_plugin.profile.name,
                    "content": self.profile_plugin.profile.content,
                    "tags": self.profile_plugin.profile.tags,
                    "created_at": self.profile_plugin.profile.created_at,
                    "updated_at": self.profile_plugin.profile.updated_at
                }
            else:
                config["role_profile"] = {"enabled": False}
            
            # 保存知识库配置
            if self.knowledge_base_plugin.knowledge_base:
                config["role_knowledge_base"] = {
                    "enabled": self.knowledge_base_plugin.enabled,
                    "name": self.knowledge_base_plugin.knowledge_base.name,
                    "source_file": self.knowledge_base_plugin.knowledge_base.source_file,
                    "description": self.knowledge_base_plugin.knowledge_base.description,
                    "search_limit": self.knowledge_base_plugin.knowledge_base.search_limit,
                    "created_at": self.knowledge_base_plugin.knowledge_base.created_at,
                    "collection_name": self.knowledge_base_plugin.knowledge_base.collection_name,
                    "embedding_model": self.knowledge_base_plugin.knowledge_base.embedding_model,
                    "chunk_size": self.knowledge_base_plugin.knowledge_base.chunk_size,
                    "chunk_overlap": self.knowledge_base_plugin.knowledge_base.chunk_overlap,
                    "processed_data": self.knowledge_base_plugin.knowledge_base.processed_data
                }
            else:
                config["role_knowledge_base"] = {"enabled": False}
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                
            logger.info("角色插件配置已保存")
        except Exception as e:
            logger.error(f"保存角色插件配置失败: {e}")
    
    def configure_profile(self, name: str, content: str, tags: List[str] = None, enabled: bool = True):
        """配置角色资料"""
        self.profile_plugin.set_profile(name, content, tags)
        if enabled:
            self.profile_plugin.enable()
        else:
            self.profile_plugin.disable()
        self._save_config()
    
    async def configure_knowledge_base(self, name: str, source_file: str, description: str = "", 
                                     search_limit: int = 3, enabled: bool = True, 
                                     process_immediately: bool = True):
        """配置角色知识库"""
        await self.knowledge_base_plugin.set_knowledge_base(
            name=name, 
            source_file=source_file, 
            description=description, 
            search_limit=search_limit,
            process_immediately=process_immediately
        )
        if enabled:
            self.knowledge_base_plugin.enable()
        else:
            self.knowledge_base_plugin.disable()
        self._save_config()
    
    def get_plugin(self, plugin_id: str) -> Optional[BaseRolePlugin]:
        """获取插件"""
        return self.plugins.get(plugin_id)
    
    def enable_plugin(self, plugin_id: str):
        """启用插件"""
        if plugin_id in self.plugins:
            self.plugins[plugin_id].enable()
            self._save_config()
            logger.info(f"插件已启用: {plugin_id}")
    
    def disable_plugin(self, plugin_id: str):
        """禁用插件"""
        if plugin_id in self.plugins:
            self.plugins[plugin_id].disable()
            self._save_config()
            logger.info(f"插件已禁用: {plugin_id}")
    
    async def get_role_context(self, keywords: List[str] = None) -> Dict[str, Any]:
        """获取角色上下文信息（综合资料和知识库）"""
        context = {}
        
        # 获取角色资料
        if await self.profile_plugin.is_available():
            profile_content = await self.profile_plugin.get_data()
            if profile_content:
                context["profile"] = profile_content
        
        # 获取知识库搜索结果
        if keywords and await self.knowledge_base_plugin.is_available():
            knowledge_results = await self.knowledge_base_plugin.get_data(keywords=keywords)
            if knowledge_results:
                context["knowledge"] = knowledge_results
        
        return context
    
    def get_status(self) -> Dict[str, Any]:
        """获取插件管理器状态"""
        # 同步版本的可用性检查
        profile_available = (self.profile_plugin.enabled and 
                           self.profile_plugin.profile is not None and 
                           bool(self.profile_plugin.profile.content.strip()))
        
        kb_available = (self.knowledge_base_plugin.enabled and 
                       self.knowledge_base_plugin.knowledge_base is not None)
        
        return {
            "profile_plugin": {
                "enabled": self.profile_plugin.enabled,
                "available": profile_available,
                "info": self.profile_plugin.get_profile_info()
            },
            "knowledge_base_plugin": {
                "enabled": self.knowledge_base_plugin.enabled,
                "available": kb_available,
                "info": self.knowledge_base_plugin.get_knowledge_base_info()
            }
        }
    
    def clear_all(self):
        """清空所有插件配置"""
        self.profile_plugin.clear_profile()
        self.profile_plugin.disable()
        self.knowledge_base_plugin.clear_knowledge_base()
        self.knowledge_base_plugin.disable()
        self._save_config()
        logger.info("所有角色插件配置已清空")


# 全局插件管理器实例
_role_plugin_manager: Optional[RolePluginManager] = None


def get_role_plugin_manager(workspace_dir: str = "./workspace") -> RolePluginManager:
    """获取全局角色插件管理器实例"""
    global _role_plugin_manager
    if _role_plugin_manager is None:
        _role_plugin_manager = RolePluginManager(workspace_dir)
    return _role_plugin_manager 