#!/usr/bin/env python3
"""
高级CSV数据库服务器 - 基于自定义MCP服务基类实现CRUD操作
支持多文件管理、复杂查询、数据验证、事务操作等
"""
import os
import csv
import json
import pandas as pd
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import asyncio
import logging
import chardet

# 导入自定义MCP基类和类型
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from mcp.server.stdio_server import StdioMCPServer
from mcp.types import Tool, Resource, JSONSchema, ToolInputSchema

logger = logging.getLogger(__name__)


class CSVDatabase:
    """CSV数据库管理器 - 提供高级数据操作功能"""
    
    def __init__(self, base_dir: str = "./csv_data"):
        """
        初始化CSV数据库
        
        Args:
            base_dir: CSV文件存储基础目录
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self._cache = {}  # 数据缓存
        self._metadata = {}  # 文件元数据
        
    def _detect_encoding(self, file_path: Path) -> str:
        """检测文件编码"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # 读取前10KB用于检测
                result = chardet.detect(raw_data)
                return result.get('encoding', 'utf-8')
        except Exception:
            return 'utf-8'
    
    def _get_file_path(self, table_name: str) -> Path:
        """获取表文件路径"""
        return self.base_dir / f"{table_name}.csv"
    
    def _load_dataframe(self, table_name: str) -> pd.DataFrame:
        """加载数据框架"""
        file_path = self._get_file_path(table_name)
        if not file_path.exists():
            raise FileNotFoundError(f"表 '{table_name}' 不存在")
        
        # 尝试从缓存获取
        cache_key = f"{table_name}_{file_path.stat().st_mtime}"
        if cache_key in self._cache:
            return self._cache[cache_key].copy()
        
        # 检测编码并加载
        encoding = self._detect_encoding(file_path)
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            self._cache[cache_key] = df.copy()
            return df
        except Exception as e:
            # 尝试其他编码
            for enc in ['utf-8', 'gbk', 'gb2312', 'latin1']:
                try:
                    df = pd.read_csv(file_path, encoding=enc)
                    self._cache[cache_key] = df.copy()
                    return df
                except:
                    continue
            raise ValueError(f"无法读取文件 '{table_name}': {e}")
    
    def _save_dataframe(self, table_name: str, df: pd.DataFrame):
        """保存数据框架"""
        file_path = self._get_file_path(table_name)
        
        # 备份原文件
        if file_path.exists():
            backup_path = file_path.with_suffix('.csv.bak')
            shutil.copy2(file_path, backup_path)
        
        try:
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            # 清除缓存
            self._cache = {k: v for k, v in self._cache.items() if not k.startswith(f"{table_name}_")}
            
            # 更新元数据
            self._metadata[table_name] = {
                'rows': len(df),
                'columns': list(df.columns),
                'last_modified': datetime.now().isoformat(),
                'size_bytes': file_path.stat().st_size
            }
        except Exception as e:
            # 恢复备份
            backup_path = file_path.with_suffix('.csv.bak')
            if backup_path.exists():
                shutil.copy2(backup_path, file_path)
            raise ValueError(f"保存文件失败: {e}")
    
    def create_table(self, table_name: str, columns: List[str], data: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """创建新表"""
        file_path = self._get_file_path(table_name)
        if file_path.exists():
            raise ValueError(f"表 '{table_name}' 已存在")
        
        # 创建空的DataFrame
        df = pd.DataFrame(columns=columns)
        
        # 如果提供了初始数据，添加进去
        if data:
            df = pd.DataFrame(data, columns=columns)
        
        self._save_dataframe(table_name, df)
        
        return {
            'table_name': table_name,
            'columns': columns,
            'rows_created': len(df),
            'created_at': datetime.now().isoformat()
        }
    
    def insert_records(self, table_name: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """插入记录"""
        df = self._load_dataframe(table_name)
        
        # 创建新记录的DataFrame
        new_df = pd.DataFrame(records)
        
        # 确保列匹配
        missing_cols = set(df.columns) - set(new_df.columns)
        for col in missing_cols:
            new_df[col] = None
        
        # 合并数据
        df = pd.concat([df, new_df], ignore_index=True)
        self._save_dataframe(table_name, df)
        
        return {
            'table_name': table_name,
            'records_inserted': len(records),
            'total_records': len(df),
            'inserted_at': datetime.now().isoformat()
        }
    
    def query_records(self, table_name: str, 
                     where: Optional[Dict[str, Any]] = None,
                     columns: Optional[List[str]] = None,
                     limit: Optional[int] = None,
                     offset: int = 0,
                     order_by: Optional[str] = None,
                     ascending: bool = True) -> Dict[str, Any]:
        """查询记录"""
        df = self._load_dataframe(table_name)
        
        # 应用WHERE条件
        if where:
            for column, value in where.items():
                if column not in df.columns:
                    raise ValueError(f"列 '{column}' 不存在")
                
                if isinstance(value, dict):
                    # 支持复杂条件: {"$gt": 100}, {"$lt": 200}, {"$like": "pattern"}
                    for op, val in value.items():
                        if op == '$gt':
                            df = df[df[column] > val]
                        elif op == '$lt':
                            df = df[df[column] < val]
                        elif op == '$gte':
                            df = df[df[column] >= val]
                        elif op == '$lte':
                            df = df[df[column] <= val]
                        elif op == '$like':
                            df = df[df[column].astype(str).str.contains(str(val), na=False)]
                        elif op == '$in':
                            df = df[df[column].isin(val)]
                        elif op == '$ne':
                            df = df[df[column] != val]
                else:
                    df = df[df[column] == value]
        
        # 排序
        if order_by and order_by in df.columns:
            df = df.sort_values(by=order_by, ascending=ascending)
        
        # 选择列
        if columns:
            missing_cols = set(columns) - set(df.columns)
            if missing_cols:
                raise ValueError(f"列不存在: {missing_cols}")
            df = df[columns]
        
        # 分页
        total_count = len(df)
        if offset > 0:
            df = df.iloc[offset:]
        if limit:
            df = df.head(limit)
        
        return {
            'table_name': table_name,
            'records': df.to_dict('records'),
            'total_count': total_count,
            'returned_count': len(df),
            'offset': offset,
            'limit': limit
        }
    
    def update_records(self, table_name: str, 
                      where: Dict[str, Any],
                      updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新记录"""
        df = self._load_dataframe(table_name)
        original_count = len(df)
        
        # 应用WHERE条件找到要更新的行
        mask = pd.Series([True] * len(df))
        for column, value in where.items():
            if column not in df.columns:
                raise ValueError(f"列 '{column}' 不存在")
            mask &= (df[column] == value)
        
        updated_count = mask.sum()
        if updated_count == 0:
            return {
                'table_name': table_name,
                'records_updated': 0,
                'message': '没有找到匹配的记录'
            }
        
        # 应用更新
        for column, value in updates.items():
            if column not in df.columns:
                raise ValueError(f"列 '{column}' 不存在")
            df.loc[mask, column] = value
        
        self._save_dataframe(table_name, df)
        
        return {
            'table_name': table_name,
            'records_updated': updated_count,
            'total_records': len(df),
            'updated_at': datetime.now().isoformat()
        }
    
    def delete_records(self, table_name: str, where: Dict[str, Any]) -> Dict[str, Any]:
        """删除记录"""
        df = self._load_dataframe(table_name)
        original_count = len(df)
        
        # 应用WHERE条件找到要删除的行
        mask = pd.Series([True] * len(df))
        for column, value in where.items():
            if column not in df.columns:
                raise ValueError(f"列 '{column}' 不存在")
            mask &= (df[column] == value)
        
        deleted_count = mask.sum()
        if deleted_count == 0:
            return {
                'table_name': table_name,
                'records_deleted': 0,
                'message': '没有找到匹配的记录'
            }
        
        # 删除匹配的行
        df = df[~mask]
        self._save_dataframe(table_name, df)
        
        return {
            'table_name': table_name,
            'records_deleted': deleted_count,
            'remaining_records': len(df),
            'deleted_at': datetime.now().isoformat()
        }
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取表信息"""
        file_path = self._get_file_path(table_name)
        if not file_path.exists():
            raise FileNotFoundError(f"表 '{table_name}' 不存在")
        
        df = self._load_dataframe(table_name)
        
        # 统计信息
        stats = df.describe(include='all').to_dict()
        
        return {
            'table_name': table_name,
            'file_path': str(file_path),
            'rows': len(df),
            'columns': list(df.columns),
            'column_types': df.dtypes.astype(str).to_dict(),
            'file_size_bytes': file_path.stat().st_size,
            'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            'statistics': stats
        }
    
    def list_tables(self) -> List[Dict[str, Any]]:
        """列出所有表"""
        tables = []
        for csv_file in self.base_dir.glob("*.csv"):
            if csv_file.suffix == '.csv' and not csv_file.name.endswith('.bak'):
                table_name = csv_file.stem
                try:
                    info = self.get_table_info(table_name)
                    tables.append({
                        'table_name': table_name,
                        'rows': info['rows'],
                        'columns_count': len(info['columns']),
                        'file_size_bytes': info['file_size_bytes'],
                        'last_modified': info['last_modified']
                    })
                except Exception as e:
                    tables.append({
                        'table_name': table_name,
                        'error': str(e)
                    })
        return tables
    
    def drop_table(self, table_name: str) -> Dict[str, Any]:
        """删除表"""
        file_path = self._get_file_path(table_name)
        if not file_path.exists():
            raise FileNotFoundError(f"表 '{table_name}' 不存在")
        
        # 备份
        backup_path = file_path.with_suffix('.csv.deleted')
        shutil.copy2(file_path, backup_path)
        
        # 删除文件
        file_path.unlink()
        
        # 清除缓存和元数据
        self._cache = {k: v for k, v in self._cache.items() if not k.startswith(f"{table_name}_")}
        if table_name in self._metadata:
            del self._metadata[table_name]
        
        return {
            'table_name': table_name,
            'dropped_at': datetime.now().isoformat(),
            'backup_path': str(backup_path)
        }


class CSVCRUDServer(StdioMCPServer):
    """高级CSV数据库MCP服务器"""
    
    def __init__(self, data_dir: str = "./csv_data"):
        """
        初始化CSV CRUD服务器
        
        Args:
            data_dir: CSV数据存储目录
        """
        super().__init__(
            name="csv_crud_server",
            version="1.0.0"
        )
        
        self.db = CSVDatabase(data_dir)
        self._register_csv_tools()
    
    def _register_csv_tools(self):
        """注册CSV操作工具"""
        
        # 创建表工具
        create_table_tool = Tool(
            name="create_table",
            description="创建新的CSV表",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "table_name": {"type": "string", "description": "表名"},
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "列名列表"
                    },
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "可选的初始数据"
                    }
                },
                required=["table_name", "columns"]
            )
        )
        self.register_tool(create_table_tool)
        
        # 插入记录工具
        insert_tool = Tool(
            name="insert_records",
            description="向表中插入记录",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "table_name": {"type": "string", "description": "表名"},
                    "records": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "要插入的记录列表"
                    }
                },
                required=["table_name", "records"]
            )
        )
        self.register_tool(insert_tool)
        
        # 查询记录工具
        query_tool = Tool(
            name="query_records",
            description="查询表中的记录",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "table_name": {"type": "string", "description": "表名"},
                    "where": {"type": "object", "description": "查询条件"},
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要返回的列"
                    },
                    "limit": {"type": "integer", "description": "返回记录数限制"},
                    "offset": {"type": "integer", "description": "偏移量"},
                    "order_by": {"type": "string", "description": "排序字段"},
                    "ascending": {"type": "boolean", "description": "是否升序"}
                },
                required=["table_name"]
            )
        )
        self.register_tool(query_tool)
        
        # 更新记录工具
        update_tool = Tool(
            name="update_records",
            description="更新表中的记录",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "table_name": {"type": "string", "description": "表名"},
                    "where": {"type": "object", "description": "更新条件"},
                    "updates": {"type": "object", "description": "更新的字段和值"}
                },
                required=["table_name", "where", "updates"]
            )
        )
        self.register_tool(update_tool)
        
        # 删除记录工具
        delete_tool = Tool(
            name="delete_records",
            description="删除表中的记录",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "table_name": {"type": "string", "description": "表名"},
                    "where": {"type": "object", "description": "删除条件"}
                },
                required=["table_name", "where"]
            )
        )
        self.register_tool(delete_tool)
        
        # 获取表信息工具
        table_info_tool = Tool(
            name="get_table_info",
            description="获取表的详细信息",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "table_name": {"type": "string", "description": "表名"}
                },
                required=["table_name"]
            )
        )
        self.register_tool(table_info_tool)
        
        # 列出所有表工具
        list_tables_tool = Tool(
            name="list_tables",
            description="列出所有可用的表",
            inputSchema=ToolInputSchema(
                type="object",
                properties={}
            )
        )
        self.register_tool(list_tables_tool)
        
        # 删除表工具
        drop_table_tool = Tool(
            name="drop_table",
            description="删除表",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "table_name": {"type": "string", "description": "表名"}
                },
                required=["table_name"]
            )
        )
        self.register_tool(drop_table_tool)
    
    async def _call_tool(self, name: str, arguments: Dict[str, Any], context) -> Dict[str, Any]:
        """处理工具调用"""
        try:
            if name == "create_table":
                result = self.db.create_table(
                    arguments["table_name"],
                    arguments["columns"],
                    arguments.get("data")
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "insert_records":
                result = self.db.insert_records(
                    arguments["table_name"],
                    arguments["records"]
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "query_records":
                result = self.db.query_records(
                    arguments["table_name"],
                    arguments.get("where"),
                    arguments.get("columns"),
                    arguments.get("limit"),
                    arguments.get("offset", 0),
                    arguments.get("order_by"),
                    arguments.get("ascending", True)
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "update_records":
                result = self.db.update_records(
                    arguments["table_name"],
                    arguments["where"],
                    arguments["updates"]
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "delete_records":
                result = self.db.delete_records(
                    arguments["table_name"],
                    arguments["where"]
                )
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "get_table_info":
                result = self.db.get_table_info(arguments["table_name"])
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "list_tables":
                result = self.db.list_tables()
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            elif name == "drop_table":
                result = self.db.drop_table(arguments["table_name"])
                return {"content": [{"type": "text", "text": json.dumps(result, indent=2, ensure_ascii=False)}]}
            
            else:
                raise ValueError(f"未知工具: {name}")
        
        except Exception as e:
            logger.error(f"工具调用失败 {name}: {e}")
            return {
                "content": [{"type": "text", "text": f"错误: {str(e)}"}],
                "isError": True
            }


async def main():
    """启动CSV CRUD服务器"""
    server = CSVCRUDServer("./csv_data")
    
    try:
        logger.info("启动CSV CRUD服务器...")
        await server.start()
    except KeyboardInterrupt:
        logger.info("接收到停止信号")
    except Exception as e:
        logger.error(f"服务器错误: {e}")
    finally:
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())