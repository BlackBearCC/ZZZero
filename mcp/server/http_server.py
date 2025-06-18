"""
HTTP MCP服务器实现（占位符）
"""
from .base import MCPServer


class HttpMCPServer(MCPServer):
    """HTTP MCP服务器（待实现）"""
    
    def __init__(self, name: str, host: str = "localhost", port: int = 8000, **kwargs):
        super().__init__(name, **kwargs)
        self.host = host
        self.port = port
    
    async def start(self):
        raise NotImplementedError("HTTP server not yet implemented")
    
    async def stop(self):
        pass
    
    async def send_notification(self, method: str, params=None):
        raise NotImplementedError("HTTP server not yet implemented") 