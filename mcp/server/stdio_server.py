"""
标准输入输出MCP服务器实现
"""
import asyncio
import sys
import os
from typing import Dict, Any, Optional
import logging

from .base import MCPServer
from ..types import JSONRPCNotification

logger = logging.getLogger(__name__)


class StdioMCPServer(MCPServer):
    """标准输入输出MCP服务器"""
    
    def __init__(self, 
                 name: str, 
                 version: str = "1.0.0",
                 **kwargs):
        """
        初始化标准输入输出MCP服务器
        
        Args:
            name: 服务器名称
            version: 服务器版本
            **kwargs: 其他配置参数
        """
        super().__init__(name, version, **kwargs)
        self._read_task = None
        self._is_windows = os.name == 'nt'
    
    async def start(self):
        """启动服务器"""
        if self._running:
            raise RuntimeError("Server is already running")
        
        try:
            self._running = True
            
            # 启动消息读取任务
            if self._is_windows:
                self._read_task = asyncio.create_task(self._read_messages_windows())
            else:
                self._read_task = asyncio.create_task(self._read_messages_unix())
            
            logger.info(f"Started MCP stdio server: {self.name}")
            
            # 等待读取任务完成
            await self._read_task
            
        except Exception as e:
            logger.error(f"Error starting stdio server: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """停止服务器"""
        if not self._running:
            return
        
        self._running = False
        
        # 取消读取任务
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        
        # 调用关闭回调
        await self._on_shutdown()
        
        logger.info(f"Stopped MCP stdio server: {self.name}")
    
    async def _read_messages_windows(self):
        """Windows系统的消息读取"""
        try:
            while self._running:
                # 在Windows上使用线程池来读取stdin
                try:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, sys.stdin.readline
                    )
                    
                    if not line:
                        # EOF reached
                        break
                    
                    message = line.strip()
                    if not message:
                        continue
                    
                    # 处理消息
                    response = await self.handle_message(message)
                    
                    # 发送响应（如果有）
                    if response:
                        await self._write_response(response)
                        
                except Exception as e:
                    logger.error(f"Error reading message: {e}")
                    break
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in Windows message reading: {e}")
        finally:
            if self._running:
                await self.stop()
    
    async def _read_messages_unix(self):
        """Unix系统的消息读取（原来的实现）"""
        try:
            # 设置标准输入输出
            stdin_reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(stdin_reader)
            
            # 获取事件循环
            loop = asyncio.get_event_loop()
            
            # 连接到标准输入
            transport, _ = await loop.connect_read_pipe(
                lambda: protocol, sys.stdin
            )
            
            while self._running:
                # 读取一行
                line = await stdin_reader.readline()
                
                if not line:
                    # EOF reached
                    break
                
                message = line.decode().strip()
                if not message:
                    continue
                
                # 处理消息
                response = await self.handle_message(message)
                
                # 发送响应（如果有）
                if response:
                    await self._write_response(response)
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in Unix message reading: {e}")
        finally:
            if self._running:
                await self.stop()
    
    async def _write_response(self, response: str):
        """写入响应到标准输出"""
        try:
            # 直接写入到stdout
            sys.stdout.write(response + '\n')
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Error writing response: {e}")
    
    async def send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """发送通知到标准输出"""
        try:
            notification = JSONRPCNotification(method=method, params=params)
            message = notification.model_dump_json(by_alias=True)
            await self._write_response(message)
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    # === 上下文管理器支持 ===
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop()


def create_stdio_server(name: str, version: str = "1.0.0", **kwargs) -> StdioMCPServer:
    """创建标准输入输出MCP服务器"""
    return StdioMCPServer(name, version, **kwargs) 