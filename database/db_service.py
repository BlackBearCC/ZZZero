# -*- coding: utf-8 -*-
"""
数据库服务管理模块

@author leo
@description 管理SQLite数据库服务的启动、停止和健康检查
@classes DatabaseService - 数据库服务管理器
@functions 
    - start_database - 启动SQLite数据库服务
    - stop_database - 停止数据库服务
    - is_database_running - 检查数据库是否运行
    - wait_for_database - 等待数据库就绪
    - get_database_status - 获取数据库状态
@example 
    db_service = DatabaseService()
    await db_service.start_database()
    if await db_service.wait_for_database():
        print("数据库已就绪")
@dependencies sqlite3, asyncio, pathlib
"""

import asyncio
import logging
import os
import time
import sqlite3
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabaseService:
    """数据库服务管理器"""
    
    def __init__(self, db_path: str = None):
        """
        初始化数据库服务管理器
        
        Args:
            db_path: SQLite数据库文件路径
        """
        # 数据库连接配置
        self.db_path = db_path or os.getenv('SQLITE_DB_PATH', './workspace/database/zzzero.db')
        
        # 确保数据库目录存在
        self.db_dir = Path(self.db_path).parent
        self.db_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_wait_time = 60  # 最大等待时间（秒）
        self.check_interval = 2   # 检查间隔（秒）
    
    async def start_database(self) -> bool:
        """启动SQLite数据库服务"""
        try:
            logger.info("初始化SQLite数据库服务...")
            
            # SQLite不需要单独启动服务，只需要确保文件可以访问
            if await self._test_database_connection():
                logger.info("SQLite数据库服务已就绪")
                return True
            else:
                logger.error("无法访问SQLite数据库文件")
                return False
                
        except Exception as e:
            logger.error(f"启动数据库服务异常: {e}")
            return False
    
    async def stop_database(self) -> bool:
        """停止数据库服务"""
        try:
            logger.info("SQLite数据库无需停止服务")
            return True
            
        except Exception as e:
            logger.error(f"停止数据库服务异常: {e}")
            return False
    
    async def is_database_running(self) -> bool:
        """检查数据库是否运行"""
        try:
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
                'database_path': self.db_path,
                'database_exists': False,
                'database_size': None,
                'connection_info': None,
                'error': None
            }
            
            # 检查数据库文件是否存在
            status['database_exists'] = Path(self.db_path).exists()
            
            # 获取数据库文件大小
            if status['database_exists']:
                try:
                    file_size = os.path.getsize(self.db_path)
                    status['database_size'] = f"{file_size / 1024 / 1024:.2f} MB"
                except:
                    status['database_size'] = "未知"
            
            # 检查数据库连接
            status['connected'] = await self._test_database_connection()
            status['running'] = status['connected']
            
            if status['connected']:
                status['connection_info'] = {
                    'database_path': self.db_path,
                    'database_type': 'SQLite'
                }
            
            return status
            
        except Exception as e:
            logger.error(f"获取数据库状态异常: {e}")
            return {
                'running': False,
                'connected': False,
                'database_path': self.db_path,
                'database_exists': False,
                'database_size': None,
                'connection_info': None,
                'error': str(e)
            }
    
    async def _test_database_connection(self) -> bool:
        """测试数据库连接"""
        try:
            # 使用异步方式测试连接，避免阻塞
            loop = asyncio.get_event_loop()
            
            def test_sync_connection():
                try:
                    conn = sqlite3.connect(
                        self.db_path,
                        timeout=5
                    )
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
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
        return f"sqlite:///{self.db_path}"
    
    def get_connection_dict(self) -> Dict[str, Any]:
        """获取数据库连接配置字典"""
        return {
            'database_path': self.db_path,
            'database_type': 'SQLite'
        }

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