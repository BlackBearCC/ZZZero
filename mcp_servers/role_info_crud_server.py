#!/usr/bin/env python3
"""
角色信息CRUD服务器 - 支持角色人设、知识库和世界书的增删查改
"""
import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 使用本地mcp模块
from mcp.server.stdio_server import StdioMCPServer
from mcp.types import Tool, ToolInputSchema

logger = logging.getLogger(__name__)

class RoleProfile:
    """角色人设"""
    def __init__(self, id: str, name: str, content: str, tags: List[str] = None, 
                 created_at: str = None, updated_at: str = None):
        self.id = id
        self.name = name
        self.content = content
        self.tags = tags or []
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "content": self.content,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RoleProfile':
        return cls(**data)

class KnowledgeEntry:
    """知识条目"""
    def __init__(self, id: str, keyword: str, content: str, description: str = "",
                 created_at: str = None, updated_at: str = None):
        self.id = id
        self.keyword = keyword
        self.content = content
        self.description = description
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "content": self.content,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeEntry':
        return cls(**data)

class WorldBookEntry:
    """世界书条目"""
    def __init__(self, id: str, concept: str, content: str, category: str = "",
                 keywords: List[str] = None, created_at: str = None, updated_at: str = None):
        self.id = id
        self.concept = concept
        self.content = content
        self.category = category
        self.keywords = keywords or []
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "concept": self.concept,
            "content": self.content,
            "category": self.category,
            "keywords": self.keywords,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorldBookEntry':
        return cls(**data)

class RoleInfoCRUDServer(StdioMCPServer):
    """角色信息CRUD MCP服务器"""
    
    def __init__(self, workspace_dir: str = "./workspace"):
        super().__init__("role-info-crud-server")
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(exist_ok=True)
        
        # 数据存储文件
        self.profiles_file = self.workspace_dir / "role_profiles.json"
        self.knowledge_file = self.workspace_dir / "role_knowledge.json"
        self.worldbook_file = self.workspace_dir / "world_book.json"
        
        # 内存数据
        self.profiles: Dict[str, RoleProfile] = {}
        self.knowledge_entries: Dict[str, KnowledgeEntry] = {}
        self.worldbook_entries: Dict[str, WorldBookEntry] = {}
        
        # ChromaDB向量数据库（可选）
        self.chroma_client = None
        self.knowledge_collection = None
        self.worldbook_collection = None
        
        self._load_data()
        self._init_vector_db()
        self._register_tools()
    
    def _load_data(self):
        """加载数据"""
        try:
            # 加载角色人设
            if self.profiles_file.exists():
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.profiles = {k: RoleProfile.from_dict(v) for k, v in data.items()}
                logger.info(f"已加载 {len(self.profiles)} 个角色人设")
            
            # 加载知识库
            if self.knowledge_file.exists():
                with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.knowledge_entries = {k: KnowledgeEntry.from_dict(v) for k, v in data.items()}
                logger.info(f"已加载 {len(self.knowledge_entries)} 个知识条目")
            
            # 加载世界书
            if self.worldbook_file.exists():
                with open(self.worldbook_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.worldbook_entries = {k: WorldBookEntry.from_dict(v) for k, v in data.items()}
                logger.info(f"已加载 {len(self.worldbook_entries)} 个世界书条目")
                
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
    
    def _save_data(self):
        """保存数据"""
        try:
            # 保存角色人设
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in self.profiles.items()}, 
                         f, ensure_ascii=False, indent=2)
            
            # 保存知识库
            with open(self.knowledge_file, 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in self.knowledge_entries.items()}, 
                         f, ensure_ascii=False, indent=2)
            
            # 保存世界书
            with open(self.worldbook_file, 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in self.worldbook_entries.items()}, 
                         f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
    
    def _init_vector_db(self):
        """初始化向量数据库"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            # 创建ChromaDB客户端
            db_path = self.workspace_dir / "vectordb"
            db_path.mkdir(exist_ok=True)
            
            self.chroma_client = chromadb.PersistentClient(
                path=str(db_path),
                settings=Settings(anonymized_telemetry=False)
            )
            
            # 获取或创建集合
            self.knowledge_collection = self.chroma_client.get_or_create_collection("role_knowledge")
            self.worldbook_collection = self.chroma_client.get_or_create_collection("world_book")
            
            logger.info("✅ 向量数据库初始化成功")
            
        except ImportError:
            logger.warning("ChromaDB未安装，将仅使用文本搜索")
        except Exception as e:
            logger.error(f"向量数据库初始化失败: {e}")
    
    def _register_tools(self):
        """注册所有工具"""
        
        # === 角色人设工具 ===
        self.register_tool(Tool(
            name="create_profile",
            description="创建新的角色人设",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "name": {"type": "string", "description": "角色名称"},
                    "content": {"type": "string", "description": "角色详细设定内容"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表"}
                },
                required=["name", "content"]
            )
        ))
        
        self.register_tool(Tool(
            name="update_profile",
            description="更新角色人设",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "profile_id": {"type": "string", "description": "角色ID"},
                    "name": {"type": "string", "description": "新的角色名称"},
                    "content": {"type": "string", "description": "新的角色设定内容"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "新的标签列表"}
                },
                required=["profile_id"]
            )
        ))
        
        self.register_tool(Tool(
            name="query_profile",
            description="查询角色人设",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "profile_id": {"type": "string", "description": "角色ID，不填则返回所有角色"},
                    "name": {"type": "string", "description": "按名称查询"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "按标签查询"}
                }
            )
        ))
        
        self.register_tool(Tool(
            name="delete_profile",
            description="删除角色人设",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "profile_id": {"type": "string", "description": "角色ID"}
                },
                required=["profile_id"]
            )
        ))
        
        self.register_tool(Tool(
            name="list_profiles",
            description="列出所有角色人设",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "limit": {"type": "integer", "description": "返回数量限制", "default": 10}
                }
            )
        ))
        
        # === 知识库工具 ===
        self.register_tool(Tool(
            name="add_knowledge",
            description="添加知识条目",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "keyword": {"type": "string", "description": "关键词"},
                    "content": {"type": "string", "description": "知识内容"},
                    "description": {"type": "string", "description": "描述说明"}
                },
                required=["keyword", "content"]
            )
        ))
        
        self.register_tool(Tool(
            name="search_knowledge",
            description="搜索知识库",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "query": {"type": "string", "description": "搜索查询"},
                    "limit": {"type": "integer", "description": "返回数量", "default": 5},
                    "use_vector": {"type": "boolean", "description": "是否使用向量搜索", "default": True}
                },
                required=["query"]
            )
        ))
        
        self.register_tool(Tool(
            name="update_knowledge",
            description="更新知识条目",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "entry_id": {"type": "string", "description": "条目ID"},
                    "keyword": {"type": "string", "description": "新关键词"},
                    "content": {"type": "string", "description": "新内容"},
                    "description": {"type": "string", "description": "新描述"}
                },
                required=["entry_id"]
            )
        ))
        
        self.register_tool(Tool(
            name="delete_knowledge",
            description="删除知识条目",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "entry_id": {"type": "string", "description": "条目ID"}
                },
                required=["entry_id"]
            )
        ))
        
        # === 世界书工具 ===
        self.register_tool(Tool(
            name="add_world_entry",
            description="添加世界书条目",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "concept": {"type": "string", "description": "世界概念"},
                    "content": {"type": "string", "description": "详细设定"},
                    "category": {"type": "string", "description": "分类"},
                    "keywords": {"type": "array", "items": {"type": "string"}, "description": "关键词列表"}
                },
                required=["concept", "content"]
            )
        ))
        
        self.register_tool(Tool(
            name="search_world",
            description="搜索世界书",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "query": {"type": "string", "description": "搜索查询"},
                    "category": {"type": "string", "description": "按分类过滤"},
                    "limit": {"type": "integer", "description": "返回数量", "default": 5},
                    "use_vector": {"type": "boolean", "description": "是否使用向量搜索", "default": True}
                },
                required=["query"]
            )
        ))
        
        self.register_tool(Tool(
            name="update_world_entry",
            description="更新世界书条目",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "entry_id": {"type": "string", "description": "条目ID"},
                    "concept": {"type": "string", "description": "新概念"},
                    "content": {"type": "string", "description": "新内容"},
                    "category": {"type": "string", "description": "新分类"},
                    "keywords": {"type": "array", "items": {"type": "string"}, "description": "新关键词列表"}
                },
                required=["entry_id"]
            )
        ))
        
        self.register_tool(Tool(
            name="delete_world_entry",
            description="删除世界书条目",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "entry_id": {"type": "string", "description": "条目ID"}
                },
                required=["entry_id"]
            )
        ))
        
        self.register_tool(Tool(
            name="get_role_context",
            description="获取完整的角色上下文（包含人设、知识库和世界书）",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "profile_id": {"type": "string", "description": "指定角色ID"},
                    "keywords": {"type": "array", "items": {"type": "string"}, "description": "搜索关键词"},
                    "knowledge_limit": {"type": "integer", "description": "知识库搜索限制", "default": 3},
                    "world_limit": {"type": "integer", "description": "世界书搜索限制", "default": 3}
                }
            )
        ))
    
    async def _call_tool(self, name: str, arguments: Dict[str, Any], context) -> Dict[str, Any]:
        """处理工具调用"""
        try:
            logger.info(f"角色信息CRUD工具调用: {name}")
            logger.info(f"参数: {arguments}")
            
            # === 角色人设工具 ===
            if name == "create_profile":
                return await self._create_profile(arguments)
            elif name == "update_profile":
                return await self._update_profile(arguments)
            elif name == "query_profile":
                return await self._query_profile(arguments)
            elif name == "delete_profile":
                return await self._delete_profile(arguments)
            elif name == "list_profiles":
                return await self._list_profiles(arguments)
            
            # === 知识库工具 ===
            elif name == "add_knowledge":
                return await self._add_knowledge(arguments)
            elif name == "search_knowledge":
                return await self._search_knowledge(arguments)
            elif name == "update_knowledge":
                return await self._update_knowledge(arguments)
            elif name == "delete_knowledge":
                return await self._delete_knowledge(arguments)
            
            # === 世界书工具 ===
            elif name == "add_world_entry":
                return await self._add_world_entry(arguments)
            elif name == "search_world":
                return await self._search_world(arguments)
            elif name == "update_world_entry":
                return await self._update_world_entry(arguments)
            elif name == "delete_world_entry":
                return await self._delete_world_entry(arguments)
            
            # === 综合工具 ===
            elif name == "get_role_context":
                return await self._get_role_context(arguments)
            
            else:
                return {"error": f"未知工具: {name}"}
                
        except Exception as e:
            logger.error(f"工具调用失败 {name}: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return {
                "error": f"工具调用失败: {str(e)}",
                "tool_name": name,
                "arguments": arguments,
                "timestamp": datetime.now().isoformat()
            }
    
    # === 角色人设方法 ===
    async def _create_profile(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """创建角色人设"""
        name = args["name"]
        content = args["content"]
        tags = args.get("tags", [])
        
        # 生成ID
        profile_id = f"profile_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # 创建角色
        profile = RoleProfile(profile_id, name, content, tags)
        self.profiles[profile_id] = profile
        
        # 保存数据
        self._save_data()
        
        return {
            "success": True,
            "profile_id": profile_id,
            "message": f"✅ 角色人设 '{name}' 创建成功",
            "profile": profile.to_dict()
        }
    
    async def _update_profile(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """更新角色人设"""
        profile_id = args["profile_id"]
        
        if profile_id not in self.profiles:
            return {"error": f"角色ID '{profile_id}' 不存在"}
        
        profile = self.profiles[profile_id]
        
        # 更新字段
        if "name" in args:
            profile.name = args["name"]
        if "content" in args:
            profile.content = args["content"]
        if "tags" in args:
            profile.tags = args["tags"]
        
        profile.updated_at = datetime.now().isoformat()
        
        # 保存数据
        self._save_data()
        
        return {
            "success": True,
            "message": f"✅ 角色人设 '{profile.name}' 更新成功",
            "profile": profile.to_dict()
        }
    
    async def _query_profile(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """查询角色人设"""
        profile_id = args.get("profile_id")
        name_filter = args.get("name")
        tags_filter = args.get("tags", [])
        
        if profile_id:
            # 按ID查询
            if profile_id in self.profiles:
                return {
                    "success": True,
                    "profile": self.profiles[profile_id].to_dict()
                }
            else:
                return {"error": f"角色ID '{profile_id}' 不存在"}
        
        # 过滤查询
        results = []
        for profile in self.profiles.values():
            if name_filter and name_filter.lower() not in profile.name.lower():
                continue
            if tags_filter and not any(tag in profile.tags for tag in tags_filter):
                continue
            results.append(profile.to_dict())
        
        return {
            "success": True,
            "count": len(results),
            "profiles": results
        }
    
    async def _delete_profile(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """删除角色人设"""
        profile_id = args["profile_id"]
        
        if profile_id not in self.profiles:
            return {"error": f"角色ID '{profile_id}' 不存在"}
        
        profile_name = self.profiles[profile_id].name
        del self.profiles[profile_id]
        
        # 保存数据
        self._save_data()
        
        return {
            "success": True,
            "message": f"✅ 角色人设 '{profile_name}' 删除成功"
        }
    
    async def _list_profiles(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """列出所有角色人设"""
        limit = args.get("limit", 10)
        
        profiles = list(self.profiles.values())
        profiles.sort(key=lambda x: x.updated_at, reverse=True)
        
        if limit > 0:
            profiles = profiles[:limit]
        
        return {
            "success": True,
            "total": len(self.profiles),
            "count": len(profiles),
            "profiles": [p.to_dict() for p in profiles]
        }
    
    # === 知识库方法 ===
    async def _add_knowledge(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """添加知识条目"""
        keyword = args["keyword"]
        content = args["content"]
        description = args.get("description", "")
        
        # 生成ID
        entry_id = f"knowledge_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # 创建条目
        entry = KnowledgeEntry(entry_id, keyword, content, description)
        self.knowledge_entries[entry_id] = entry
        
        # 添加到向量数据库
        if self.knowledge_collection:
            try:
                self.knowledge_collection.add(
                    documents=[content],
                    metadatas=[{
                        "id": entry_id,
                        "keyword": keyword,
                        "description": description,
                        "created_at": entry.created_at
                    }],
                    ids=[entry_id]
                )
            except Exception as e:
                logger.warning(f"向量数据库添加失败: {e}")
        
        # 保存数据
        self._save_data()
        
        return {
            "success": True,
            "entry_id": entry_id,
            "message": f"✅ 知识条目 '{keyword}' 添加成功",
            "entry": entry.to_dict()
        }
    
    async def _search_knowledge(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """搜索知识库"""
        query = args["query"]
        limit = args.get("limit", 5)
        use_vector = args.get("use_vector", True)
        
        results = []
        
        # 向量搜索
        if use_vector and self.knowledge_collection:
            try:
                vector_results = self.knowledge_collection.query(
                    query_texts=[query],
                    n_results=limit
                )
                
                for i, doc_id in enumerate(vector_results["ids"][0]):
                    if doc_id in self.knowledge_entries:
                        entry = self.knowledge_entries[doc_id]
                        results.append({
                            **entry.to_dict(),
                            "score": 1 - vector_results["distances"][0][i],
                            "search_type": "vector"
                        })
                        
            except Exception as e:
                logger.warning(f"向量搜索失败: {e}")
        
        # 如果向量搜索没有结果，使用文本搜索
        if not results:
            query_lower = query.lower()
            for entry in self.knowledge_entries.values():
                score = 0
                if query_lower in entry.keyword.lower():
                    score += 0.8
                if query_lower in entry.content.lower():
                    score += 0.6
                if query_lower in entry.description.lower():
                    score += 0.4
                
                if score > 0:
                    results.append({
                        **entry.to_dict(),
                        "score": score,
                        "search_type": "text"
                    })
            
            # 按分数排序
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:limit]
        
        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": results
        }
    
    async def _update_knowledge(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """更新知识条目"""
        entry_id = args["entry_id"]
        
        if entry_id not in self.knowledge_entries:
            return {"error": f"知识条目ID '{entry_id}' 不存在"}
        
        entry = self.knowledge_entries[entry_id]
        
        # 更新字段
        if "keyword" in args:
            entry.keyword = args["keyword"]
        if "content" in args:
            entry.content = args["content"]
        if "description" in args:
            entry.description = args["description"]
        
        entry.updated_at = datetime.now().isoformat()
        
        # 更新向量数据库
        if self.knowledge_collection:
            try:
                self.knowledge_collection.update(
                    ids=[entry_id],
                    documents=[entry.content],
                    metadatas=[{
                        "id": entry_id,
                        "keyword": entry.keyword,
                        "description": entry.description,
                        "updated_at": entry.updated_at
                    }]
                )
            except Exception as e:
                logger.warning(f"向量数据库更新失败: {e}")
        
        # 保存数据
        self._save_data()
        
        return {
            "success": True,
            "message": f"✅ 知识条目 '{entry.keyword}' 更新成功",
            "entry": entry.to_dict()
        }
    
    async def _delete_knowledge(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """删除知识条目"""
        entry_id = args["entry_id"]
        
        if entry_id not in self.knowledge_entries:
            return {"error": f"知识条目ID '{entry_id}' 不存在"}
        
        entry_keyword = self.knowledge_entries[entry_id].keyword
        del self.knowledge_entries[entry_id]
        
        # 从向量数据库删除
        if self.knowledge_collection:
            try:
                self.knowledge_collection.delete(ids=[entry_id])
            except Exception as e:
                logger.warning(f"向量数据库删除失败: {e}")
        
        # 保存数据
        self._save_data()
        
        return {
            "success": True,
            "message": f"✅ 知识条目 '{entry_keyword}' 删除成功"
        }
    
    # === 世界书方法 ===
    async def _add_world_entry(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """添加世界书条目"""
        concept = args["concept"]
        content = args["content"]
        category = args.get("category", "")
        keywords = args.get("keywords", [])
        
        # 生成ID
        entry_id = f"world_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # 创建条目
        entry = WorldBookEntry(entry_id, concept, content, category, keywords)
        self.worldbook_entries[entry_id] = entry
        
        # 添加到向量数据库
        if self.worldbook_collection:
            try:
                self.worldbook_collection.add(
                    documents=[content],
                    metadatas=[{
                        "id": entry_id,
                        "concept": concept,
                        "category": category,
                        "keywords": keywords,
                        "created_at": entry.created_at
                    }],
                    ids=[entry_id]
                )
            except Exception as e:
                logger.warning(f"向量数据库添加失败: {e}")
        
        # 保存数据
        self._save_data()
        
        return {
            "success": True,
            "entry_id": entry_id,
            "message": f"✅ 世界书条目 '{concept}' 添加成功",
            "entry": entry.to_dict()
        }
    
    async def _search_world(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """搜索世界书"""
        query = args["query"]
        category_filter = args.get("category")
        limit = args.get("limit", 5)
        use_vector = args.get("use_vector", True)
        
        results = []
        
        # 向量搜索
        if use_vector and self.worldbook_collection:
            try:
                where_filter = {}
                if category_filter:
                    where_filter["category"] = category_filter
                
                vector_results = self.worldbook_collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=where_filter if where_filter else None
                )
                
                for i, doc_id in enumerate(vector_results["ids"][0]):
                    if doc_id in self.worldbook_entries:
                        entry = self.worldbook_entries[doc_id]
                        results.append({
                            **entry.to_dict(),
                            "score": 1 - vector_results["distances"][0][i],
                            "search_type": "vector"
                        })
                        
            except Exception as e:
                logger.warning(f"向量搜索失败: {e}")
        
        # 如果向量搜索没有结果，使用文本搜索
        if not results:
            query_lower = query.lower()
            for entry in self.worldbook_entries.values():
                # 分类过滤
                if category_filter and entry.category != category_filter:
                    continue
                
                score = 0
                if query_lower in entry.concept.lower():
                    score += 0.8
                if query_lower in entry.content.lower():
                    score += 0.6
                if any(query_lower in kw.lower() for kw in entry.keywords):
                    score += 0.7
                
                if score > 0:
                    results.append({
                        **entry.to_dict(),
                        "score": score,
                        "search_type": "text"
                    })
            
            # 按分数排序
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:limit]
        
        return {
            "success": True,
            "query": query,
            "category": category_filter,
            "count": len(results),
            "results": results
        }
    
    async def _update_world_entry(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """更新世界书条目"""
        entry_id = args["entry_id"]
        
        if entry_id not in self.worldbook_entries:
            return {"error": f"世界书条目ID '{entry_id}' 不存在"}
        
        entry = self.worldbook_entries[entry_id]
        
        # 更新字段
        if "concept" in args:
            entry.concept = args["concept"]
        if "content" in args:
            entry.content = args["content"]
        if "category" in args:
            entry.category = args["category"]
        if "keywords" in args:
            entry.keywords = args["keywords"]
        
        entry.updated_at = datetime.now().isoformat()
        
        # 更新向量数据库
        if self.worldbook_collection:
            try:
                self.worldbook_collection.update(
                    ids=[entry_id],
                    documents=[entry.content],
                    metadatas=[{
                        "id": entry_id,
                        "concept": entry.concept,
                        "category": entry.category,
                        "keywords": entry.keywords,
                        "updated_at": entry.updated_at
                    }]
                )
            except Exception as e:
                logger.warning(f"向量数据库更新失败: {e}")
        
        # 保存数据
        self._save_data()
        
        return {
            "success": True,
            "message": f"✅ 世界书条目 '{entry.concept}' 更新成功",
            "entry": entry.to_dict()
        }
    
    async def _delete_world_entry(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """删除世界书条目"""
        entry_id = args["entry_id"]
        
        if entry_id not in self.worldbook_entries:
            return {"error": f"世界书条目ID '{entry_id}' 不存在"}
        
        entry_concept = self.worldbook_entries[entry_id].concept
        del self.worldbook_entries[entry_id]
        
        # 从向量数据库删除
        if self.worldbook_collection:
            try:
                self.worldbook_collection.delete(ids=[entry_id])
            except Exception as e:
                logger.warning(f"向量数据库删除失败: {e}")
        
        # 保存数据
        self._save_data()
        
        return {
            "success": True,
            "message": f"✅ 世界书条目 '{entry_concept}' 删除成功"
        }
    
    # === 综合方法 ===
    async def _get_role_context(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """获取完整的角色上下文"""
        profile_id = args.get("profile_id")
        keywords = args.get("keywords", [])
        knowledge_limit = args.get("knowledge_limit", 3)
        world_limit = args.get("world_limit", 3)
        
        context = {}
        
        # 获取角色人设
        if profile_id:
            if profile_id in self.profiles:
                context["profile"] = self.profiles[profile_id].to_dict()
            else:
                return {"error": f"角色ID '{profile_id}' 不存在"}
        else:
            # 如果没有指定，获取最新的角色
            if self.profiles:
                latest_profile = max(self.profiles.values(), key=lambda x: x.updated_at)
                context["profile"] = latest_profile.to_dict()
        
        # 搜索相关知识
        if keywords:
            knowledge_results = []
            world_results = []
            
            for keyword in keywords:
                # 搜索知识库
                kb_search = await self._search_knowledge({
                    "query": keyword,
                    "limit": knowledge_limit
                })
                if kb_search.get("success"):
                    knowledge_results.extend(kb_search.get("results", []))
                
                # 搜索世界书
                world_search = await self._search_world({
                    "query": keyword,
                    "limit": world_limit
                })
                if world_search.get("success"):
                    world_results.extend(world_search.get("results", []))
            
            # 去重并排序
            knowledge_results = list({r["id"]: r for r in knowledge_results}.values())
            world_results = list({r["id"]: r for r in world_results}.values())
            
            knowledge_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            world_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            context["knowledge"] = knowledge_results[:knowledge_limit]
            context["worldbook"] = world_results[:world_limit]
        
        return {
            "success": True,
            "context": context,
            "summary": {
                "has_profile": "profile" in context,
                "knowledge_count": len(context.get("knowledge", [])),
                "worldbook_count": len(context.get("worldbook", []))
            }
        }
    
    async def cleanup(self):
        """清理资源"""
        logger.info("正在清理角色信息CRUD服务器...")
        
        # 保存数据
        self._save_data()
        
        # 清理ChromaDB连接
        if self.chroma_client:
            try:
                # ChromaDB没有显式的关闭方法，Python会自动清理
                pass
            except Exception as e:
                logger.warning(f"清理ChromaDB连接失败: {e}")
        
        logger.info("角色信息CRUD服务器清理完成")


async def test_role_info_crud():
    """测试角色信息CRUD功能"""
    print("🚀 角色信息CRUD服务器 - 本地测试")
    print("=" * 60)
    
    server = RoleInfoCRUDServer()
    
    try:
        # 测试创建角色人设
        print("\n1. 测试创建角色人设")
        result = await server._create_profile({
            "name": "方知衡",
            "content": "28岁天文系客座教授，性格清冷但负责任，喜欢在咖啡店工作，有晨跑习惯",
            "tags": ["教授", "天文", "清冷"]
        })
        print(f"结果: {result}")
        profile_id = result.get("profile_id")
        
        # 测试添加知识
        print("\n2. 测试添加知识")
        result = await server._add_knowledge({
            "keyword": "天文观测",
            "content": "使用专业望远镜进行星空观测，记录天体运动轨迹",
            "description": "方知衡的专业技能"
        })
        print(f"结果: {result}")
        
        # 测试添加世界书
        print("\n3. 测试添加世界书")
        result = await server._add_world_entry({
            "concept": "城市大学",
            "content": "方知衡工作的大学，拥有先进的天文台设施",
            "category": "地点",
            "keywords": ["大学", "天文台", "教学"]
        })
        print(f"结果: {result}")
        
        # 测试搜索
        print("\n4. 测试搜索知识")
        result = await server._search_knowledge({
            "query": "天文",
            "limit": 5
        })
        print(f"结果: {result}")
        
        # 测试获取角色上下文
        print("\n5. 测试获取角色上下文")
        result = await server._get_role_context({
            "profile_id": profile_id,
            "keywords": ["天文", "大学"],
            "knowledge_limit": 3,
            "world_limit": 3
        })
        print(f"结果: {result}")
        
        print("\n✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await server.cleanup()


async def main():
    """主函数"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 检查启动模式
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # 本地测试模式
        await test_role_info_crud()
    else:
        # MCP服务器模式
        server = RoleInfoCRUDServer()
        logger.info("🚀 启动角色信息CRUD MCP服务器...")
        await server.start()


if __name__ == "__main__":
    asyncio.run(main())