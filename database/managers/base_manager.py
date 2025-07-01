"""
通用数据库管理基类 - 提供SQLite连接、表操作等基础功能
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
import threading

logger = logging.getLogger(__name__)

class DatabaseManager:
    """通用数据库管理器基类"""
    
    def __init__(self, db_path: str = "workspace/databases/main.db"):
        """初始化数据库连接"""
        self.db_path = Path(db_path)
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 线程锁，确保数据库操作的线程安全
        self._lock = threading.Lock()
        
        # 初始化数据库
        self._init_database()
    
    def _init_database(self):
        """初始化数据库 - 子类重写此方法来创建特定表"""
        with self._get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
            conn.execute("PRAGMA journal_mode = WAL")  # 启用WAL模式提高并发性能
            logger.info(f"数据库初始化完成: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def execute_query(self, sql: str, params: tuple = (), fetch_all: bool = True) -> Union[List[Dict], Dict, None]:
        """执行查询SQL"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute(sql, params)
                    
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
                    cursor = conn.executemany(sql, params_list)
                    conn.commit()
                    return cursor.rowcount
                    
            except Exception as e:
                logger.error(f"批量执行失败: {sql} | 错误: {e}")
                raise e
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表结构信息"""
        try:
            sql = f"PRAGMA table_info({table_name})"
            return self.execute_query(sql)
        except Exception as e:
            logger.error(f"获取表结构失败: {table_name} | 错误: {e}")
            return []
    
    def get_all_tables(self) -> List[str]:
        """获取数据库中所有表名"""
        try:
            sql = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
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
                    cursor = conn.execute(sql, values)
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
            
            with self._get_connection() as conn:
                with open(backup_path, 'w', encoding='utf-8') as f:
                    for line in conn.iterdump():
                        if table_name in line:
                            f.write(f"{line}\n")
            
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
            columns = [col['name'] for col in schema]
            
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
                'database_path': str(self.db_path),
                'database_size': self.db_path.stat().st_size if self.db_path.exists() else 0,
                'tables': {},
                'total_records': 0
            }
            
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
            logger.info("数据库清理优化完成")
        except Exception as e:
            logger.error(f"数据库清理失败: {e}")
            raise e 