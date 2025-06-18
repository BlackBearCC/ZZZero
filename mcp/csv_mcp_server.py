"""
CSV MCP 服务器
提供CSV文件查询、筛选、统计等功能的MCP服务
"""

import asyncio
import os
import pandas as pd
from typing import Any, Dict, List, Optional, Union
import json
from pathlib import Path

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl


class CSVMCPServer:
    """CSV MCP服务器类"""
    
    def __init__(self, csv_directory: str = None):
        """
        初始化CSV MCP服务器
        
        Args:
            csv_directory: CSV文件目录路径，默认为当前目录
        """
        self.csv_directory = csv_directory or os.getcwd()
        self.server = Server("csv-query-server")
        self.csv_cache = {}  # 缓存已加载的CSV文件
        
        # 注册工具
        self._register_tools()
        
    def _register_tools(self):
        """注册MCP工具"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[types.Tool]:
            """返回可用的CSV工具列表"""
            return [
                types.Tool(
                    name="csv_list_files",
                    description="列出指定目录中的所有CSV文件",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "description": "要搜索的目录路径（可选，默认为配置的目录）"
                            }
                        }
                    }
                ),
                types.Tool(
                    name="csv_query",
                    description="查询CSV文件数据，支持条件筛选和聚合操作",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "CSV文件路径"
                            },
                            "query": {
                                "type": "string",
                                "description": "查询条件（pandas查询语法）"
                            },
                            "columns": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要选择的列名列表（可选）"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "限制返回的行数（可选）"
                            }
                        },
                        "required": ["file_path"]
                    }
                ),
                types.Tool(
                    name="csv_stats",
                    description="获取CSV文件的统计信息",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "CSV文件路径"
                            },
                            "column": {
                                "type": "string",
                                "description": "要统计的列名（可选，默认统计所有数值列）"
                            }
                        },
                        "required": ["file_path"]
                    }
                ),
                types.Tool(
                    name="csv_schema",
                    description="获取CSV文件的结构信息（列名、数据类型等）",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "CSV文件路径"
                            }
                        },
                        "required": ["file_path"]
                    }
                ),
                types.Tool(
                    name="csv_search",
                    description="在CSV文件中搜索包含特定关键词的行",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "CSV文件路径"
                            },
                            "keyword": {
                                "type": "string",
                                "description": "搜索关键词"
                            },
                            "columns": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要搜索的列名列表（可选，默认搜索所有列）"
                            },
                            "case_sensitive": {
                                "type": "boolean",
                                "description": "是否区分大小写（默认false）"
                            }
                        },
                        "required": ["file_path", "keyword"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            """处理工具调用"""
            try:
                if name == "csv_list_files":
                    return await self._list_csv_files(arguments)
                elif name == "csv_query":
                    return await self._query_csv(arguments)
                elif name == "csv_stats":
                    return await self._get_csv_stats(arguments)
                elif name == "csv_schema":
                    return await self._get_csv_schema(arguments)
                elif name == "csv_search":
                    return await self._search_csv(arguments)
                else:
                    raise ValueError(f"未知工具: {name}")
            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=f"执行工具 {name} 时发生错误: {str(e)}"
                )]
    
    async def _list_csv_files(self, arguments: dict) -> list[types.TextContent]:
        """列出CSV文件"""
        directory = arguments.get("directory", self.csv_directory)
        
        try:
            csv_files = []
            for file_path in Path(directory).rglob("*.csv"):
                file_info = {
                    "name": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime
                }
                csv_files.append(file_info)
            
            result = {
                "directory": directory,
                "total_files": len(csv_files),
                "files": csv_files
            }
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"列出CSV文件时发生错误: {str(e)}"
            )]
    
    async def _query_csv(self, arguments: dict) -> list[types.TextContent]:
        """查询CSV数据"""
        file_path = arguments["file_path"]
        query = arguments.get("query")
        columns = arguments.get("columns")
        limit = arguments.get("limit")
        
        try:
            # 加载CSV文件
            df = await self._load_csv(file_path)
            
            # 应用查询条件
            if query:
                df = df.query(query)
            
            # 选择指定列
            if columns:
                df = df[columns]
            
            # 限制行数
            if limit:
                df = df.head(limit)
            
            # 转换为JSON格式
            result = {
                "file_path": file_path,
                "total_rows": len(df),
                "columns": list(df.columns),
                "data": df.to_dict(orient='records')
            }
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"查询CSV文件时发生错误: {str(e)}"
            )]
    
    async def _get_csv_stats(self, arguments: dict) -> list[types.TextContent]:
        """获取CSV统计信息"""
        file_path = arguments["file_path"]
        column = arguments.get("column")
        
        try:
            df = await self._load_csv(file_path)
            
            if column:
                # 单列统计
                if column not in df.columns:
                    raise ValueError(f"列 '{column}' 不存在")
                
                stats = df[column].describe().to_dict()
                result = {
                    "file_path": file_path,
                    "column": column,
                    "statistics": stats
                }
            else:
                # 全体统计
                stats = df.describe().to_dict()
                # 转换数据类型为字符串以避免序列化问题
                data_types = {col: str(dtype) for col, dtype in df.dtypes.to_dict().items()}
                result = {
                    "file_path": file_path,
                    "total_rows": len(df),
                    "total_columns": len(df.columns),
                    "columns": list(df.columns),
                    "data_types": data_types,
                    "statistics": stats
                }
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"获取统计信息时发生错误: {str(e)}"
            )]
    
    async def _get_csv_schema(self, arguments: dict) -> list[types.TextContent]:
        """获取CSV结构信息"""
        file_path = arguments["file_path"]
        
        try:
            df = await self._load_csv(file_path)
            
            schema_info = []
            for col in df.columns:
                col_info = {
                    "column_name": col,
                    "data_type": str(df[col].dtype),
                    "non_null_count": df[col].count(),
                    "null_count": df[col].isnull().sum(),
                    "unique_count": df[col].nunique()
                }
                
                # 添加示例值
                if not df[col].empty:
                    col_info["sample_values"] = df[col].dropna().head(3).tolist()
                
                schema_info.append(col_info)
            
            result = {
                "file_path": file_path,
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "schema": schema_info
            }
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"获取结构信息时发生错误: {str(e)}"
            )]
    
    async def _search_csv(self, arguments: dict) -> list[types.TextContent]:
        """搜索CSV数据"""
        file_path = arguments["file_path"]
        keyword = arguments["keyword"]
        columns = arguments.get("columns")
        case_sensitive = arguments.get("case_sensitive", False)
        
        try:
            df = await self._load_csv(file_path)
            
            # 确定搜索列
            search_columns = columns if columns else df.columns.tolist()
            
            # 执行搜索
            mask = pd.Series([False] * len(df))
            for col in search_columns:
                if col in df.columns:
                    if case_sensitive:
                        mask |= df[col].astype(str).str.contains(keyword, na=False)
                    else:
                        mask |= df[col].astype(str).str.contains(keyword, case=False, na=False)
            
            result_df = df[mask]
            
            result = {
                "file_path": file_path,
                "keyword": keyword,
                "search_columns": search_columns,
                "total_matches": len(result_df),
                "matches": result_df.to_dict(orient='records')
            }
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, indent=2)
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"搜索CSV文件时发生错误: {str(e)}"
            )]
    
    async def _load_csv(self, file_path: str) -> pd.DataFrame:
        """加载CSV文件，使用缓存提高性能"""
        # 解析文件路径
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.csv_directory, file_path)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV文件不存在: {file_path}")
        
        # 检查缓存
        file_stat = os.stat(file_path)
        cache_key = f"{file_path}_{file_stat.st_mtime}"
        
        if cache_key not in self.csv_cache:
            # 加载CSV文件
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                # 尝试其他编码
                df = pd.read_csv(file_path, encoding='gbk')
            
            self.csv_cache[cache_key] = df
            
            # 清理旧缓存
            if len(self.csv_cache) > 10:  # 最多缓存10个文件
                oldest_key = min(self.csv_cache.keys(), key=lambda k: k.split('_')[-1])
                del self.csv_cache[oldest_key]
        
        return self.csv_cache[cache_key].copy()
    
    async def run_server(self):
        """运行MCP服务器"""
        from mcp.server.models import InitializationOptions
        
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            init_options = InitializationOptions(
                server_name="csv-query-server",
                server_version="0.1.0",
                capabilities=self.server.get_capabilities(
                    notification_options=NotificationOptions(
                        prompts_changed=True,
                        resources_changed=True,
                        tools_changed=True,
                    ),
                    experimental_capabilities={},
                ),
            )
            
            await self.server.run(
                read_stream,
                write_stream,
                init_options,
            )


if __name__ == "__main__":
    # 创建并运行CSV MCP服务器
    csv_server = CSVMCPServer()
    asyncio.run(csv_server.run_server()) 