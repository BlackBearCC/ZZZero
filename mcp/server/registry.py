"""
MCP服务端注册表
用于管理资源、工具和提示的注册
"""
from typing import Dict, List, Optional, Callable, Any
import logging

from ..types import Resource, Tool, Prompt

logger = logging.getLogger(__name__)


class Registry:
    """基础注册表"""
    
    def __init__(self):
        """初始化注册表"""
        self._items: Dict[str, Any] = {}
        self._change_callbacks: List[Callable] = []
    
    def register(self, key: str, item: Any):
        """注册项目"""
        self._items[key] = item
        self._notify_change()
    
    def unregister(self, key: str) -> Optional[Any]:
        """取消注册项目"""
        item = self._items.pop(key, None)
        if item:
            self._notify_change()
        return item
    
    def get(self, key: str) -> Optional[Any]:
        """获取项目"""
        return self._items.get(key)
    
    def list_all(self) -> List[Any]:
        """列出所有项目"""
        return list(self._items.values())
    
    def keys(self) -> List[str]:
        """获取所有键"""
        return list(self._items.keys())
    
    def add_change_callback(self, callback: Callable):
        """添加变更回调"""
        self._change_callbacks.append(callback)
    
    def _notify_change(self):
        """通知变更"""
        for callback in self._change_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in change callback: {e}")


class ResourceRegistry(Registry):
    """资源注册表"""
    
    def register_resource(self, resource: Resource):
        """注册资源"""
        self.register(resource.uri, resource)
        logger.info(f"Registered resource: {resource.name} ({resource.uri})")
    
    def unregister_resource(self, uri: str) -> Optional[Resource]:
        """取消注册资源"""
        resource = self.unregister(uri)
        if resource:
            logger.info(f"Unregistered resource: {resource.name} ({uri})")
        return resource
    
    def get_resource(self, uri: str) -> Optional[Resource]:
        """获取资源"""
        return self.get(uri)
    
    def list_resources(self) -> List[Resource]:
        """列出所有资源"""
        return self.list_all()


class ToolRegistry(Registry):
    """工具注册表"""
    
    def register_tool(self, tool: Tool):
        """注册工具"""
        self.register(tool.name, tool)
        logger.info(f"Registered tool: {tool.name}")
    
    def unregister_tool(self, name: str) -> Optional[Tool]:
        """取消注册工具"""
        tool = self.unregister(name)
        if tool:
            logger.info(f"Unregistered tool: {tool.name}")
        return tool
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self.get(name)
    
    def list_tools(self) -> List[Tool]:
        """列出所有工具"""
        return self.list_all()


class PromptRegistry(Registry):
    """提示注册表"""
    
    def register_prompt(self, prompt: Prompt):
        """注册提示"""
        self.register(prompt.name, prompt)
        logger.info(f"Registered prompt: {prompt.name}")
    
    def unregister_prompt(self, name: str) -> Optional[Prompt]:
        """取消注册提示"""
        prompt = self.unregister(name)
        if prompt:
            logger.info(f"Unregistered prompt: {prompt.name}")
        return prompt
    
    def get_prompt(self, name: str) -> Optional[Prompt]:
        """获取提示"""
        return self.get(name)
    
    def list_prompts(self) -> List[Prompt]:
        """列出所有提示"""
        return self.list_all() 