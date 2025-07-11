# -*- coding: utf-8 -*-
"""
数据库服务管理模块

@author leo
@description 管理PostgreSQL数据库服务的启动、停止和健康检查
@classes DatabaseService - 数据库服务管理器
@functions 
    - start_database - 启动PostgreSQL数据库服务
    - stop_database - 停止数据库服务
    - is_database_running - 检查数据库是否运行
    - wait_for_database - 等待数据库就绪
    - get_database_status - 获取数据库状态
@example 
    db_service = DatabaseService()
    await db_service.start_database()
    if await db_service.wait_for_database():
        print("数据库已就绪")
@dependencies docker, asyncio, psycopg2, subprocess
"""

import asyncio
import subprocess
import logging
import os
import time
import psycopg2
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabaseService:
    """数据库服务管理器"""
    
    def __init__(self, 
                 compose_file: str = "docker-compose.yml",
                 service_name: str = "postgres"):
        """
        初始化数据库服务管理器
        
        Args:
            compose_file: Docker Compose文件路径
            service_name: 数据库服务名称
        """
        self.compose_file = Path(compose_file)
        self.service_name = service_name
        
        # 数据库连接配置
        self.db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', '5432')),
            'database': os.getenv('POSTGRES_DB', 'zzzero'),
            'user': os.getenv('POSTGRES_USER', 'zzzero_user'),
            'password': os.getenv('POSTGRES_PASSWORD', 'zzzero_pass')
        }
        
        self.max_wait_time = 60  # 最大等待时间（秒）
        self.check_interval = 2   # 检查间隔（秒）
    
    async def start_database(self) -> bool:
        """启动PostgreSQL数据库服务"""
        try:
            logger.info("启动PostgreSQL数据库服务...")
            
            # 检查Docker和docker-compose是否可用
            if not await self._check_docker_available():
                logger.warning("Docker或docker-compose不可用，尝试连接现有数据库...")
                # 如果Docker不可用，尝试连接现有的PostgreSQL实例
                if await self._test_database_connection():
                    logger.info("连接到现有PostgreSQL实例成功")
                    return True
                else:
                    logger.error("无法连接到PostgreSQL数据库，请确保PostgreSQL服务运行在 localhost:5432")
                    return False
            
            # 检查compose文件是否存在
            if not self.compose_file.exists():
                logger.error(f"Docker Compose文件不存在: {self.compose_file}")
                return False
            
            # 启动数据库服务
            cmd = f"docker-compose -f {self.compose_file} up -d {self.service_name}"
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"启动数据库服务失败: {stderr.decode()}")
                return False
            
            logger.info(f"数据库服务启动命令执行成功: {stdout.decode()}")
            
            # 等待数据库就绪
            if await self.wait_for_database():
                logger.info("PostgreSQL数据库服务启动成功并已就绪")
                return True
            else:
                logger.error("数据库服务启动超时")
                return False
                
        except Exception as e:
            logger.error(f"启动数据库服务异常: {e}")
            return False
    
    async def stop_database(self) -> bool:
        """停止数据库服务"""
        try:
            logger.info("停止PostgreSQL数据库服务...")
            
            cmd = f"docker-compose -f {self.compose_file} stop {self.service_name}"
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"停止数据库服务失败: {stderr.decode()}")
                return False
            
            logger.info("PostgreSQL数据库服务已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止数据库服务异常: {e}")
            return False
    
    async def is_database_running(self) -> bool:
        """检查数据库是否运行"""
        try:
            # 检查Docker容器状态
            cmd = f"docker-compose -f {self.compose_file} ps -q {self.service_name}"
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0 or not stdout.strip():
                return False
            
            # 检查数据库连接
            return await self._test_database_connection()
            
        except Exception as e:
            logger.error(f"检查数据库状态异常: {e}")
            return False
    
    async def wait_for_database(self, max_wait: Optional[int] = None) -> bool:
        """等待数据库就绪"""
        max_wait = max_wait or self.max_wait_time
        start_time = time.time()
        
        logger.info(f"等待数据库就绪，最大等待时间: {max_wait}秒")
        
        while time.time() - start_time < max_wait:
            if await self._test_database_connection():
                elapsed = time.time() - start_time
                logger.info(f"数据库已就绪，耗时: {elapsed:.2f}秒")
                return True
            
            logger.debug(f"数据库尚未就绪，继续等待... ({time.time() - start_time:.1f}s)")
            await asyncio.sleep(self.check_interval)
        
        logger.error(f"等待数据库就绪超时 ({max_wait}秒)")
        return False
    
    async def get_database_status(self) -> Dict[str, Any]:
        """获取数据库状态信息"""
        try:
            status = {
                'running': False,
                'connected': False,
                'container_status': 'unknown',
                'connection_info': None,
                'error': None
            }
            
            # 检查容器状态
            cmd = f"docker-compose -f {self.compose_file} ps {self.service_name}"
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and stdout:
                container_info = stdout.decode().strip()
                if "Up" in container_info:
                    status['running'] = True
                    status['container_status'] = 'running'
                elif "Exit" in container_info:
                    status['container_status'] = 'stopped'
                else:
                    status['container_status'] = 'unknown'
            
            # 检查数据库连接
            status['connected'] = await self._test_database_connection()
            
            if status['connected']:
                status['connection_info'] = {
                    'host': self.db_config['host'],
                    'port': self.db_config['port'],
                    'database': self.db_config['database'],
                    'user': self.db_config['user']
                }
            
            return status
            
        except Exception as e:
            logger.error(f"获取数据库状态异常: {e}")
            return {
                'running': False,
                'connected': False,
                'container_status': 'error',
                'connection_info': None,
                'error': str(e)
            }
    
    async def _check_docker_available(self) -> bool:
        """检查Docker和docker-compose是否可用"""
        try:
            # 检查docker
            process = await asyncio.create_subprocess_shell(
                "docker --version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            if process.returncode != 0:
                logger.error("Docker不可用")
                return False
            
            # 检查docker-compose
            process = await asyncio.create_subprocess_shell(
                "docker-compose --version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            if process.returncode != 0:
                logger.error("docker-compose不可用")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"检查Docker可用性异常: {e}")
            return False
    
    async def _test_database_connection(self) -> bool:
        """测试数据库连接"""
        try:
            # 使用异步方式测试连接，避免阻塞
            loop = asyncio.get_event_loop()
            
            def test_sync_connection():
                try:
                    conn = psycopg2.connect(
                        host=self.db_config['host'],
                        port=self.db_config['port'],
                        database=self.db_config['database'],
                        user=self.db_config['user'],
                        password=self.db_config['password'],
                        connect_timeout=5
                    )
                    conn.close()
                    return True
                except:
                    return False
            
            # 在线程池中执行同步连接测试
            result = await loop.run_in_executor(None, test_sync_connection)
            return result
            
        except Exception as e:
            logger.debug(f"数据库连接测试失败: {e}")
            return False
    
    def get_connection_string(self) -> str:
        """获取数据库连接字符串"""
        return (
            f"postgresql://{self.db_config['user']}:{self.db_config['password']}"
            f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
        )
    
    def get_connection_dict(self) -> Dict[str, Any]:
        """获取数据库连接配置字典"""
        return self.db_config.copy()

# 全局数据库服务实例
_db_service = None

def get_database_service() -> DatabaseService:
    """获取全局数据库服务实例"""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service

async def ensure_database_running() -> bool:
    """确保数据库服务运行"""
    db_service = get_database_service()
    
    # 检查是否已经运行
    if await db_service.is_database_running():
        logger.info("数据库服务已在运行")
        return True
    
    # 启动数据库服务
    return await db_service.start_database()