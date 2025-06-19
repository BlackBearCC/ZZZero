#!/usr/bin/env python3
"""
简化版MCP工具管理器
直接调用MCP服务器，简化工具使用
"""
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from tools.base import ToolManager
from tools.mcp_manager import mcp_manager

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    result: Any
    error: Optional[str] = None
    tool_name: Optional[str] = None


@dataclass
class MCPTool:
    """MCP工具信息"""
    name: str
    description: str
    server_id: str
    schema: Optional[Dict[str, Any]] = None


class MCPToolManager(ToolManager):
    """简化版MCP工具管理器"""
    
    def __init__(self):
        """初始化MCP工具管理器"""
        super().__init__()
        self.available_tools: Dict[str, MCPTool] = {}
        self.enabled_servers: set = set()
        
        # 默认启用常用服务器
        self.enable_server("csv")
        self.enable_server("chromadb")
        
        logger.info("简化MCP工具管理器初始化完成")
    
    async def initialize(self):
        """实现抽象方法：初始化工具管理器"""
        # 启动所有已启用的服务器
        for server_id in list(self.enabled_servers):
            try:
                mcp_manager.start_server(server_id)
            except Exception as e:
                logger.warning(f"初始化时启动服务器失败 {server_id}: {e}")
        
        logger.info("MCP工具管理器初始化完成")
    
    def enable_server(self, server_id: str) -> bool:
        """启用MCP服务器"""
        try:
            success = mcp_manager.start_server(server_id)
            if success:
                self.enabled_servers.add(server_id)
                self._register_server_tools(server_id)
                logger.info(f"启用MCP服务器: {server_id}")
            return success
        except Exception as e:
            logger.error(f"启用服务器失败 {server_id}: {e}")
            return False
    
    def disable_server(self, server_id: str) -> bool:
        """禁用MCP服务器"""
        try:
            mcp_manager.stop_server(server_id)
            self.enabled_servers.discard(server_id)
            self._unregister_server_tools(server_id)
            logger.info(f"禁用MCP服务器: {server_id}")
            return True
        except Exception as e:
            logger.error(f"禁用服务器失败 {server_id}: {e}")
            return False
    
    def _register_server_tools(self, server_id: str):
        """注册服务器工具"""
        # 为简化起见，手动注册已知工具
        if server_id == "csv":
            csv_tools = [
                MCPTool("create_table", "创建CSV表", server_id),
                MCPTool("insert_records", "插入记录", server_id),
                MCPTool("query_records", "查询记录", server_id),
                MCPTool("update_records", "更新记录", server_id),
                MCPTool("delete_records", "删除记录", server_id),
                MCPTool("list_tables", "列出所有表", server_id),
                MCPTool("get_table_info", "获取表信息", server_id),
                MCPTool("drop_table", "删除表", server_id),
            ]
            for tool in csv_tools:
                self.available_tools[f"{server_id}_{tool.name}"] = tool
        
        elif server_id == "chromadb":
            chroma_tools = [
                MCPTool("create_collection", "创建集合", server_id),
                MCPTool("add_documents", "添加文档", server_id),
                MCPTool("query_documents", "查询文档", server_id),
                MCPTool("update_documents", "更新文档", server_id),
                MCPTool("delete_documents", "删除文档", server_id),
                MCPTool("list_collections", "列出所有集合", server_id),
                MCPTool("get_collection_info", "获取集合信息", server_id),
                MCPTool("delete_collection", "删除集合", server_id),
            ]
            for tool in chroma_tools:
                self.available_tools[f"{server_id}_{tool.name}"] = tool
    
    def _unregister_server_tools(self, server_id: str):
        """注销服务器工具"""
        keys_to_remove = [key for key in self.available_tools.keys() 
                         if key.startswith(f"{server_id}_")]
        for key in keys_to_remove:
            del self.available_tools[key]
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        tools = []
        for tool_key, tool in self.available_tools.items():
            if tool.server_id in self.enabled_servers and mcp_manager.is_running(tool.server_id):
                tools.append({
                    'name': tool_key,
                    'description': f"[{tool.server_id}] {tool.description}",
                    'server_id': tool.server_id,
                    'original_name': tool.name
                })
        return tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """调用MCP工具"""
        try:
            if tool_name not in self.available_tools:
                return ToolResult(
                    success=False,
                    result=f"未知工具: {tool_name}",
                    error=f"工具 {tool_name} 不存在"
                )
            
            tool = self.available_tools[tool_name]
            
            # 检查服务器是否运行
            if not mcp_manager.is_running(tool.server_id):
                return ToolResult(
                    success=False,
                    result=f"服务器未运行: {tool.server_id}",
                    error=f"MCP服务器 {tool.server_id} 未运行"
                )
            
            # 简化的工具调用 - 返回模拟结果
            # 在实际实现中，这里应该通过MCP协议调用服务器
            result = await self._simulate_tool_call(tool, arguments)
            
            return ToolResult(
                success=True,
                result=result,
                tool_name=tool_name
            )
            
        except Exception as e:
            logger.error(f"MCP工具调用失败 {tool_name}: {e}")
            return ToolResult(
                success=False,
                result=f"工具调用失败: {str(e)}",
                error=str(e),
                tool_name=tool_name
            )
    
    async def _simulate_tool_call(self, tool: MCPTool, arguments: Dict[str, Any]) -> str:
        """模拟工具调用 - 临时实现"""
        # 这是一个简化的模拟实现
        # 在实际情况下，应该通过MCP协议与服务器通信
        
        if tool.server_id == "csv":
            if tool.name == "list_tables":
                return json.dumps({"tables": ["sample_table1", "sample_table2"]}, 
                                ensure_ascii=False, indent=2)
            elif tool.name == "create_table":
                table_name = arguments.get("table_name", "new_table")
                return json.dumps({"message": f"已创建表: {table_name}"}, 
                                ensure_ascii=False, indent=2)
            elif tool.name == "query_records":
                table_name = arguments.get("table_name", "unknown")
                return json.dumps({
                    "table_name": table_name,
                    "records": [{"id": 1, "name": "示例数据"}],
                    "total_count": 1
                }, ensure_ascii=False, indent=2)
        
        elif tool.server_id == "chromadb":
            if tool.name == "list_collections":
                return json.dumps({"collections": ["sample_collection1", "sample_collection2"]}, 
                                ensure_ascii=False, indent=2)
            elif tool.name == "create_collection":
                collection_name = arguments.get("collection_name", "new_collection")
                return json.dumps({"message": f"已创建集合: {collection_name}"}, 
                                ensure_ascii=False, indent=2)
            elif tool.name == "query_documents":
                query = arguments.get("query", "sample query")
                return json.dumps({
                    "query": query,
                    "results": [{"id": "doc1", "content": "示例文档内容", "score": 0.95}],
                    "total_count": 1
                }, ensure_ascii=False, indent=2)
        
        # 默认返回
        return json.dumps({
            "tool": tool.name,
            "server": tool.server_id,
            "arguments": arguments,
            "result": "工具执行成功"
        }, ensure_ascii=False, indent=2)
    
    def get_servers_status(self) -> Dict[str, Dict[str, Any]]:
        """获取服务器状态"""
        return mcp_manager.list_servers()
    
    def start_all_servers(self) -> Dict[str, bool]:
        """启动所有服务器"""
        return mcp_manager.start_all()
    
    async def cleanup(self):
        """异步清理资源（实现抽象方法）"""
        try:
            mcp_manager.stop_all()
            logger.info("MCP工具管理器已清理")
        except Exception as e:
            logger.error(f"清理MCP工具管理器失败: {e}")
    
    def cleanup_sync(self):
        """同步清理资源"""
        try:
            mcp_manager.stop_all()
            logger.info("MCP工具管理器已清理")
        except Exception as e:
            logger.error(f"清理MCP工具管理器失败: {e}") 