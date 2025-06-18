"""
MCP服务器基类 - 生产级实现
"""
import asyncio
import json
import uuid
import time
from typing import Dict, List, Any, Optional, Callable, Union, Type
from datetime import datetime
import logging
from abc import ABC, abstractmethod

from ..types import (
    JSONRPCRequest, JSONRPCResponse, JSONRPCNotification,
    InitializeRequest, InitializeResponse, ServerInfo, ServerCapabilities,
    Resource, Tool, Prompt, ReadResourceRequest, ReadResourceResponse,
    CallToolRequest, CallToolResponse, GetPromptRequest, GetPromptResponse,
    ListResourcesResponse, ListToolsResponse, ListPromptsResponse,
    MCPMethods, ErrorCode, MCPError, ResourcesCapability, ToolsCapability, PromptsCapability
)

logger = logging.getLogger(__name__)


class RequestContext:
    """请求上下文"""
    
    def __init__(self, request_id: Union[str, int], method: str, params: Optional[Dict[str, Any]] = None):
        self.request_id = request_id
        self.method = method
        self.params = params or {}
        self.start_time = time.time()
        self.client_info = None
        self.metadata = {}
    
    @property
    def duration(self) -> float:
        """请求持续时间（秒）"""
        return time.time() - self.start_time


class MCPHandler:
    """MCP处理器基类"""
    
    async def handle_request(self, context: RequestContext) -> Any:
        """处理请求"""
        raise NotImplementedError
    
    async def handle_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """处理通知"""
        pass


class MCPServer(ABC):
    """MCP服务器基类 - 生产级实现"""
    
    def __init__(self, 
                 name: str, 
                 version: str = "1.0.0",
                 protocol_version: str = "2024-11-05",
                 max_request_size: int = 1024 * 1024,  # 1MB
                 request_timeout: float = 30.0,
                 enable_metrics: bool = True):
        """
        初始化MCP服务器
        
        Args:
            name: 服务器名称
            version: 服务器版本
            protocol_version: 协议版本
            max_request_size: 最大请求大小（字节）
            request_timeout: 请求超时时间（秒）
            enable_metrics: 是否启用指标收集
        """
        self.name = name
        self.version = version
        self.protocol_version = protocol_version
        self.max_request_size = max_request_size
        self.request_timeout = request_timeout
        self.enable_metrics = enable_metrics
        
        # 状态管理
        self._initialized = False
        self._running = False
        self._client_info = None
        
        # 处理器注册
        self._request_handlers: Dict[str, MCPHandler] = {}
        self._notification_handlers: Dict[str, Callable] = {}
        
        # 注册表
        self._resources: Dict[str, Resource] = {}
        self._tools: Dict[str, Tool] = {}
        self._prompts: Dict[str, Prompt] = {}
        
        # 指标收集
        self._metrics = {
            'requests_total': 0,
            'requests_success': 0,
            'requests_error': 0,
            'avg_response_time': 0.0,
            'active_connections': 0
        } if enable_metrics else None
        
        # 能力配置
        self._capabilities = ServerCapabilities(
            resources=ResourcesCapability(subscribe=True, list_changed=True),
            tools=ToolsCapability(list_changed=True),
            prompts=PromptsCapability(list_changed=True)
        )
        
        # 注册默认处理器
        self._register_default_handlers()
        
        logger.info(f"Initialized MCP server: {name} v{version}")
    
    def _register_default_handlers(self):
        """注册默认处理器"""
        class InitializeHandler(MCPHandler):
            def __init__(self, server):
                self.server = server
            
            async def handle_request(self, context: RequestContext) -> Dict[str, Any]:
                return await self.server._handle_initialize(context)
        
        class ResourceListHandler(MCPHandler):
            def __init__(self, server):
                self.server = server
            
            async def handle_request(self, context: RequestContext) -> Dict[str, Any]:
                return await self.server._handle_list_resources(context)
        
        class ResourceReadHandler(MCPHandler):
            def __init__(self, server):
                self.server = server
            
            async def handle_request(self, context: RequestContext) -> Dict[str, Any]:
                return await self.server._handle_read_resource(context)
        
        class ToolListHandler(MCPHandler):
            def __init__(self, server):
                self.server = server
            
            async def handle_request(self, context: RequestContext) -> Dict[str, Any]:
                return await self.server._handle_list_tools(context)
        
        class ToolCallHandler(MCPHandler):
            def __init__(self, server):
                self.server = server
            
            async def handle_request(self, context: RequestContext) -> Dict[str, Any]:
                return await self.server._handle_call_tool(context)
        
        class PromptListHandler(MCPHandler):
            def __init__(self, server):
                self.server = server
            
            async def handle_request(self, context: RequestContext) -> Dict[str, Any]:
                return await self.server._handle_list_prompts(context)
        
        class PromptGetHandler(MCPHandler):
            def __init__(self, server):
                self.server = server
            
            async def handle_request(self, context: RequestContext) -> Dict[str, Any]:
                return await self.server._handle_get_prompt(context)
        
        # 注册处理器
        self._request_handlers[MCPMethods.INITIALIZE] = InitializeHandler(self)
        self._request_handlers[MCPMethods.RESOURCES_LIST] = ResourceListHandler(self)
        self._request_handlers[MCPMethods.RESOURCES_READ] = ResourceReadHandler(self)
        self._request_handlers[MCPMethods.TOOLS_LIST] = ToolListHandler(self)
        self._request_handlers[MCPMethods.TOOLS_CALL] = ToolCallHandler(self)
        self._request_handlers[MCPMethods.PROMPTS_LIST] = PromptListHandler(self)
        self._request_handlers[MCPMethods.PROMPTS_GET] = PromptGetHandler(self)
    
    # === 处理器注册 ===
    
    def add_request_handler(self, method: str, handler: MCPHandler):
        """添加请求处理器"""
        self._request_handlers[method] = handler
        logger.debug(f"Registered request handler for method: {method}")
    
    def add_notification_handler(self, method: str, handler: Callable):
        """添加通知处理器"""
        self._notification_handlers[method] = handler
        logger.debug(f"Registered notification handler for method: {method}")
    
    def remove_request_handler(self, method: str):
        """移除请求处理器"""
        if method in self._request_handlers:
            del self._request_handlers[method]
            logger.debug(f"Removed request handler for method: {method}")
    
    # === 资源管理 ===
    
    def register_resource(self, resource: Resource):
        """注册资源"""
        self._resources[resource.uri] = resource
        logger.info(f"Registered resource: {resource.name} ({resource.uri})")
    
    def unregister_resource(self, uri: str):
        """取消注册资源"""
        if uri in self._resources:
            resource = self._resources.pop(uri)
            logger.info(f"Unregistered resource: {resource.name} ({uri})")
    
    def get_resource(self, uri: str) -> Optional[Resource]:
        """获取资源"""
        return self._resources.get(uri)
    
    def list_resources(self) -> List[Resource]:
        """列出所有资源"""
        return list(self._resources.values())
    
    # === 工具管理 ===
    
    def register_tool(self, tool: Tool):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def unregister_tool(self, name: str):
        """取消注册工具"""
        if name in self._tools:
            tool = self._tools.pop(name)
            logger.info(f"Unregistered tool: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[Tool]:
        """列出所有工具"""
        return list(self._tools.values())
    
    # === 提示管理 ===
    
    def register_prompt(self, prompt: Prompt):
        """注册提示"""
        self._prompts[prompt.name] = prompt
        logger.info(f"Registered prompt: {prompt.name}")
    
    def unregister_prompt(self, name: str):
        """取消注册提示"""
        if name in self._prompts:
            prompt = self._prompts.pop(name)
            logger.info(f"Unregistered prompt: {prompt.name}")
    
    def get_prompt(self, name: str) -> Optional[Prompt]:
        """获取提示"""
        return self._prompts.get(name)
    
    def list_prompts(self) -> List[Prompt]:
        """列出所有提示"""
        return list(self._prompts.values())
    
    # === 消息处理 ===
    
    async def handle_message(self, message: str) -> Optional[str]:
        """处理消息"""
        if len(message) > self.max_request_size:
            return self._create_error_response(
                None, ErrorCode.INVALID_REQUEST.value, "Request too large"
            )
        
        try:
            data = json.loads(message)
            
            # 验证JSON-RPC格式
            if "jsonrpc" not in data or data["jsonrpc"] != "2.0":
                return self._create_error_response(
                    None, ErrorCode.INVALID_REQUEST.value, "Invalid JSON-RPC version"
                )
            
            # 处理请求
            if "id" in data and "method" in data:
                return await self._handle_request(data)
            
            # 处理通知
            elif "method" in data:
                await self._handle_notification(data)
                return None
            
            else:
                return self._create_error_response(
                    None, ErrorCode.INVALID_REQUEST.value, "Invalid message format"
                )
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return self._create_error_response(
                None, ErrorCode.PARSE_ERROR.value, "Parse error"
            )
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return self._create_error_response(
                None, ErrorCode.INTERNAL_ERROR.value, str(e)
            )
    
    async def _handle_request(self, data: Dict[str, Any]) -> str:
        """处理请求"""
        method = data.get("method")
        request_id = data.get("id")
        params = data.get("params", {})
        
        # 创建请求上下文
        context = RequestContext(request_id, method, params)
        context.client_info = self._client_info
        
        # 更新指标
        if self._metrics:
            self._metrics['requests_total'] += 1
        
        try:
            # 检查方法是否存在
            if method not in self._request_handlers:
                return self._create_error_response(
                    request_id, ErrorCode.METHOD_NOT_FOUND.value, f"Method not found: {method}"
                )
            
            # 检查初始化状态（初始化方法除外）
            if method != MCPMethods.INITIALIZE and not self._initialized:
                return self._create_error_response(
                    request_id, ErrorCode.INVALID_REQUEST.value, "Server not initialized"
                )
            
            # 执行请求处理器
            handler = self._request_handlers[method]
            
            # 添加超时控制
            result = await asyncio.wait_for(
                handler.handle_request(context),
                timeout=self.request_timeout
            )
            
            # 更新指标
            if self._metrics:
                self._metrics['requests_success'] += 1
                self._update_response_time_metric(context.duration)
            
            # 创建响应
            response = JSONRPCResponse(id=request_id, result=result)
            return response.model_dump_json(by_alias=True)
            
        except asyncio.TimeoutError:
            logger.error(f"Request timeout for method: {method}")
            if self._metrics:
                self._metrics['requests_error'] += 1
            return self._create_error_response(
                request_id, ErrorCode.INTERNAL_ERROR.value, "Request timeout"
            )
        except Exception as e:
            logger.error(f"Error in request handler for {method}: {e}")
            if self._metrics:
                self._metrics['requests_error'] += 1
            return self._create_error_response(
                request_id, ErrorCode.INTERNAL_ERROR.value, str(e)
            )
    
    async def _handle_notification(self, data: Dict[str, Any]):
        """处理通知"""
        method = data.get("method")
        params = data.get("params", {})
        
        try:
            if method in self._notification_handlers:
                handler = self._notification_handlers[method]
                await handler(params)
            else:
                logger.debug(f"No handler for notification: {method}")
        except Exception as e:
            logger.error(f"Error in notification handler for {method}: {e}")
    
    def _create_error_response(self, request_id: Any, code: int, message: str) -> str:
        """创建错误响应"""
        error = MCPError(code=code, message=message)
        response = JSONRPCResponse(id=request_id, error=error.model_dump())
        return response.model_dump_json(by_alias=True)
    
    def _update_response_time_metric(self, duration: float):
        """更新响应时间指标"""
        if not self._metrics:
            return
        
        current_avg = self._metrics['avg_response_time']
        total_requests = self._metrics['requests_total']
        
        # 计算新的平均响应时间
        new_avg = ((current_avg * (total_requests - 1)) + duration) / total_requests
        self._metrics['avg_response_time'] = new_avg
    
    # === 默认处理器实现 ===
    
    async def _handle_initialize(self, context: RequestContext) -> Dict[str, Any]:
        """处理初始化请求"""
        try:
            request = InitializeRequest(**context.params)
            
            # 保存客户端信息
            self._client_info = request.client_info
            context.client_info = request.client_info
            
            # 创建响应
            response = InitializeResponse(
                protocol_version=self.protocol_version,
                capabilities=self._capabilities,
                server_info=ServerInfo(name=self.name, version=self.version)
            )
            
            self._initialized = True
            logger.info(f"Server initialized for client: {request.client_info.name}")
            
            # 调用初始化完成回调
            await self._on_initialized(request.client_info)
            
            return response.model_dump(by_alias=True)
            
        except Exception as e:
            raise ValueError(f"Invalid initialize request: {e}")
    
    async def _handle_list_resources(self, context: RequestContext) -> Dict[str, Any]:
        """处理列出资源请求"""
        resources = await self._get_resources(context)
        response = ListResourcesResponse(resources=resources)
        return response.model_dump(by_alias=True)
    
    async def _handle_read_resource(self, context: RequestContext) -> Dict[str, Any]:
        """处理读取资源请求"""
        try:
            request = ReadResourceRequest(**context.params)
            contents = await self._read_resource(request.uri, context)
            response = ReadResourceResponse(contents=contents)
            return response.model_dump(by_alias=True)
        except Exception as e:
            raise ValueError(f"Failed to read resource: {e}")
    
    async def _handle_list_tools(self, context: RequestContext) -> Dict[str, Any]:
        """处理列出工具请求"""
        tools = await self._get_tools(context)
        response = ListToolsResponse(tools=tools)
        return response.model_dump(by_alias=True)
    
    async def _handle_call_tool(self, context: RequestContext) -> Dict[str, Any]:
        """处理调用工具请求"""
        try:
            request = CallToolRequest(**context.params)
            result = await self._call_tool(request.name, request.arguments, context)
            return result
        except Exception as e:
            raise ValueError(f"Failed to call tool: {e}")
    
    async def _handle_list_prompts(self, context: RequestContext) -> Dict[str, Any]:
        """处理列出提示请求"""
        prompts = await self._get_prompts(context)
        response = ListPromptsResponse(prompts=prompts)
        return response.model_dump(by_alias=True)
    
    async def _handle_get_prompt(self, context: RequestContext) -> Dict[str, Any]:
        """处理获取提示请求"""
        try:
            request = GetPromptRequest(**context.params)
            result = await self._get_prompt_messages(request.name, request.arguments, context)
            return result
        except Exception as e:
            raise ValueError(f"Failed to get prompt: {e}")
    
    # === 抽象方法（子类实现） ===
    
    async def _get_resources(self, context: RequestContext) -> List[Resource]:
        """获取资源列表（子类可重写）"""
        return self.list_resources()
    
    async def _read_resource(self, uri: str, context: RequestContext) -> List[Any]:
        """读取资源内容（子类必须实现）"""
        raise NotImplementedError("Subclasses must implement _read_resource")
    
    async def _get_tools(self, context: RequestContext) -> List[Tool]:
        """获取工具列表（子类可重写）"""
        return self.list_tools()
    
    async def _call_tool(self, name: str, arguments: Dict[str, Any], context: RequestContext) -> Dict[str, Any]:
        """调用工具（子类必须实现）"""
        raise NotImplementedError("Subclasses must implement _call_tool")
    
    async def _get_prompts(self, context: RequestContext) -> List[Prompt]:
        """获取提示列表（子类可重写）"""
        return self.list_prompts()
    
    async def _get_prompt_messages(self, name: str, arguments: Optional[Dict[str, str]], context: RequestContext) -> Dict[str, Any]:
        """获取提示消息（子类必须实现）"""
        raise NotImplementedError("Subclasses must implement _get_prompt_messages")
    
    # === 生命周期回调 ===
    
    async def _on_initialized(self, client_info):
        """初始化完成回调"""
        pass
    
    async def _on_shutdown(self):
        """关闭回调"""
        pass
    
    # === 抽象方法 ===
    
    @abstractmethod
    async def start(self):
        """启动服务器"""
        pass
    
    @abstractmethod
    async def stop(self):
        """停止服务器"""
        pass
    
    @abstractmethod
    async def send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """发送通知"""
        pass
    
    # === 指标和状态 ===
    
    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """获取服务器指标"""
        return self._metrics.copy() if self._metrics else None
    
    def get_status(self) -> Dict[str, Any]:
        """获取服务器状态"""
        return {
            'name': self.name,
            'version': self.version,
            'protocol_version': self.protocol_version,
            'initialized': self._initialized,
            'running': self._running,
            'client_info': self._client_info.model_dump() if self._client_info else None,
            'resource_count': len(self._resources),
            'tool_count': len(self._tools),
            'prompt_count': len(self._prompts),
            'metrics': self.get_metrics()
        }
    
    # === 通知发送辅助方法 ===
    
    async def notify_resources_changed(self):
        """通知资源列表变化"""
        await self.send_notification(MCPMethods.NOTIFICATIONS_RESOURCES_LIST_CHANGED)
    
    async def notify_tools_changed(self):
        """通知工具列表变化"""
        await self.send_notification(MCPMethods.NOTIFICATIONS_TOOLS_LIST_CHANGED)
    
    async def notify_prompts_changed(self):
        """通知提示列表变化"""
        await self.send_notification(MCPMethods.NOTIFICATIONS_PROMPTS_LIST_CHANGED) 