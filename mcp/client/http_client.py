"""
HTTP MCP客户端实现（占位符）
"""
from .base import MCPClient


class HttpMCPClient(MCPClient):
    """HTTP MCP客户端（待实现）"""
    
    def __init__(self, name: str, server_url: str, **kwargs):
        super().__init__(name, **kwargs)
        self.server_url = server_url
    
    async def connect(self):
        raise NotImplementedError("HTTP client not yet implemented")
    
    async def disconnect(self):
        pass
    
    async def _send_message(self, message: str):
        raise NotImplementedError("HTTP client not yet implemented") 