"""
MCP协议类型定义
"""
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class MCPMethods:
    """MCP方法常量"""
    # 初始化
    INITIALIZE = "initialize"
    
    # 资源相关
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    
    # 工具相关
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    
    # 提示相关
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    
    # 通知
    NOTIFICATIONS_INITIALIZED = "notifications/initialized"
    NOTIFICATIONS_RESOURCES_LIST_CHANGED = "notifications/resources/list_changed"
    NOTIFICATIONS_TOOLS_LIST_CHANGED = "notifications/tools/list_changed"
    NOTIFICATIONS_PROMPTS_LIST_CHANGED = "notifications/prompts/list_changed"


class ErrorCode(Enum):
    """JSON-RPC错误代码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


# JSON-RPC基础类型
class JSONRPCRequest(BaseModel):
    """JSON-RPC请求"""
    jsonrpc: str = "2.0"
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC响应"""
    jsonrpc: str = "2.0"
    id: Union[str, int]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class JSONRPCNotification(BaseModel):
    """JSON-RPC通知"""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPError(BaseModel):
    """MCP错误"""
    code: int
    message: str
    data: Optional[Any] = None


# 客户端信息
class ClientInfo(BaseModel):
    """客户端信息"""
    name: str
    version: str


# 服务器信息
class ServerInfo(BaseModel):
    """服务器信息"""
    name: str
    version: str


# 能力定义
class ResourcesCapability(BaseModel):
    """资源能力"""
    subscribe: bool = False
    list_changed: bool = False


class ToolsCapability(BaseModel):
    """工具能力"""
    list_changed: bool = False


class PromptsCapability(BaseModel):
    """提示能力"""
    list_changed: bool = False


class ClientCapabilities(BaseModel):
    """客户端能力"""
    experimental: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None


class ServerCapabilities(BaseModel):
    """服务器能力"""
    resources: Optional[ResourcesCapability] = None
    tools: Optional[ToolsCapability] = None
    prompts: Optional[PromptsCapability] = None


# 初始化相关
class InitializeRequest(BaseModel):
    """初始化请求"""
    protocol_version: str
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    client_info: ClientInfo


class InitializeResponse(BaseModel):
    """初始化响应"""
    protocol_version: str
    capabilities: ServerCapabilities
    server_info: ServerInfo


# 资源相关
class Resource(BaseModel):
    """资源定义"""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


class ReadResourceRequest(BaseModel):
    """读取资源请求"""
    uri: str


class TextResourceContents(BaseModel):
    """文本资源内容"""
    type: str = "text"
    text: str
    uri: str
    mime_type: Optional[str] = None


class ReadResourceResponse(BaseModel):
    """读取资源响应"""
    contents: List[Any]


class ListResourcesResponse(BaseModel):
    """列出资源响应"""
    resources: List[Resource]


# 工具相关
class ToolInputSchema(BaseModel):
    """工具输入模式"""
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


class Tool(BaseModel):
    """工具定义"""
    name: str
    description: str
    inputSchema: ToolInputSchema


class CallToolRequest(BaseModel):
    """调用工具请求"""
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolContent(BaseModel):
    """工具内容"""
    type: str
    text: str


class CallToolResponse(BaseModel):
    """调用工具响应"""
    content: List[ToolContent]
    isError: bool = False


class ListToolsResponse(BaseModel):
    """列出工具响应"""
    tools: List[Tool]


# 提示相关
class Prompt(BaseModel):
    """提示定义"""
    name: str
    description: str
    arguments: Optional[Dict[str, Any]] = None


class GetPromptRequest(BaseModel):
    """获取提示请求"""
    name: str
    arguments: Optional[Dict[str, str]] = None


class GetPromptResponse(BaseModel):
    """获取提示响应"""
    messages: List[Any]


class ListPromptsResponse(BaseModel):
    """列出提示响应"""
    prompts: List[Prompt]


# JSON Schema类型（用于向后兼容）
JSONSchema = Dict[str, Any] 