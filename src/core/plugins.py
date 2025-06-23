"""
角色插件系统 - 提供角色资料和角色知识库的全局配置管理
"""
import os
import json
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


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
    processed_data: List[str] = None  # 处理后的文本数据
    
    def __post_init__(self):
        if self.processed_data is None:
            self.processed_data = []


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
    """角色知识库插件"""
    
    def __init__(self):
        super().__init__(
            plugin_id="role_knowledge_base",
            name="角色知识库",
            description="提供基于向量搜索的角色知识库"
        )
        self.knowledge_base: Optional[RoleKnowledgeBase] = None
        self._vector_store = None
    
    def set_knowledge_base(self, name: str, source_file: str, description: str = "", search_limit: int = 3):
        """设置角色知识库"""
        now = datetime.now().isoformat()
        self.knowledge_base = RoleKnowledgeBase(
            name=name,
            source_file=source_file,
            description=description,
            created_at=now,
            search_limit=search_limit
        )
        # 立即处理源文件
        self._process_source_file()
        logger.info(f"角色知识库已设置: {name} -> {source_file}")
    
    def _process_source_file(self):
        """处理源文件（txt或csv）为知识库数据"""
        if not self.knowledge_base or not self.knowledge_base.source_file:
            return
        
        source_path = Path(self.knowledge_base.source_file)
        if not source_path.exists():
            logger.warning(f"知识库源文件不存在: {source_path}")
            return
        
        try:
            self.knowledge_base.processed_data = []
            
            if source_path.suffix.lower() == '.txt':
                # 处理txt文件
                with open(source_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 按段落分割
                paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
                self.knowledge_base.processed_data = paragraphs
                
            elif source_path.suffix.lower() == '.csv':
                # 处理csv文件
                import csv
                with open(source_path, 'r', encoding='utf-8') as f:
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
            
            logger.info(f"知识库数据处理完成: {len(self.knowledge_base.processed_data)} 条")
            
        except Exception as e:
            logger.error(f"处理知识库源文件失败: {e}")
            self.knowledge_base.processed_data = []
    
    async def _init_vector_store(self):
        """初始化向量存储"""
        if not self.knowledge_base or self._vector_store:
            return
        
        try:
            # 这里可以根据实际需要集成不同的向量数据库
            # 暂时使用简单的文件系统模拟
            kb_path = Path(self.knowledge_base.path)
            if kb_path.exists():
                logger.info(f"向量知识库路径存在: {kb_path}")
                self._vector_store = "initialized"  # 标记为已初始化
            else:
                logger.warning(f"向量知识库路径不存在: {kb_path}")
        except Exception as e:
            logger.error(f"初始化向量知识库失败: {e}")
    
    async def search_knowledge(self, keywords: List[str], limit: int = None) -> List[Dict[str, Any]]:
        """搜索知识库"""
        if not self.enabled or not self.knowledge_base or not self.knowledge_base.processed_data:
            return []
        
        # 使用指定的搜索限制或默认限制
        search_limit = limit or self.knowledge_base.search_limit
        
        try:
            results = []
            
            # 简单的关键词匹配搜索
            for keyword in keywords:
                keyword_lower = keyword.lower()
                matches = []
                
                for i, text in enumerate(self.knowledge_base.processed_data):
                    if keyword_lower in text.lower():
                        # 计算简单的相关性分数（关键词出现次数）
                        score = text.lower().count(keyword_lower) / len(text.split())
                        matches.append({
                            "content": text,
                            "score": score,
                            "source": f"knowledge_item_{i+1}",
                            "keyword": keyword
                        })
                
                # 按分数排序，取前几个
                matches.sort(key=lambda x: x['score'], reverse=True)
                results.extend(matches[:search_limit])
            
            # 去重并限制总数
            seen_content = set()
            unique_results = []
            for result in results:
                if result['content'] not in seen_content:
                    seen_content.add(result['content'])
                    unique_results.append(result)
                    if len(unique_results) >= search_limit:
                        break
            
            logger.info(f"知识库搜索完成: {len(keywords)} 个关键词 -> {len(unique_results)} 个结果")
            return unique_results
            
        except Exception as e:
            logger.error(f"搜索知识库失败: {e}")
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
        
        await self._init_vector_store()
        return self._vector_store is not None
    
    def get_knowledge_base_info(self) -> Optional[Dict[str, Any]]:
        """获取知识库信息"""
        if not self.knowledge_base:
            return None
        return {
            "name": self.knowledge_base.name,
            "source_file": self.knowledge_base.source_file,
            "description": self.knowledge_base.description,
            "enabled": self.knowledge_base.enabled,
            "search_limit": self.knowledge_base.search_limit,
            "created_at": self.knowledge_base.created_at,
            "data_count": len(self.knowledge_base.processed_data) if self.knowledge_base.processed_data else 0
        }
    
    def clear_knowledge_base(self):
        """清空知识库配置"""
        self.knowledge_base = None
        self._vector_store = None
        logger.info("角色知识库配置已清空")


class RolePluginManager:
    """角色插件管理器"""
    
    def __init__(self, workspace_dir: str = "./workspace"):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(exist_ok=True)
        
        # 初始化插件
        self.profile_plugin = RoleProfilePlugin()
        self.knowledge_base_plugin = RoleKnowledgeBasePlugin()
        
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
                        self.knowledge_base_plugin.set_knowledge_base(
                            name=kb_config.get("name", "默认知识库"),
                            source_file=source_file,
                            description=kb_config.get("description", ""),
                            search_limit=kb_config.get("search_limit", 3)
                        )
                        # 如果有保存的处理数据，直接加载
                        if "processed_data" in kb_config and self.knowledge_base_plugin.knowledge_base:
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
    
    def configure_knowledge_base(self, name: str, source_file: str, description: str = "", 
                                search_limit: int = 3, enabled: bool = True):
        """配置角色知识库"""
        self.knowledge_base_plugin.set_knowledge_base(name, source_file, description, search_limit)
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