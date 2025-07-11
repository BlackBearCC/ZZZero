# -*- coding: utf-8 -*-
"""
PostgreSQL数据库管理基类

@author leo
@description 提供PostgreSQL连接、表操作等基础功能，替代SQLite数据库管理器
@classes PostgreSQLManager - PostgreSQL数据库管理器基类
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
    manager = PostgreSQLManager(
        host="localhost",
        database="zzzero",
        user="username",
        password="password"
    )
    result = manager.execute_query("SELECT * FROM users")
@dependencies psycopg2-binary, logging, pathlib, threading
"""

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
import threading

logger = logging.getLogger(__name__)

class PostgreSQLManager:
    """PostgreSQL数据库管理器基类"""
    
    def __init__(self, 
                 host: str = None,
                 port: int = 5432,
                 database: str = None,
                 user: str = None,
                 password: str = None,
                 connection_string: str = None):
        """
        初始化PostgreSQL数据库连接
        
        Args:
            host: 数据库主机地址
            port: 数据库端口
            database: 数据库名称
            user: 用户名
            password: 密码
            connection_string: 完整连接字符串（可选，优先使用）
        """
        if not PSYCOPG2_AVAILABLE:
            logger.warning("psycopg2 未安装，PostgreSQL功能将不可用")
            self.available = False
            return
        
        self.available = True
        # 从环境变量获取默认配置
        self.host = host or os.getenv('POSTGRES_HOST', 'localhost')
        self.port = port or int(os.getenv('POSTGRES_PORT', '5432'))
        self.database = database or os.getenv('POSTGRES_DB', 'zzzero')
        self.user = user or os.getenv('POSTGRES_USER', 'postgres')
        self.password = password or os.getenv('POSTGRES_PASSWORD', 'password')
        
        # 构建连接字符串
        if connection_string:
            self.connection_string = connection_string
        else:
            self.connection_string = (
                f"host={self.host} "
                f"port={self.port} "
                f"dbname={self.database} "
                f"user={self.user} "
                f"password={self.password}"
            )
        
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
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
            logger.info(f"PostgreSQL连接测试成功: {self.host}:{self.port}/{self.database}")
        except Exception as e:
            logger.error(f"PostgreSQL连接测试失败: {e}")
            raise e
    
    def _init_database(self):
        """初始化数据库 - 子类重写此方法来创建特定表"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # 创建扩展（如果需要）
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
                    conn.commit()
            logger.info(f"PostgreSQL数据库初始化完成: {self.database}")
        except Exception as e:
            logger.warning(f"数据库初始化警告: {e}")
    
    def _get_connection(self) -> psycopg2.extensions.connection:
        """获取数据库连接"""
        return psycopg2.connect(self.connection_string)
    
    def execute_query(self, sql: str, params: tuple = (), fetch_all: bool = True) -> Union[List[Dict], Dict, None]:
        """执行查询SQL"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                        cursor.execute(sql, params)
                        
                        if sql.strip().upper().startswith('SELECT'):
                            if fetch_all:
                                return [dict(row) for row in cursor.fetchall()]
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
                    with conn.cursor() as cursor:
                        cursor.executemany(sql, params_list)
                        conn.commit()
                        return cursor.rowcount
                        
            except Exception as e:
                logger.error(f"批量执行失败: {sql} | 错误: {e}")
                raise e
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表结构信息"""
        try:
            sql = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision,
                numeric_scale
            FROM information_schema.columns 
            WHERE table_name = %s
            ORDER BY ordinal_position
            """
            return self.execute_query(sql, (table_name,))
        except Exception as e:
            logger.error(f"获取表结构失败: {table_name} | 错误: {e}")
            return []
    
    def get_all_tables(self) -> List[str]:
        """获取数据库中所有表名"""
        try:
            sql = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
            result = self.execute_query(sql)
            return [row['table_name'] for row in result]
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            return []
    
    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        try:
            sql = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = %s
            )
            """
            result = self.execute_query(sql, (table_name,), fetch_all=False)
            return result['exists'] if result else False
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
            placeholders = ', '.join(['%s' for _ in data])
            values = list(data.values())
            
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) RETURNING id"
            
            with self._lock:
                with self._get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(sql, values)
                        conn.commit()
                        result = cursor.fetchone()
                        return result[0] if result else None
                        
        except Exception as e:
            logger.error(f"插入记录失败: {table_name} | 数据: {data} | 错误: {e}")
            raise e
    
    def update_record(self, table_name: str, data: Dict[str, Any], where_clause: str, where_params: tuple = ()) -> int:
        """更新记录"""
        try:
            set_clause = ', '.join([f"{key} = %s" for key in data.keys()])
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
            schema_sql = f"\\d+ {table_name}"
            
            # 获取数据
            data_sql = f"SELECT * FROM {table_name}"
            data = self.execute_query(data_sql)
            
            # 写入备份文件
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(f"-- 表 {table_name} 备份文件\n")
                f.write(f"-- 生成时间: {datetime.now()}\n\n")
                
                # 写入数据
                if data:
                    columns = list(data[0].keys())
                    for row in data:
                        values = [f"'{v}'" if isinstance(v, str) else str(v) for v in row.values()]
                        f.write(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(values)});\n")
            
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
                'database_host': self.host,
                'database_port': self.port,
                'database_name': self.database,
                'database_user': self.user,
                'tables': {},
                'total_records': 0
            }
            
            # 获取数据库大小
            size_sql = "SELECT pg_size_pretty(pg_database_size(current_database())) as database_size"
            size_result = self.execute_query(size_sql, fetch_all=False)
            if size_result:
                info['database_size'] = size_result['database_size']
            
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
                conn.autocommit = True
                with conn.cursor() as cursor:
                    cursor.execute("VACUUM ANALYZE")
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