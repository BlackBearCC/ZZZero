#!/usr/bin/env python3
"""
增强版MCP管理器
支持本地和远程MCP服务器的统一管理
"""
import os
import sys
import asyncio
import subprocess
import logging
import httpx
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

# 使用安装的mcp包
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

logger = logging.getLogger(__name__)


class MCPServerType(Enum):
    """MCP服务器类型"""
    LOCAL_STDIO = "local_stdio"
    REMOTE_HTTP = "remote_http"
    LOCAL_HTTP = "local_http"


@dataclass
class MCPServerConfig:
    """MCP服务器配置"""
    name: str
    type: MCPServerType
    description: str
    
    # 本地stdio配置
    script_path: Optional[str] = None
    args: Optional[List[str]] = None
    cwd: Optional[str] = None
    
    # HTTP配置
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    
    # 状态
    enabled: bool = False
    connected: bool = False
    
    # 元数据
    capabilities: Optional[Dict[str, Any]] = None
    tools: Optional[List[str]] = None
    resources: Optional[List[str]] = None
    prompts: Optional[List[str]] = None


class MCPManager:
    """增强版MCP管理器"""
    
    def __init__(self):
        """初始化MCP管理器"""
        self.servers: Dict[str, MCPServerConfig] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        
        # 注册内置服务器
        self._register_builtin_servers()
        
        logger.info("MCP管理器初始化完成")
    
    def _register_builtin_servers(self):
        """注册内置服务器"""
        # 获取mcp_servers目录路径
        mcp_servers_dir = Path(__file__).parent.parent.parent / "mcp_servers"
        
        # CSV CRUD服务器
        self.servers["csv"] = MCPServerConfig(
            name="CSV CRUD服务器",
            type=MCPServerType.LOCAL_STDIO,
            description="高级CSV数据库服务器，支持完整的CRUD操作、复杂查询、数据验证等",
            script_path=str(mcp_servers_dir / "csv_crud_server.py"),
            args=[],
            cwd=str(mcp_servers_dir)
        )
        
        # ChromaDB CRUD服务器
        self.servers["chromadb"] = MCPServerConfig(
            name="ChromaDB CRUD服务器", 
            type=MCPServerType.LOCAL_STDIO,
            description="高级ChromaDB向量数据库服务器，支持向量存储、语义搜索、集合管理等",
            script_path=str(mcp_servers_dir / "chromadb_crud_server.py"),
            args=[],
            cwd=str(mcp_servers_dir)
        )
    
    def add_remote_server(self, server_id: str, name: str, url: str, 
                         description: str = "", headers: Optional[Dict[str, str]] = None):
        """添加远程MCP服务器"""
        self.servers[server_id] = MCPServerConfig(
            name=name,
            type=MCPServerType.REMOTE_HTTP,
            description=description,
            url=url,
            headers=headers or {}
        )
        logger.info(f"已添加远程MCP服务器: {name} ({url})")
    
    def add_local_http_server(self, server_id: str, name: str, url: str,
                             description: str = "", headers: Optional[Dict[str, str]] = None):
        """添加本地HTTP MCP服务器"""
        self.servers[server_id] = MCPServerConfig(
            name=name,
            type=MCPServerType.LOCAL_HTTP,
            description=description,
            url=url,
            headers=headers or {}
        )
        logger.info(f"已添加本地HTTP MCP服务器: {name} ({url})")
    
    def list_servers(self) -> List[Dict[str, Any]]:
        """列出所有服务器"""
        servers_info = []
        for server_id, config in self.servers.items():
            info = {
                'id': server_id,
                'name': config.name,
                'type': config.type.value,
                'description': config.description,
                'enabled': config.enabled,
                'connected': config.connected,
                'capabilities': config.capabilities,
                'tools': config.tools or [],
                'resources': config.resources or [],
                'prompts': config.prompts or []
            }
            
            if config.type == MCPServerType.REMOTE_HTTP or config.type == MCPServerType.LOCAL_HTTP:
                info['url'] = config.url
            elif config.type == MCPServerType.LOCAL_STDIO:
                info['script_path'] = config.script_path
                
            servers_info.append(info)
        
        return servers_info
    
    async def connect_server(self, server_id: str) -> bool:
        """连接服务器"""
        if server_id not in self.servers:
            logger.error(f"未知服务器: {server_id}")
            return False
        
        config = self.servers[server_id]
        
        try:
            if config.type == MCPServerType.LOCAL_STDIO:
                success = await self._connect_stdio_server(server_id, config)
            elif config.type in [MCPServerType.REMOTE_HTTP, MCPServerType.LOCAL_HTTP]:
                success = await self._connect_http_server(server_id, config)
            else:
                logger.error(f"不支持的服务器类型: {config.type}")
                return False
            
            if success:
                config.connected = True
                await self._fetch_server_capabilities(server_id)
                logger.info(f"成功连接服务器: {config.name}")
            
            return success
            
        except Exception as e:
            logger.error(f"连接服务器失败 {config.name}: {e}")
            return False
    
    async def _connect_stdio_server(self, server_id: str, config: MCPServerConfig) -> bool:
        """连接stdio服务器"""
        if not config.script_path or not Path(config.script_path).exists():
            logger.error(f"脚本文件不存在: {config.script_path}")
            return False
        
        try:
            # 创建服务器参数
            server_params = StdioServerParameters(
                command=sys.executable,
                args=[config.script_path] + (config.args or []),
                cwd=config.cwd
            )
            
            # 使用stdio_client创建连接 - 正确使用异步上下文管理器
            async with stdio_client(server_params) as (read_stream, write_stream):
                # 创建会话
                session = ClientSession(read_stream, write_stream)
                
                # 初始化会话
                await session.initialize()
                
                # 保存会话和流（需要保持连接）
                self.sessions[server_id] = session
                # 注意：这里需要特殊处理，因为退出上下文管理器会关闭流
                # 我们需要保持流开启，所以可能需要不同的方法
            
            return True
            
        except Exception as e:
            logger.error(f"连接stdio服务器失败 {config.name}: {e}")
            return False
    
    async def _connect_http_server(self, server_id: str, config: MCPServerConfig) -> bool:
        """连接HTTP服务器"""
        # 测试连接
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(config.url, headers=config.headers)
                if response.status_code == 200:
                    # 这里应该实现HTTP MCP协议
                    # 目前先简单测试连接
                    return True
                else:
                    logger.error(f"HTTP服务器响应错误: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"连接HTTP服务器失败: {e}")
            return False
    
    async def _fetch_server_capabilities(self, server_id: str):
        """获取服务器能力信息"""
        session = self.sessions.get(server_id)
        if not session:
            return
        
        config = self.servers[server_id]
        
        try:
            # 获取工具列表
            tools_result = await session.list_tools()
            if tools_result and hasattr(tools_result, 'tools'):
                config.tools = [tool.name for tool in tools_result.tools]
            
            # 获取资源列表
            try:
                resources_result = await session.list_resources()
                if resources_result and hasattr(resources_result, 'resources'):
                    config.resources = [resource.name for resource in resources_result.resources]
            except:
                config.resources = []
            
            # 获取提示列表
            try:
                prompts_result = await session.list_prompts()
                if prompts_result and hasattr(prompts_result, 'prompts'):
                    config.prompts = [prompt.name for prompt in prompts_result.prompts]
            except:
                config.prompts = []
            
            logger.info(f"已获取服务器能力: {config.name}")
            
        except Exception as e:
            logger.warning(f"获取服务器能力失败 {config.name}: {e}")
    
    async def disconnect_server(self, server_id: str) -> bool:
        """断开服务器连接"""
        if server_id not in self.servers:
            return False
        
        config = self.servers[server_id]
        
        try:
            # 关闭会话
            if server_id in self.sessions:
                session = self.sessions[server_id]
                # 关闭会话 - ClientSession可能没有disconnect方法
                try:
                    # 尝试关闭会话
                    if hasattr(session, 'close'):
                        await session.close()
                except:
                    pass
                del self.sessions[server_id]
            
            # 终止进程（如果是本地服务器）
            if server_id in self.processes:
                process = self.processes[server_id]
                process.terminate()
                del self.processes[server_id]
            
            config.connected = False
            logger.info(f"已断开服务器: {config.name}")
            return True
            
        except Exception as e:
            logger.error(f"断开服务器失败 {config.name}: {e}")
            return False
    
    async def enable_server(self, server_id: str) -> bool:
        """启用服务器"""
        if server_id not in self.servers:
            return False
        
        self.servers[server_id].enabled = True
        
        # 如果尚未连接，尝试连接
        if not self.servers[server_id].connected:
            return await self.connect_server(server_id)
        
        return True
    
    async def disable_server(self, server_id: str) -> bool:
        """禁用服务器"""
        if server_id not in self.servers:
            return False
        
        self.servers[server_id].enabled = False
        
        # 断开连接
        if self.servers[server_id].connected:
            await self.disconnect_server(server_id)
        
        return True
    
    def get_enabled_servers(self) -> List[str]:
        """获取已启用的服务器列表"""
        return [server_id for server_id, config in self.servers.items() if config.enabled]
    
    def get_connected_servers(self) -> List[str]:
        """获取已连接的服务器列表"""
        return [server_id for server_id, config in self.servers.items() if config.connected]
    
    async def call_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用工具"""
        if server_id not in self.sessions:
            raise ValueError(f"服务器未连接: {server_id}")
        
        session = self.sessions[server_id]
        
        try:
            result = await session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"调用工具失败 {tool_name}: {e}")
            raise
    
    async def get_resource(self, server_id: str, resource_uri: str) -> Any:
        """获取资源"""
        if server_id not in self.sessions:
            raise ValueError(f"服务器未连接: {server_id}")
        
        session = self.sessions[server_id]
        
        try:
            result = await session.read_resource(resource_uri)
            return result
        except Exception as e:
            logger.error(f"获取资源失败 {resource_uri}: {e}")
            raise
    
    async def get_prompt(self, server_id: str, prompt_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """获取提示"""
        if server_id not in self.sessions:
            raise ValueError(f"服务器未连接: {server_id}")
        
        session = self.sessions[server_id]
        
        try:
            result = await session.get_prompt(prompt_name, arguments)
            return result
        except Exception as e:
            logger.error(f"获取提示失败 {prompt_name}: {e}")
            raise
    
    async def cleanup(self):
        """清理资源"""
        # 断开所有连接
        for server_id in list(self.sessions.keys()):
            await self.disconnect_server(server_id)
        
        logger.info("MCP管理器已清理")


# 单例实例
mcp_manager = MCPManager() 