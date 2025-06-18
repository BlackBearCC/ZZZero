"""
MCP客户端基类 - 生产级实现
"""
import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime
import logging
from abc import ABC, abstractmethod

from ..types import (
    JSONRPCRequest, JSONRPCResponse, JSONRPCNotification,
    InitializeRequest, InitializeResponse, ClientInfo, ClientCapabilities,
    Resource, Tool, Prompt, ReadResourceRequest, ReadResourceResponse,
    CallToolRequest, CallToolResponse, GetPromptRequest, GetPromptResponse,
    ListResourcesResponse, ListToolsResponse, ListPromptsResponse,
    MCPMethods, ErrorCode, MCPError, TextResourceContents, ToolContent
)

logger = logging.getLogger(__name__)


class ResponseWaiter:
    """响应等待器"""
    
    def __init__(self, request_id: Union[str, int], timeout: float = 30.0):
        self.request_id = request_id
        self.timeout = timeout
        self.future = asyncio.Future()
        self.start_time = time.time()
    
    async def wait(self) -> Any:
        """等待响应"""
        try:
            return await asyncio.wait_for(self.future, timeout=self.timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Request {self.request_id} timed out after {self.timeout}s")
    
    def set_result(self, result: Any):
        """设置结果"""
        if not self.future.done():
            self.future.set_result(result)
    
    def set_exception(self, exception: Exception):
        """设置异常"""
        if not self.future.done():
            self.future.set_exception(exception)
    
    @property
    def is_done(self) -> bool:
        """是否完成"""
        return self.future.done()
    
    @property
    def duration(self) -> float:
        """持续时间"""
        return time.time() - self.start_time


class MCPClient(ABC):
    """MCP客户端基类 - 生产级实现"""
    
    def __init__(self, 
                 name: str, 
                 version: str = "1.0.0",
                 protocol_version: str = "2024-11-05",
                 request_timeout: float = 30.0,
                 max_concurrent_requests: int = 100,
                 enable_metrics: bool = True,
                 auto_reconnect: bool = True,
                 reconnect_delay: float = 1.0):
        """
        初始化MCP客户端
        
        Args:
            name: 客户端名称
            version: 客户端版本
            protocol_version: 协议版本
            request_timeout: 请求超时时间（秒）
            max_concurrent_requests: 最大并发请求数
            enable_metrics: 是否启用指标收集
            auto_reconnect: 是否自动重连
            reconnect_delay: 重连延迟（秒）
        """
        self.name = name
        self.version = version
        self.protocol_version = protocol_version
        self.request_timeout = request_timeout
        self.max_concurrent_requests = max_concurrent_requests
        self.enable_metrics = enable_metrics
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay
        
        # 状态管理
        self._connected = False
        self._initialized = False
        self._server_info = None
        self._server_capabilities = None
        
        # 请求管理
        self._request_id = 0
        self._pending_requests: Dict[Union[str, int], ResponseWaiter] = {}
        self._request_semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # 通知处理器
        self._notification_handlers: Dict[str, Callable] = {}
        
        # 指标收集
        self._metrics = {
            'requests_sent': 0,
            'requests_success': 0,
            'requests_error': 0,
            'notifications_received': 0,
            'avg_response_time': 0.0,
            'connection_count': 0
        } if enable_metrics else None
        
        # 注册默认通知处理器
        self._register_default_handlers()
        
        logger.info(f"Initialized MCP client: {name} v{version}")
    
    def _register_default_handlers(self):
        """注册默认通知处理器"""
        # 可以在这里注册一些默认的通知处理器
        pass
    
    def _get_next_request_id(self) -> int:
        """获取下一个请求ID"""
        self._request_id += 1
        return self._request_id
    
    # === 连接管理 ===
    
    @abstractmethod
    async def connect(self):
        """连接到服务器"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass
    
    @abstractmethod
    async def _send_message(self, message: str):
        """发送消息（子类实现）"""
        pass
    
    # === 消息处理 ===
    
    async def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """发送请求并等待响应"""
        if not self._connected:
            raise RuntimeError("Client not connected")
        
        async with self._request_semaphore:
            request_id = self._get_next_request_id()
            request = JSONRPCRequest(id=request_id, method=method, params=params)
            
            # 创建响应等待器
            waiter = ResponseWaiter(request_id, self.request_timeout)
            self._pending_requests[request_id] = waiter
            
            # 更新指标
            if self._metrics:
                self._metrics['requests_sent'] += 1
            
            try:
                # 发送请求
                await self._send_message(request.model_dump_json(by_alias=True))
                
                # 等待响应
                result = await waiter.wait()
                
                # 更新指标
                if self._metrics:
                    self._metrics['requests_success'] += 1
                    self._update_response_time_metric(waiter.duration)
                
                return result
                
            except Exception as e:
                # 更新指标
                if self._metrics:
                    self._metrics['requests_error'] += 1
                
                logger.error(f"Error sending request {method}: {e}")
                raise
            finally:
                # 清理
                self._pending_requests.pop(request_id, None)
    
    async def send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """发送通知"""
        if not self._connected:
            raise RuntimeError("Client not connected")
        
        notification = JSONRPCNotification(method=method, params=params)
        await self._send_message(notification.model_dump_json(by_alias=True))
    
    async def handle_message(self, message: str):
        """处理收到的消息"""
        try:
            data = json.loads(message)
            
            # 检查是否是有效的JSON-RPC消息
            if "jsonrpc" not in data or data["jsonrpc"] != "2.0":
                logger.error("Invalid JSON-RPC version")
                return
            
            # 处理响应
            if "id" in data:
                await self._handle_response(data)
            
            # 处理通知
            elif "method" in data:
                await self._handle_notification(data)
            
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON message")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _handle_response(self, data: Dict[str, Any]):
        """处理响应"""
        request_id = data.get("id")
        
        if request_id in self._pending_requests:
            waiter = self._pending_requests[request_id]
            
            if "error" in data:
                # 错误响应
                error = data["error"]
                exception = Exception(f"MCP Error {error.get('code')}: {error.get('message')}")
                waiter.set_exception(exception)
            else:
                # 成功响应
                waiter.set_result(data.get("result"))
        else:
            logger.warning(f"Received response for unknown request ID: {request_id}")
    
    async def _handle_notification(self, data: Dict[str, Any]):
        """处理通知"""
        method = data.get("method")
        params = data.get("params", {})
        
        # 更新指标
        if self._metrics:
            self._metrics['notifications_received'] += 1
        
        if method in self._notification_handlers:
            try:
                handler = self._notification_handlers[method]
                await handler(params)
            except Exception as e:
                logger.error(f"Error in notification handler for {method}: {e}")
        else:
            logger.debug(f"No handler for notification: {method}")
    
    def add_notification_handler(self, method: str, handler: Callable):
        """添加通知处理器"""
        self._notification_handlers[method] = handler
        logger.debug(f"Added notification handler for method: {method}")
    
    def remove_notification_handler(self, method: str):
        """移除通知处理器"""
        if method in self._notification_handlers:
            del self._notification_handlers[method]
            logger.debug(f"Removed notification handler for method: {method}")
    
    def _update_response_time_metric(self, duration: float):
        """更新响应时间指标"""
        if not self._metrics:
            return
        
        current_avg = self._metrics['avg_response_time']
        total_requests = self._metrics['requests_success']
        
        # 计算新的平均响应时间
        new_avg = ((current_avg * (total_requests - 1)) + duration) / total_requests
        self._metrics['avg_response_time'] = new_avg
    
    # === 协议方法 ===
    
    async def initialize(self) -> InitializeResponse:
        """初始化连接"""
        if self._initialized:
            raise RuntimeError("Client already initialized")
        
        if not self._connected:
            raise RuntimeError("Client not connected")
        
        request = InitializeRequest(
            protocol_version=self.protocol_version,
            capabilities=ClientCapabilities(),
            client_info=ClientInfo(name=self.name, version=self.version)
        )
        
        result = await self.send_request(MCPMethods.INITIALIZE, request.model_dump(by_alias=True))
        response = InitializeResponse(**result)
        
        # 保存服务器信息
        self._server_info = response.server_info
        self._server_capabilities = response.capabilities
        self._initialized = True
        
        # 发送初始化完成通知
        await self.send_notification(MCPMethods.NOTIFICATIONS_INITIALIZED)
        
        logger.info(f"Initialized connection to server: {response.server_info.name}")
        return response
    
    async def list_resources(self) -> List[Resource]:
        """列出资源"""
        self._check_initialized()
        
        result = await self.send_request(MCPMethods.RESOURCES_LIST)
        response = ListResourcesResponse(**result)
        return response.resources
    
    async def read_resource(self, uri: str) -> List[Union[TextResourceContents, Any]]:
        """读取资源"""
        self._check_initialized()
        
        request = ReadResourceRequest(uri=uri)
        result = await self.send_request(MCPMethods.RESOURCES_READ, request.model_dump(by_alias=True))
        response = ReadResourceResponse(**result)
        return response.contents
    
    async def list_tools(self) -> List[Tool]:
        """列出工具"""
        self._check_initialized()
        
        result = await self.send_request(MCPMethods.TOOLS_LIST)
        response = ListToolsResponse(**result)
        return response.tools
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[ToolContent]:
        """调用工具"""
        self._check_initialized()
        
        request = CallToolRequest(name=name, arguments=arguments)
        result = await self.send_request(MCPMethods.TOOLS_CALL, request.model_dump(by_alias=True))
        response = CallToolResponse(**result)
        return response.content
    
    async def list_prompts(self) -> List[Prompt]:
        """列出提示"""
        self._check_initialized()
        
        result = await self.send_request(MCPMethods.PROMPTS_LIST)
        response = ListPromptsResponse(**result)
        return response.prompts
    
    async def get_prompt(self, name: str, arguments: Optional[Dict[str, str]] = None) -> GetPromptResponse:
        """获取提示"""
        self._check_initialized()
        
        request = GetPromptRequest(name=name, arguments=arguments)
        result = await self.send_request(MCPMethods.PROMPTS_GET, request.model_dump(by_alias=True))
        return GetPromptResponse(**result)
    
    def _check_initialized(self):
        """检查是否已初始化"""
        if not self._initialized:
            raise RuntimeError("Client not initialized")
    
    # === 属性访问 ===
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected
    
    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized
    
    @property
    def server_info(self):
        """服务器信息"""
        return self._server_info
    
    @property
    def server_capabilities(self):
        """服务器能力"""
        return self._server_capabilities
    
    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """获取客户端指标"""
        return self._metrics.copy() if self._metrics else None
    
    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        return {
            'name': self.name,
            'version': self.version,
            'protocol_version': self.protocol_version,
            'connected': self._connected,
            'initialized': self._initialized,
            'server_info': self._server_info.model_dump() if self._server_info else None,
            'server_capabilities': self._server_capabilities.model_dump() if self._server_capabilities else None,
            'pending_requests': len(self._pending_requests),
            'metrics': self.get_metrics()
        }
    
    # === 生命周期管理 ===
    
    async def _cleanup_pending_requests(self):
        """清理待处理的请求"""
        for waiter in self._pending_requests.values():
            if not waiter.is_done:
                waiter.set_exception(Exception("Connection closed"))
        self._pending_requests.clear()
    
    async def _on_connected(self):
        """连接成功回调"""
        if self._metrics:
            self._metrics['connection_count'] += 1
        logger.info(f"Connected to MCP server")
    
    async def _on_disconnected(self):
        """断开连接回调"""
        self._connected = False
        self._initialized = False
        await self._cleanup_pending_requests()
        logger.info(f"Disconnected from MCP server")
    
    # === 上下文管理器支持 ===
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect() 