#!/usr/bin/env python3
"""
新闻标题和内容分类服务
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

# 添加项目根目录到Python路径，以便导入本地mcp模块
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mcp.server.stdio_server import StdioMCPServer
from mcp.types import Tool, Resource, JSONSchema, ToolInputSchema

logger = logging.getLogger(__name__)



class CSVCRUDServer(StdioMCPServer):
    """新闻标题和内容分类MCP服务器"""
    
    def __init__(self, data_dir: str = "./workspace/output"):
        """
        初始化新闻标题和内容分类服务器
        
        Args:
            data_dir: 数据存储目录，默认输出到workspace/output
        """
        super().__init__(
            name="news_classification_server",
            version="1.0.0"
        )

        self._register_news_classification_tools()
    
    def _register_news_classification_tools(self):
        """注册新闻标题和内容分类工具"""
        
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
    server = CSVCRUDServer("./workspace/output")
    
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