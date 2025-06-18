"""
MCP (Model Context Protocol) 集成模块
基于标准MCP协议实现，提供生产级的服务端和客户端实现
"""

# 共享类型定义
from .types import *

# 服务端组件
from .server import (
    MCPServer,
    StdioMCPServer,
    create_stdio_server
)

# 客户端组件  
from .client import (
    MCPClient,
    StdioMCPClient,
    MCPTool,
    ToolExecutor,
    create_stdio_client,
    create_tools_system_prompt
)

# 传统组件（向后兼容）
try:
    from .mcp_launcher import MCPLauncher
    from .config import MCPConfig
    _has_legacy = True
except ImportError:
    _has_legacy = False

__all__ = [
    # 服务端组件
    'MCPServer',
    'StdioMCPServer', 
    'create_stdio_server',
    
    # 客户端组件
    'MCPClient',
    'StdioMCPClient',
    'MCPTool',
    'ToolExecutor',
    'create_stdio_client',
    'create_tools_system_prompt',
    
    # 核心类型定义
    'JSONRPCRequest',
    'JSONRPCResponse', 
    'JSONRPCNotification',
    'Resource',
    'Tool',
    'Prompt',
    'MCPMethods',
    'MCPHandler',
    'RequestContext',
    'ResponseWaiter',
    
    # 高级类型
    'InitializeRequest',
    'InitializeResponse',
    'ServerInfo',
    'ClientInfo',
    'ServerCapabilities',
    'ClientCapabilities',
    'ToolContent',
    'ReadResourceRequest',
    'ReadResourceResponse',
    'CallToolRequest',
    'CallToolResponse',
    'GetPromptRequest',
    'GetPromptResponse',
]

# 添加传统组件（如果可用）
if _has_legacy:
    __all__.extend(['MCPLauncher', 'MCPConfig']) 