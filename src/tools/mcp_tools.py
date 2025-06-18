#!/usr/bin/env python3
"""
MCP工具管理器
将MCP服务器的工具、资源和提示集成到Agent工具系统中
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
import json

from .base import ToolManager
from ..core.base import BaseTool
from .mcp_manager import mcp_manager, MCPServerType

logger = logging.getLogger(__name__)


class MCPTool(BaseTool):
    """MCP工具包装器"""
    
    def __init__(self, server_id: str, tool_name: str, tool_schema: Dict[str, Any]):
        """
        初始化MCP工具
        
        Args:
            server_id: MCP服务器ID
            tool_name: 工具名称
            tool_schema: 工具模式定义
        """
        self.server_id = server_id
        self.original_name = tool_name
        
        # 构造唯一的工具名称
        unique_name = f"mcp_{server_id}_{tool_name}"
        
        super().__init__(
            name=unique_name,
            description=tool_schema.get("description", f"MCP工具: {tool_name}"),
            parameters=tool_schema.get("inputSchema", {})
        )
    
    async def execute(self, **kwargs) -> Any:
        """执行MCP工具"""
        try:
            # 调用MCP服务器的工具
            result = await mcp_manager.call_tool(
                self.server_id, 
                self.original_name, 
                kwargs
            )
            
            # 解析结果
            if hasattr(result, 'content') and result.content:
                content = result.content[0] if result.content else None
                if content:
                    if hasattr(content, 'text'):
                        return content.text
                    elif hasattr(content, 'data'):
                        return content.data
            
            return str(result)
            
        except Exception as e:
            logger.error(f"MCP工具执行失败 {self.name}: {e}")
            raise Exception(f"MCP工具执行失败: {e}")


class MCPResourceTool(BaseTool):
    """MCP资源访问工具"""
    
    def __init__(self, server_id: str, resource_name: str, resource_info: Dict[str, Any]):
        """
        初始化MCP资源工具
        
        Args:
            server_id: MCP服务器ID
            resource_name: 资源名称
            resource_info: 资源信息
        """
        self.server_id = server_id
        self.resource_uri = resource_info.get("uri", resource_name)
        
        # 构造唯一的工具名称
        unique_name = f"mcp_resource_{server_id}_{resource_name}"
        
        super().__init__(
            name=unique_name,
            description=f"获取MCP资源: {resource_info.get('description', resource_name)}",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    
    async def execute(self, **kwargs) -> Any:
        """获取MCP资源"""
        try:
            result = await mcp_manager.get_resource(self.server_id, self.resource_uri)
            
            # 解析资源内容
            if hasattr(result, 'contents') and result.contents:
                content = result.contents[0] if result.contents else None
                if content:
                    if hasattr(content, 'text'):
                        return content.text
                    elif hasattr(content, 'blob'):
                        return f"二进制资源 (大小: {len(content.blob)} bytes)"
            
            return str(result)
            
        except Exception as e:
            logger.error(f"MCP资源获取失败 {self.name}: {e}")
            raise Exception(f"MCP资源获取失败: {e}")


class MCPPromptTool(BaseTool):
    """MCP提示工具"""
    
    def __init__(self, server_id: str, prompt_name: str, prompt_info: Dict[str, Any]):
        """
        初始化MCP提示工具
        
        Args:
            server_id: MCP服务器ID
            prompt_name: 提示名称
            prompt_info: 提示信息
        """
        self.server_id = server_id
        self.original_name = prompt_name
        
        # 构造唯一的工具名称
        unique_name = f"mcp_prompt_{server_id}_{prompt_name}"
        
        # 构建参数模式
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # 从提示参数构建工具参数
        if "arguments" in prompt_info:
            for arg in prompt_info["arguments"]:
                arg_name = arg.get("name", "")
                parameters["properties"][arg_name] = {
                    "type": "string",
                    "description": arg.get("description", "")
                }
                if arg.get("required", False):
                    parameters["required"].append(arg_name)
        
        super().__init__(
            name=unique_name,
            description=f"使用MCP提示: {prompt_info.get('description', prompt_name)}",
            parameters=parameters
        )
    
    async def execute(self, **kwargs) -> Any:
        """执行MCP提示"""
        try:
            result = await mcp_manager.get_prompt(self.server_id, self.original_name, kwargs)
            
            # 解析提示结果
            if hasattr(result, 'messages') and result.messages:
                # 将消息转换为文本
                messages = []
                for msg in result.messages:
                    if hasattr(msg, 'content'):
                        if hasattr(msg.content, 'text'):
                            messages.append(f"{msg.role}: {msg.content.text}")
                        else:
                            messages.append(f"{msg.role}: {str(msg.content)}")
                
                return "\n".join(messages)
            
            return str(result)
            
        except Exception as e:
            logger.error(f"MCP提示执行失败 {self.name}: {e}")
            raise Exception(f"MCP提示执行失败: {e}")


class MCPToolManager(ToolManager):
    """增强的工具管理器，集成MCP服务"""
    
    def __init__(self, enabled_servers: Optional[List[str]] = None):
        """
        初始化MCP工具管理器
        
        Args:
            enabled_servers: 启用的MCP服务器列表
        """
        super().__init__()
        self.enabled_servers = enabled_servers or []
        self.mcp_tools: Dict[str, BaseTool] = {}
        
    async def initialize(self):
        """初始化工具管理器"""
        # 连接并加载MCP服务器
        await self._load_mcp_servers()
        
        logger.info(f"MCP工具管理器初始化完成，加载了 {len(self.mcp_tools)} 个MCP工具")
    
    async def cleanup(self):
        """清理资源"""
        await mcp_manager.cleanup()
    
    async def enable_tool(self, tool_name: str):
        """启用工具"""
        super().enable_tool(tool_name)
    
    async def _load_mcp_servers(self):
        """加载MCP服务器"""
        # 如果没有指定启用的服务器，则启用所有可用的
        if not self.enabled_servers:
            self.enabled_servers = list(mcp_manager.servers.keys())
        
        # 连接启用的服务器
        for server_id in self.enabled_servers:
            await self._connect_and_load_server(server_id)
    
    async def _connect_and_load_server(self, server_id: str):
        """连接并加载单个MCP服务器"""
        try:
            # 启用服务器（会自动连接）
            success = await mcp_manager.enable_server(server_id)
            if not success:
                logger.warning(f"无法连接MCP服务器: {server_id}")
                return
            
            # 获取服务器信息
            servers_info = mcp_manager.list_servers()
            server_info = next((s for s in servers_info if s['id'] == server_id), None)
            if not server_info:
                logger.warning(f"找不到服务器信息: {server_id}")
                return
            
            # 加载工具
            await self._load_server_tools(server_id, server_info)
            
            # 加载资源（作为工具）
            await self._load_server_resources(server_id, server_info)
            
            # 加载提示（作为工具）
            await self._load_server_prompts(server_id, server_info)
            
            logger.info(f"成功加载MCP服务器: {server_info['name']}")
            
        except Exception as e:
            logger.error(f"加载MCP服务器失败 {server_id}: {e}")
    
    async def _load_server_tools(self, server_id: str, server_info: Dict[str, Any]):
        """加载服务器工具"""
        if server_id not in mcp_manager.sessions:
            return
        
        try:
            session = mcp_manager.sessions[server_id]
            tools_result = await session.list_tools()
            
            if tools_result and tools_result.tools:
                for tool in tools_result.tools:
                    mcp_tool = MCPTool(server_id, tool.name, {
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    })
                    
                    self.mcp_tools[mcp_tool.name] = mcp_tool
                    self.tools[mcp_tool.name] = mcp_tool
                    
                logger.info(f"加载了 {len(tools_result.tools)} 个工具从 {server_id}")
                
        except Exception as e:
            logger.warning(f"加载服务器工具失败 {server_id}: {e}")
    
    async def _load_server_resources(self, server_id: str, server_info: Dict[str, Any]):
        """加载服务器资源"""
        if server_id not in mcp_manager.sessions:
            return
        
        try:
            session = mcp_manager.sessions[server_id]
            resources_result = await session.list_resources()
            
            if resources_result and resources_result.resources:
                for resource in resources_result.resources:
                    resource_tool = MCPResourceTool(server_id, resource.name, {
                        "uri": resource.uri,
                        "description": resource.description,
                        "mimeType": getattr(resource, 'mimeType', None)
                    })
                    
                    self.mcp_tools[resource_tool.name] = resource_tool
                    self.tools[resource_tool.name] = resource_tool
                    
                logger.info(f"加载了 {len(resources_result.resources)} 个资源从 {server_id}")
                
        except Exception as e:
            logger.warning(f"加载服务器资源失败 {server_id}: {e}")
    
    async def _load_server_prompts(self, server_id: str, server_info: Dict[str, Any]):
        """加载服务器提示"""
        if server_id not in mcp_manager.sessions:
            return
        
        try:
            session = mcp_manager.sessions[server_id]
            prompts_result = await session.list_prompts()
            
            if prompts_result and prompts_result.prompts:
                for prompt in prompts_result.prompts:
                    prompt_tool = MCPPromptTool(server_id, prompt.name, {
                        "description": prompt.description,
                        "arguments": prompt.arguments
                    })
                    
                    self.mcp_tools[prompt_tool.name] = prompt_tool
                    self.tools[prompt_tool.name] = prompt_tool
                    
                logger.info(f"加载了 {len(prompts_result.prompts)} 个提示从 {server_id}")
                
        except Exception as e:
            logger.warning(f"加载服务器提示失败 {server_id}: {e}")
    
    def enable_mcp_server(self, server_id: str):
        """启用MCP服务器"""
        if server_id not in self.enabled_servers:
            self.enabled_servers.append(server_id)
    
    def disable_mcp_server(self, server_id: str):
        """禁用MCP服务器"""
        if server_id in self.enabled_servers:
            self.enabled_servers.remove(server_id)
            
            # 移除该服务器的所有工具
            tools_to_remove = [
                name for name, tool in self.mcp_tools.items()
                if hasattr(tool, 'server_id') and tool.server_id == server_id
            ]
            
            for tool_name in tools_to_remove:
                del self.mcp_tools[tool_name]
                if tool_name in self.tools:
                    del self.tools[tool_name]
    
    def get_mcp_servers_status(self) -> List[Dict[str, Any]]:
        """获取MCP服务器状态"""
        return mcp_manager.list_servers()
    
    async def refresh_mcp_servers(self):
        """刷新MCP服务器"""
        # 清除现有MCP工具
        for tool_name in list(self.mcp_tools.keys()):
            if tool_name in self.tools:
                del self.tools[tool_name]
        self.mcp_tools.clear()
        
        # 重新加载
        await self._load_mcp_servers()
    
    def get_tools_description(self) -> str:
        """获取工具描述"""
        base_desc = super().get_tools_description()
        
        # 添加MCP工具说明
        if self.mcp_tools:
            mcp_desc = "\n\n=== MCP服务工具 ==="
            
            # 按服务器分组
            servers = {}
            for tool_name, tool in self.mcp_tools.items():
                if hasattr(tool, 'server_id'):
                    server_id = tool.server_id
                    if server_id not in servers:
                        servers[server_id] = []
                    servers[server_id].append(tool)
            
            for server_id, tools in servers.items():
                server_info = next((s for s in mcp_manager.list_servers() if s['id'] == server_id), None)
                server_name = server_info['name'] if server_info else server_id
                
                mcp_desc += f"\n\n{server_name}:"
                for tool in tools:
                    mcp_desc += f"\n- {tool.name}: {tool.description}"
            
            base_desc += mcp_desc
        
        return base_desc 