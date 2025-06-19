#!/usr/bin/env python3
"""
简化版MCP管理器
在应用启动时一次性启动所有MCP服务器，然后保持运行
启用/禁用只控制工具是否暴露给Agent，不影响服务器进程
"""
import os
import sys
import asyncio
import subprocess
import logging
import time
import atexit
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ServerStatus(Enum):
    """服务器状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class MCPServerConfig:
    """MCP服务器配置"""
    name: str
    command: List[str]
    working_dir: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    description: str = ""


class SimpleMCPManager:
    """简化版MCP管理器 - 统一管理所有MCP服务器进程"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """单例模式 - 确保全局唯一实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化MCP管理器"""
        if SimpleMCPManager._initialized:
            return
            
        self.servers: Dict[str, MCPServerConfig] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.status: Dict[str, ServerStatus] = {}
        self.project_root = Path(__file__).parent.parent.parent
        
        # 注册内置服务器
        self._register_builtin_servers()
        
        # 注册退出清理
        atexit.register(self._cleanup_on_exit)
        
        SimpleMCPManager._initialized = True
        logger.info(f"MCP管理器初始化完成 (实例ID: {id(self)})")
    
    def _register_builtin_servers(self):
        """注册内置MCP服务器"""
        python_exe = sys.executable
        
        # CSV CRUD服务器
        csv_server_path = self.project_root / "mcp_servers" / "csv_crud_server.py"
        if csv_server_path.exists():
            self.servers["csv"] = MCPServerConfig(
                name="CSV CRUD服务器",
                command=[python_exe, str(csv_server_path)],
                working_dir=str(self.project_root),
                description="CSV文件数据库CRUD操作服务器"
            )
        
        # ChromaDB服务器
        chroma_server_path = self.project_root / "mcp_servers" / "chromadb_crud_server.py"
        if chroma_server_path.exists():
            self.servers["chromadb"] = MCPServerConfig(
                name="ChromaDB CRUD服务器",
                command=[python_exe, str(chroma_server_path)],
                working_dir=str(self.project_root),
                description="ChromaDB向量数据库操作服务器"
            )
    
    def start_all_servers(self) -> Dict[str, bool]:
        """启动所有MCP服务器 - 应用启动时调用一次"""
        logger.info("开始启动所有MCP服务器...")
        results = {}
        
        for server_id in self.servers:
            try:
                results[server_id] = self._start_server_process(server_id)
            except Exception as e:
                logger.error(f"启动服务器失败 {server_id}: {e}")
                results[server_id] = False
        
        # 记录启动结果
        running_count = sum(results.values())
        total_count = len(results)
        logger.info(f"MCP服务器启动完成：{running_count}/{total_count} 个服务器运行中")
        
        return results
    
    def _start_server_process(self, server_id: str) -> bool:
        """启动单个MCP服务器进程"""
        if server_id not in self.servers:
            logger.error(f"未知服务器: {server_id}")
            return False
        
        # 如果已经在运行，跳过
        if self.is_running(server_id):
            logger.info(f"MCP服务器已在运行: {self.servers[server_id].name}")
            return True
        
        config = self.servers[server_id]
        self.status[server_id] = ServerStatus.STARTING
        
        try:
            logger.info(f"启动MCP服务器: {config.name}")
            
            # 启动进程
            process = subprocess.Popen(
                config.command,
                cwd=config.working_dir,
                env={**os.environ, **(config.env or {})},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=0
            )
            
            # 简短等待确保进程启动
            time.sleep(0.5)
            
            # 检查进程是否还在运行
            if process.poll() is None:
                self.processes[server_id] = process
                self.status[server_id] = ServerStatus.RUNNING
                logger.info(f"✅ MCP服务器启动成功: {config.name} (PID: {process.pid})")
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"❌ MCP服务器启动失败: {config.name}")
                logger.error(f"stdout: {stdout}")
                logger.error(f"stderr: {stderr}")
                self.status[server_id] = ServerStatus.ERROR
                return False
                
        except Exception as e:
            logger.error(f"启动MCP服务器失败 {config.name}: {e}")
            self.status[server_id] = ServerStatus.ERROR
            return False
    
    def is_running(self, server_id: str) -> bool:
        """检查服务器是否运行"""
        if server_id not in self.processes:
            logger.debug(f"进程检查: {server_id} 不在进程字典中")
            return False
        
        process = self.processes[server_id]
        poll_result = process.poll()
        if poll_result is None:
            logger.debug(f"进程检查: {server_id} 正在运行 (PID: {process.pid})")
            return True
        else:
            # 进程已结束，清理状态
            logger.warning(f"进程检查: {server_id} 已结束 (PID: {process.pid}, 退出码: {poll_result})")
            del self.processes[server_id]
            self.status[server_id] = ServerStatus.STOPPED
            return False
    
    def get_server_status(self, server_id: str) -> ServerStatus:
        """获取服务器状态"""
        if server_id not in self.servers:
            return ServerStatus.ERROR
        
        # 更新状态
        if self.is_running(server_id):
            self.status[server_id] = ServerStatus.RUNNING
        elif server_id not in self.status:
            self.status[server_id] = ServerStatus.STOPPED
        
        return self.status.get(server_id, ServerStatus.STOPPED)
    
    def list_servers(self) -> Dict[str, Dict[str, Any]]:
        """列出所有服务器及其状态"""
        result = {}
        for server_id, config in self.servers.items():
            result[server_id] = {
                'name': config.name,
                'description': config.description,
                'status': self.get_server_status(server_id).value,
                'running': self.is_running(server_id)
            }
        return result
    
    def stop_all_servers(self):
        """停止所有服务器 - 应用关闭时调用"""
        logger.info("正在停止所有MCP服务器...")
        for server_id in list(self.processes.keys()):
            self._stop_server_process(server_id)
        logger.info("所有MCP服务器已停止")
    
    def _stop_server_process(self, server_id: str) -> bool:
        """停止单个MCP服务器进程"""
        if server_id in self.processes:
            try:
                process = self.processes[server_id]
                process.terminate()
                
                # 等待进程结束
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                
                del self.processes[server_id]
                self.status[server_id] = ServerStatus.STOPPED
                logger.info(f"MCP服务器已停止: {self.servers[server_id].name}")
                return True
            except Exception as e:
                logger.error(f"停止MCP服务器失败: {e}")
                return False
        return True
    
    def _cleanup_on_exit(self):
        """程序退出时的清理函数"""
        try:
            self.stop_all_servers()
        except:
            pass


# 全局MCP管理器实例
mcp_manager = SimpleMCPManager() 