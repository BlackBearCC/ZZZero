"""
简单的CSV MCP服务器
独立运行，不依赖复杂架构
"""

import asyncio
import json
import os
import sys
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional


class SimpleCSVServer:
    """简单的CSV服务器"""
    
    def __init__(self, csv_directory: str = None):
        self.csv_directory = csv_directory or os.getcwd()
        self.csv_cache = {}
        
    async def handle_request(self, request: dict) -> dict:
        """处理请求"""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")
        
        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocol_version": "2024-11-05",
                        "capabilities": {
                            "tools": {"list_changed": True}
                        },
                        "server_info": {
                            "name": "simple-csv-server",
                            "version": "0.1.0"
                        }
                    }
                }
            
            elif method == "tools/list":
                tools = [
                    {
                        "name": "csv_list_files",
                        "description": "列出CSV文件",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "directory": {
                                    "type": "string",
                                    "description": "目录路径"
                                }
                            }
                        }
                    },
                    {
                        "name": "csv_query",
                        "description": "查询CSV数据",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "CSV文件路径"
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "限制行数"
                                }
                            },
                            "required": ["file_path"]
                        }
                    }
                ]
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": tools}
                }
            
            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})
                
                if name == "csv_list_files":
                    result = await self._list_csv_files(arguments)
                elif name == "csv_query":
                    result = await self._query_csv(arguments)
                else:
                    raise ValueError(f"未知工具: {name}")
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": result}]}
                }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"未知方法: {method}"
                    }
                }
                
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"内部错误: {str(e)}"
                }
            }
    
    async def _list_csv_files(self, arguments: dict) -> str:
        """列出CSV文件"""
        directory = arguments.get("directory", self.csv_directory)
        
        try:
            csv_files = []
            for file_path in Path(directory).rglob("*.csv"):
                csv_files.append({
                    "name": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size
                })
            
            result = {
                "directory": directory,
                "total_files": len(csv_files),
                "files": csv_files
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"列出CSV文件时发生错误: {str(e)}"
    
    async def _query_csv(self, arguments: dict) -> str:
        """查询CSV数据"""
        file_path = arguments["file_path"]
        limit = arguments.get("limit", 10)
        
        try:
            # 解析文件路径
            if not os.path.isabs(file_path):
                file_path = os.path.join(self.csv_directory, file_path)
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return f"CSV文件不存在: {file_path}"
            
            # 加载CSV文件
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='gbk')
            
            # 限制行数
            df = df.head(limit)
            
            result = {
                "file_path": file_path,
                "total_rows": len(df),
                "columns": list(df.columns),
                "data": df.to_dict(orient='records')
            }
            
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"查询CSV文件时发生错误: {str(e)}"
    
    async def run(self):
        """运行服务器"""
        print("启动简单CSV MCP服务器...")
        print("使用STDIO协议...")
        
        while True:
            try:
                # 从stdin读取请求
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                
                if not line:
                    break
                
                # 解析JSON请求
                try:
                    request = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
                
                # 处理请求
                response = await self.handle_request(request)
                
                # 发送响应
                print(json.dumps(response), flush=True)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"处理请求时发生错误: {e}", file=sys.stderr)


async def main():
    """主函数"""
    server = SimpleCSVServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main()) 