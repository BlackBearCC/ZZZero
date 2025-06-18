"""
MCP协议标准类型定义
基于Model Context Protocol规范
"""
from typing import Dict, List, Any, Optional, Union, Literal
from pydantic import BaseModel, Field
from enum import Enum


class JSONRPCMessage(BaseModel):
    """JSON-RPC 2.0消息基类"""
    jsonrpc: str = "2.0"


class JSONRPCRequest(JSONRPCMessage):
    """JSON-RPC请求"""
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCResponse(JSONRPCMessage):
    """JSON-RPC响应"""
    id: Union[str, int]
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class JSONRPCNotification(JSONRPCMessage):
    """JSON-RPC通知（无响应）"""
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPError(BaseModel):
    """MCP错误信息"""
    code: int
    message: str
    data: Optional[Any] = None


class ErrorCode(Enum):
    """标准错误码"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


# === 初始化相关 ===

class ClientInfo(BaseModel):
    """客户端信息"""
    name: str
    version: str


class ServerInfo(BaseModel):
    """服务器信息"""
    name: str
    version: str


class Capabilities(BaseModel):
    """能力声明"""
    experimental: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None


class ResourcesCapability(BaseModel):
    """资源能力"""
    subscribe: Optional[bool] = False
    list_changed: Optional[bool] = False


class ToolsCapability(BaseModel):
    """工具能力"""
    list_changed: Optional[bool] = False


class PromptsCapability(BaseModel):
    """提示能力"""
    list_changed: Optional[bool] = False


class ServerCapabilities(Capabilities):
    """服务器能力"""
    resources: Optional[ResourcesCapability] = None
    tools: Optional[ToolsCapability] = None
    prompts: Optional[PromptsCapability] = None


class ClientCapabilities(Capabilities):
    """客户端能力"""
    roots: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None


class InitializeRequest(BaseModel):
    """初始化请求"""
    protocol_version: str
    capabilities: ClientCapabilities
    client_info: ClientInfo


class InitializeResponse(BaseModel):
    """初始化响应"""
    protocol_version: str
    capabilities: ServerCapabilities
    server_info: ServerInfo


# === 资源相关 ===

class Resource(BaseModel):
    """资源定义"""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = Field(None, alias="mimeType")


class ResourceTemplate(BaseModel):
    """资源模板"""
    uri_template: str = Field(alias="uriTemplate")
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = Field(None, alias="mimeType")


class TextResourceContents(BaseModel):
    """文本资源内容"""
    uri: str
    mime_type: Optional[str] = Field(None, alias="mimeType")
    text: str


class BlobResourceContents(BaseModel):
    """二进制资源内容"""
    uri: str
    mime_type: Optional[str] = Field(None, alias="mimeType")
    blob: str  # base64编码


ResourceContents = Union[TextResourceContents, BlobResourceContents]


class ListResourcesResponse(BaseModel):
    """列出资源响应"""
    resources: List[Resource]


class ReadResourceRequest(BaseModel):
    """读取资源请求"""
    uri: str


class ReadResourceResponse(BaseModel):
    """读取资源响应"""
    contents: List[ResourceContents]


# === 工具相关 ===

class ToolInputSchema(BaseModel):
    """工具输入模式"""
    type: str = "object"
    properties: Dict[str, Any]
    required: Optional[List[str]] = None


class Tool(BaseModel):
    """工具定义"""
    name: str
    description: str
    input_schema: ToolInputSchema = Field(alias="inputSchema")


class CallToolRequest(BaseModel):
    """调用工具请求"""
    name: str
    arguments: Dict[str, Any]


class ToolContent(BaseModel):
    """工具内容"""
    type: Literal["text", "image", "resource"] = "text"
    text: Optional[str] = None
    data: Optional[str] = None  # base64 for images
    mime_type: Optional[str] = Field(None, alias="mimeType")


class CallToolResponse(BaseModel):
    """调用工具响应"""
    content: List[ToolContent]
    is_error: Optional[bool] = Field(False, alias="isError")


class ListToolsResponse(BaseModel):
    """列出工具响应"""
    tools: List[Tool]


# === 提示相关 ===

class PromptArgument(BaseModel):
    """提示参数"""
    name: str
    description: Optional[str] = None
    required: Optional[bool] = False


class Prompt(BaseModel):
    """提示定义"""
    name: str
    description: Optional[str] = None
    arguments: Optional[List[PromptArgument]] = None


class PromptMessage(BaseModel):
    """提示消息"""
    role: Literal["user", "assistant", "system"]
    content: Union[str, Dict[str, Any]]


class GetPromptRequest(BaseModel):
    """获取提示请求"""
    name: str
    arguments: Optional[Dict[str, str]] = None


class GetPromptResponse(BaseModel):
    """获取提示响应"""
    description: Optional[str] = None
    messages: List[PromptMessage]


class ListPromptsResponse(BaseModel):
    """列出提示响应"""
    prompts: List[Prompt]


# === Sampling相关 ===

class ModelPreferences(BaseModel):
    """模型偏好"""
    hints: Optional[List[Dict[str, str]]] = None
    cost_priority: Optional[float] = Field(None, alias="costPriority")
    speed_priority: Optional[float] = Field(None, alias="speedPriority")
    intelligence_priority: Optional[float] = Field(None, alias="intelligencePriority")


class SamplingMessage(BaseModel):
    """采样消息"""
    role: Literal["user", "assistant"]
    content: Union[str, Dict[str, Any]]


class CreateMessageRequest(BaseModel):
    """创建消息请求"""
    messages: List[SamplingMessage]
    model_preferences: Optional[ModelPreferences] = Field(None, alias="modelPreferences")
    system_prompt: Optional[str] = Field(None, alias="systemPrompt")
    include_context: Optional[Literal["none", "thisServer", "allServers"]] = Field(None, alias="includeContext")
    temperature: Optional[float] = None
    max_tokens: int = Field(alias="maxTokens")
    stop_sequences: Optional[List[str]] = Field(None, alias="stopSequences")
    metadata: Optional[Dict[str, Any]] = None


class CreateMessageResponse(BaseModel):
    """创建消息响应"""
    model: str
    stop_reason: Optional[str] = Field(None, alias="stopReason")
    role: Literal["user", "assistant"]
    content: Union[str, Dict[str, Any]]


# === 根目录相关 ===

class Root(BaseModel):
    """根目录定义"""
    uri: str
    name: Optional[str] = None


class ListRootsResponse(BaseModel):
    """列出根目录响应"""
    roots: List[Root]


# === 通知相关 ===

class ProgressNotification(BaseModel):
    """进度通知"""
    progress_token: Union[str, int] = Field(alias="progressToken")
    progress: float
    total: Optional[float] = None


class LoggingLevel(Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    ALERT = "alert"
    EMERGENCY = "emergency"


class LoggingNotification(BaseModel):
    """日志通知"""
    level: LoggingLevel
    message: str
    data: Optional[Any] = None


# === 方法名常量 ===

class MCPMethods:
    """MCP方法名常量"""
    # 初始化
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    
    # 资源
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_SUBSCRIBE = "resources/subscribe"
    RESOURCES_UNSUBSCRIBE = "resources/unsubscribe"
    
    # 工具
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    
    # 提示
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    
    # 采样
    SAMPLING_CREATE_MESSAGE = "sampling/createMessage"
    
    # 根目录
    ROOTS_LIST = "roots/list"
    
    # 通知
    NOTIFICATIONS_INITIALIZED = "notifications/initialized"
    NOTIFICATIONS_PROGRESS = "notifications/progress"
    NOTIFICATIONS_MESSAGE = "notifications/message"
    NOTIFICATIONS_RESOURCES_LIST_CHANGED = "notifications/resources/list_changed"
    NOTIFICATIONS_RESOURCES_UPDATED = "notifications/resources/updated"
    NOTIFICATIONS_TOOLS_LIST_CHANGED = "notifications/tools/list_changed"
    NOTIFICATIONS_PROMPTS_LIST_CHANGED = "notifications/prompts/list_changed" 