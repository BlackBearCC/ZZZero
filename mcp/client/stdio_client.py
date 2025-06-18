"""
标准输入输出MCP客户端实现
"""
import asyncio
import subprocess
from typing import List, Optional
import logging

from .base import MCPClient

logger = logging.getLogger(__name__)


class StdioMCPClient(MCPClient):
    """标准输入输出MCP客户端"""
    
    def __init__(self, 
                 name: str,
                 server_command: str,
                 server_args: Optional[List[str]] = None,
                 version: str = "1.0.0",
                 **kwargs):
        """
        初始化标准输入输出MCP客户端
        
        Args:
            name: 客户端名称
            server_command: 服务器命令
            server_args: 服务器参数
            version: 客户端版本
            **kwargs: 其他配置参数
        """
        super().__init__(name, version, **kwargs)
        self.server_command = server_command
        self.server_args = server_args or []
        self._process = None
        self._read_task = None
        self._write_lock = asyncio.Lock()
    
    async def connect(self):
        """连接到服务器"""
        if self._connected:
            raise RuntimeError("Client already connected")
        
        try:
            # 启动服务器进程
            self._process = await asyncio.create_subprocess_exec(
                self.server_command,
                *self.server_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            logger.info(f"Started MCP server process: {self.server_command}")
            
            # 启动读取任务
            self._read_task = asyncio.create_task(self._read_messages())
            
            self._connected = True
            await self._on_connected()
            
            # 自动初始化
            await self.initialize()
            
        except Exception as e:
            logger.error(f"Error connecting to server: {e}")
            await self._cleanup()
            raise
    
    async def disconnect(self):
        """断开连接"""
        if not self._connected:
            return
        
        await self._cleanup()
        await self._on_disconnected()
    
    async def _cleanup(self):
        """清理资源"""
        # 取消读取任务
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        
        # 终止进程
        if self._process:
            if self._process.returncode is None:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Process did not terminate gracefully, killing it")
                    self._process.kill()
                    await self._process.wait()
            self._process = None
        
        self._connected = False
    
    async def _send_message(self, message: str):
        """发送消息到服务器"""
        if not self._process or not self._process.stdin:
            raise RuntimeError("Process not available")
        
        async with self._write_lock:
            try:
                self._process.stdin.write((message + '\n').encode('utf-8'))
                await self._process.stdin.drain()
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                raise
    
    async def _read_messages(self):
        """读取服务器消息"""
        try:
            while self._connected and self._process and self._process.returncode is None:
                line = await self._process.stdout.readline()
                
                if not line:
                    # EOF reached
                    break
                
                message = line.decode('utf-8').strip()
                if message:
                    await self.handle_message(message)
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading messages: {e}")
        finally:
            # 连接丢失，触发清理
            if self._connected:
                await self._cleanup()
                await self._on_disconnected()
    
    # === 上下文管理器支持 ===
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.disconnect()


async def create_stdio_client(server_command: str, 
                            server_args: Optional[List[str]] = None,
                            client_name: str = "mcp-client",
                            **kwargs) -> StdioMCPClient:
    """
    创建并连接标准输入输出MCP客户端
    
    Args:
        server_command: 服务器命令
        server_args: 服务器参数
        client_name: 客户端名称
        **kwargs: 其他配置参数
        
    Returns:
        已连接的MCP客户端
    """
    client = StdioMCPClient(client_name, server_command, server_args, **kwargs)
    await client.connect()
    return client 