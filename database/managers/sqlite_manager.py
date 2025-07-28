# -*- coding: utf-8 -*-
"""
SQLite数据库管理基类

@author leo
@description 提供SQLite连接、表操作等基础功能，替代PostgreSQL数据库管理器
@classes SQLiteManager - SQLite数据库管理器基类
@functions 
    - __init__ - 初始化数据库连接
    - _get_connection - 获取数据库连接
    - execute_query - 执行查询SQL
    - execute_many - 批量执行SQL
    - get_table_schema - 获取表结构信息
    - get_all_tables - 获取数据库中所有表名
    - table_exists - 检查表是否存在
    - create_table_if_not_exists - 创建表（如果不存在）
    - insert_record - 插入单条记录
    - update_record - 更新记录
    - delete_record - 删除记录
    - get_record_count - 获取记录数量
    - backup_table - 备份表数据
    - export_table_to_csv - 导出表数据到CSV文件
    - get_database_info - 获取数据库信息
@example 
    manager = SQLiteManager(db_path="./database/zzzero.db")
    result = manager.execute_query("SELECT * FROM users")
@dependencies sqlite3, logging, pathlib, threading
"""

import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
import threading

logger = logging.getLogger(__name__)

class SQLiteManager:
    """SQLite数据库管理器基类"""
    
    def __init__(self, 
                 db_path: str = None,
                 timeout: int = 30,
                 check_same_thread: bool = False):
        """
        初始化SQLite数据库连接
        
        Args:
            db_path: 数据库文件路径
            timeout: 连接超时时间（秒）
            check_same_thread: 是否检查同一线程
        """
        # 从环境变量获取默认配置
        self.db_path = db_path or os.getenv('SQLITE_DB_PATH', './workspace/database/zzzero.db')
        self.timeout = timeout or int(os.getenv('SQLITE_TIMEOUT', '30'))
        self.check_same_thread = check_same_thread or os.getenv('SQLITE_CHECK_SAME_THREAD', 'false').lower() == 'true'
        
        # 确保数据库目录存在
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
        # 线程锁，确保数据库操作的线程安全
        self._lock = threading.Lock()
        
        # 测试连接
        self._test_connection()
        
        # 初始化数据库
        self._init_database()
    
    def _test_connection(self):
        """测试数据库连接"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
            logger.info(f"SQLite连接测试成功: {self.db_path}")
        except Exception as e:
            logger.error(f"SQLite连接测试失败: {e}")
            raise e
    
    def _init_database(self):
        """初始化数据库 - 子类重写此方法来创建特定表"""
        try:
            with self._get_connection() as conn:
                # 启用外键约束
                conn.execute("PRAGMA foreign_keys = ON")
                # 设置WAL模式提升性能
                conn.execute("PRAGMA journal_mode = WAL")
                conn.commit()
            logger.info(f"SQLite数据库初始化完成: {self.db_path}")
        except Exception as e:
            logger.warning(f"数据库初始化警告: {e}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=self.check_same_thread
        )
        # 设置Row工厂，使查询结果可以像字典一样访问
        conn.row_factory = sqlite3.Row
        return conn
    
    def execute_query(self, sql: str, params: tuple = (), fetch_all: bool = True) -> Union[List[Dict], Dict, None, int]:
        """执行查询SQL"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, params)
                    
                    if sql.strip().upper().startswith('SELECT'):
                        if fetch_all:
                            rows = cursor.fetchall()
                            return [dict(row) for row in rows]
                        else:
                            row = cursor.fetchone()
                            return dict(row) if row else None
                    else:
                        conn.commit()
                        return cursor.rowcount
                        
            except Exception as e:
                logger.error(f"数据库查询失败: {sql} | 参数: {params} | 错误: {e}")
                raise e
    
    def execute_many(self, sql: str, params_list: List[tuple]) -> int:
        """批量执行SQL"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.executemany(sql, params_list)
                    conn.commit()
                    return cursor.rowcount
                    
            except Exception as e:
                logger.error(f"批量执行失败: {sql} | 错误: {e}")
                raise e
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表结构信息"""
        try:
            sql = f"PRAGMA table_info({table_name})"
            result = self.execute_query(sql)
            
            # 转换为类似PostgreSQL的格式
            schema = []
            for row in result:
                schema.append({
                    'column_name': row['name'],
                    'data_type': row['type'],
                    'is_nullable': 'YES' if not row['notnull'] else 'NO',
                    'column_default': row['dflt_value'],
                    'primary_key': bool(row['pk'])
                })
            return schema
        except Exception as e:
            logger.error(f"获取表结构失败: {table_name} | 错误: {e}")
            return []
    
    def get_all_tables(self) -> List[str]:
        """获取数据库中所有表名"""
        try:
            sql = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            result = self.execute_query(sql)
            return [row['name'] for row in result]
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            return []
    
    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        try:
            sql = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
            result = self.execute_query(sql, (table_name,), fetch_all=False)
            return result is not None
        except Exception as e:
            logger.error(f"检查表存在性失败: {table_name} | 错误: {e}")
            return False
    
    def create_table_if_not_exists(self, table_name: str, schema: str):
        """创建表（如果不存在）"""
        try:
            sql = f"CREATE TABLE IF NOT EXISTS {table_name} {schema}"
            self.execute_query(sql)
            logger.info(f"表创建/验证完成: {table_name}")
        except Exception as e:
            logger.error(f"创建表失败: {table_name} | 错误: {e}")
            raise e
    
    def drop_table(self, table_name: str):
        """删除表"""
        try:
            sql = f"DROP TABLE IF EXISTS {table_name}"
            self.execute_query(sql)
            logger.info(f"表删除完成: {table_name}")
        except Exception as e:
            logger.error(f"删除表失败: {table_name} | 错误: {e}")
            raise e
    
    def insert_record(self, table_name: str, data: Dict[str, Any]) -> int:
        """插入单条记录"""
        try:
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            values = list(data.values())
            
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, values)
                    conn.commit()
                    return cursor.lastrowid
                    
        except Exception as e:
            logger.error(f"插入记录失败: {table_name} | 数据: {data} | 错误: {e}")
            raise e
    
    def update_record(self, table_name: str, data: Dict[str, Any], where_clause: str, where_params: tuple = ()) -> int:
        """更新记录"""
        try:
            set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
            values = list(data.values()) + list(where_params)
            
            sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
            return self.execute_query(sql, tuple(values))
            
        except Exception as e:
            logger.error(f"更新记录失败: {table_name} | 数据: {data} | 条件: {where_clause} | 错误: {e}")
            raise e
    
    def delete_record(self, table_name: str, where_clause: str, where_params: tuple = ()) -> int:
        """删除记录"""
        try:
            sql = f"DELETE FROM {table_name} WHERE {where_clause}"
            return self.execute_query(sql, where_params)
            
        except Exception as e:
            logger.error(f"删除记录失败: {table_name} | 条件: {where_clause} | 错误: {e}")
            raise e
    
    def get_record_count(self, table_name: str, where_clause: str = "1=1", where_params: tuple = ()) -> int:
        """获取记录数量"""
        try:
            sql = f"SELECT COUNT(*) as count FROM {table_name} WHERE {where_clause}"
            result = self.execute_query(sql, where_params, fetch_all=False)
            return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"获取记录数量失败: {table_name} | 错误: {e}")
            return 0
    
    def backup_table(self, table_name: str, backup_path: str = None) -> str:
        """备份表数据到SQL文件"""
        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"workspace/backups/{table_name}_backup_{timestamp}.sql"
            
            # 确保备份目录存在
            Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
            
            # 获取表结构
            schema = self.get_table_schema(table_name)
            
            # 获取数据
            data_sql = f"SELECT * FROM {table_name}"
            data = self.execute_query(data_sql)
            
            # 写入备份文件
            newline = '\n'
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(f"-- 表 {table_name} 备份文件{newline}")
                f.write(f"-- 生成时间: {datetime.now()}{newline}{newline}")
                
                # 写入数据
                if data:
                    columns = list(data[0].keys())
                    for row in data:
                        values = []
                        for v in row.values():
                            if v is None:
                                values.append('NULL')
                            elif isinstance(v, str):
                                # 避免在f-string中使用反斜杠
                                escaped_value = v.replace("'", "''")
                                values.append(f"'{escaped_value}'")
                            else:
                                values.append(str(v))
                        f.write(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(values)});{newline}")
            
            logger.info(f"表备份完成: {table_name} -> {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"表备份失败: {table_name} | 错误: {e}")
            raise e
    
    def export_table_to_csv(self, table_name: str, output_path: str = None, where_clause: str = "1=1", where_params: tuple = ()) -> str:
        """导出表数据到CSV文件"""
        try:
            import csv
            
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"workspace/exports/{table_name}_export_{timestamp}.csv"
            
            # 确保导出目录存在
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # 获取表结构
            schema = self.get_table_schema(table_name)
            columns = [col['column_name'] for col in schema]
            
            # 获取数据
            sql = f"SELECT * FROM {table_name} WHERE {where_clause}"
            data = self.execute_query(sql, where_params)
            
            # 写入CSV
            with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"CSV导出完成: {table_name} -> {output_path} | 记录数: {len(data)}")
            return output_path
            
        except Exception as e:
            logger.error(f"CSV导出失败: {table_name} | 错误: {e}")
            raise e
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        try:
            info = {
                'database_path': self.db_path,
                'database_size': None,
                'tables': {},
                'total_records': 0
            }
            
            # 获取数据库大小
            try:
                file_size = os.path.getsize(self.db_path)
                info['database_size'] = f"{file_size / 1024 / 1024:.2f} MB"
            except:
                info['database_size'] = "未知"
            
            # 获取所有表的信息
            tables = self.get_all_tables()
            for table in tables:
                count = self.get_record_count(table)
                info['tables'][table] = {
                    'record_count': count,
                    'schema': self.get_table_schema(table)
                }
                info['total_records'] += count
            
            return info
            
        except Exception as e:
            logger.error(f"获取数据库信息失败: {e}")
            return {}
    
    def vacuum_database(self):
        """清理和优化数据库"""
        try:
            with self._get_connection() as conn:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                conn.commit()
            logger.info("数据库清理优化完成")
        except Exception as e:
            logger.error(f"数据库清理失败: {e}")
            raise e
    
    def create_index(self, table_name: str, column_names: List[str], index_name: str = None):
        """创建索引"""
        try:
            if not index_name:
                index_name = f"idx_{table_name}_{'_'.join(column_names)}"
            
            columns_str = ', '.join(column_names)
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
            self.execute_query(sql)
            logger.info(f"索引创建完成: {index_name} on {table_name}({columns_str})")
        except Exception as e:
            logger.error(f"创建索引失败: {table_name} | 错误: {e}")
            raise e