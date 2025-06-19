#!/usr/bin/env python3
"""
简化版MCP工具管理器
只管理工具的暴露，不管理服务器生命周期
启用/禁用只控制是否向Agent暴露工具描述
"""
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from tools.base import ToolManager
from tools.mcp_manager import mcp_manager
from core.base import BaseTool

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


class MCPBaseTool(BaseTool):
    """MCP工具的BaseTool适配器"""
    
    def __init__(self, mcp_tool: MCPTool, tool_manager: 'MCPToolManager'):
        """
        初始化MCP工具适配器
        
        Args:
            mcp_tool: MCP工具信息
            tool_manager: MCP工具管理器引用
        """
        # 构建参数描述 - 简化版本，实际应该从MCP服务器获取
        parameters = {
            "data": {
                "type": "object",
                "description": "工具执行参数",
                "required": False
            }
        }
        
        super().__init__(
            name=f"{mcp_tool.server_id}_{mcp_tool.name}",
            description=f"[{mcp_tool.server_id}] {mcp_tool.description}",
            parameters=parameters
        )
        
        self.mcp_tool = mcp_tool
        self.tool_manager = tool_manager
    
    async def execute(self, **kwargs) -> Any:
        """执行MCP工具"""
        return await self.tool_manager._simulate_tool_call(self.mcp_tool, kwargs)


class MCPToolManager(ToolManager):
    """简化版MCP工具管理器 - 只管理工具暴露，不管理服务器生命周期"""
    
    def __init__(self):
        """初始化MCP工具管理器"""
        super().__init__()
        # 所有可用的工具定义（不管服务器是否启用）
        self.all_available_tools: Dict[str, MCPTool] = {}
        # 当前启用的服务器ID集合
        self.enabled_servers: set = set()
        
        # 注册所有可用工具
        self._register_all_tools()
        
        # 默认启用常用服务器
        self.set_enabled_servers(["csv", "chromadb"])
        
        logger.info("简化MCP工具管理器初始化完成")
    
    async def initialize(self):
        """实现抽象方法：初始化工具管理器"""
        # MCP服务器应该已经在main.py中启动了，这里只做初始化检查
        servers_status = mcp_manager.list_servers()
        running_count = sum(1 for info in servers_status.values() if info['running'])
        total_count = len(servers_status)
        
        # 添加详细的调试信息
        logger.info(f"MCP工具管理器初始化完成，检测到 {running_count}/{total_count} 个服务器运行中")
        logger.debug(f"访问的MCP管理器实例ID: {id(mcp_manager)}")
        for server_id, info in servers_status.items():
            logger.debug(f"服务器 {server_id}: {info['name']} - 运行状态: {info['running']}")
        
        # 检查进程字典
        logger.debug(f"MCP管理器进程数量: {len(mcp_manager.processes)}")
        for server_id, process in mcp_manager.processes.items():
            poll_result = process.poll()
            logger.debug(f"进程 {server_id}: poll() = {poll_result} (None表示运行中)")
    
    def _register_all_tools(self):
        """注册所有可用的工具定义"""
        # CSV服务器工具
        csv_tools = [
            MCPTool("create_table", "创建CSV表", "csv"),
            MCPTool("insert_records", "插入记录", "csv"),
            MCPTool("query_records", "查询记录", "csv"),
            MCPTool("update_records", "更新记录", "csv"),
            MCPTool("delete_records", "删除记录", "csv"),
            MCPTool("list_tables", "列出所有表", "csv"),
            MCPTool("get_table_info", "获取表信息", "csv"),
            MCPTool("drop_table", "删除表", "csv"),
        ]
        for tool in csv_tools:
            tool_key = f"{tool.server_id}_{tool.name}"
            self.all_available_tools[tool_key] = tool
            # 创建BaseTool适配器并注册到基类
            base_tool = MCPBaseTool(tool, self)
            self.register_tool(base_tool)
        
        # ChromaDB服务器工具
        chroma_tools = [
            MCPTool("create_collection", "创建集合", "chromadb"),
            MCPTool("add_documents", "添加文档", "chromadb"),
            MCPTool("query_documents", "查询文档", "chromadb"),
            MCPTool("update_documents", "更新文档", "chromadb"),
            MCPTool("delete_documents", "删除文档", "chromadb"),
            MCPTool("list_collections", "列出所有集合", "chromadb"),
            MCPTool("get_collection_info", "获取集合信息", "chromadb"),
            MCPTool("delete_collection", "删除集合", "chromadb"),
        ]
        for tool in chroma_tools:
            tool_key = f"{tool.server_id}_{tool.name}"
            self.all_available_tools[tool_key] = tool
            # 创建BaseTool适配器并注册到基类
            base_tool = MCPBaseTool(tool, self)
            self.register_tool(base_tool)
    
    def set_enabled_servers(self, server_ids: List[str]):
        """设置启用的服务器（只影响工具暴露，不影响服务器进程）"""
        self.enabled_servers = set(server_ids)
        self._update_enabled_tools()
        logger.info(f"更新启用的MCP服务器: {server_ids}")
    
    def _update_enabled_tools(self):
        """根据启用的服务器更新可用工具列表"""
        # 清空当前启用工具
        self.enabled_tools.clear()
        
        # 根据启用的服务器添加工具
        for tool_key, tool in self.all_available_tools.items():
            if tool.server_id in self.enabled_servers:
                self.enabled_tools.add(tool_key)
        
        enabled_count = len(self.enabled_tools)
        total_count = len(self.all_available_tools)
        logger.info(f"工具暴露更新：{enabled_count}/{total_count} 个工具可用")
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表（只返回启用服务器且服务器正在运行的工具）"""
        tools = []
        for tool_name in self.enabled_tools:
            if tool_name in self.all_available_tools:
                tool = self.all_available_tools[tool_name]
                # 检查服务器是否运行
                if mcp_manager.is_running(tool.server_id):
                    tools.append({
                        'name': tool_name,
                        'description': f"[{tool.server_id}] {tool.description}",
                        'server_id': tool.server_id,
                        'original_name': tool.name
                    })
                else:
                    logger.warning(f"服务器 {tool.server_id} 未运行，工具 {tool_name} 不可用")
        
        return tools
    
    def get_all_servers_info(self) -> Dict[str, Dict[str, Any]]:
        """获取所有服务器信息（包括工具数量）"""
        servers_info = mcp_manager.list_servers()
        
        # 为每个服务器添加工具数量信息
        for server_id, info in servers_info.items():
            tool_count = len([t for t in self.all_available_tools.values() if t.server_id == server_id])
            enabled_tool_count = len([tool_name for tool_name in self.enabled_tools 
                                    if tool_name in self.all_available_tools and 
                                    self.all_available_tools[tool_name].server_id == server_id])
            
            info.update({
                'total_tools': tool_count,
                'enabled_tools': enabled_tool_count,
                'enabled': server_id in self.enabled_servers
            })
        
        return servers_info
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """调用MCP工具"""
        try:
            if tool_name not in self.enabled_tools:
                return ToolResult(
                    success=False,
                    result=f"工具未启用: {tool_name}",
                    error=f"工具 {tool_name} 未启用或不存在"
                )
            
            if tool_name not in self.all_available_tools:
                return ToolResult(
                    success=False,
                    result=f"工具不存在: {tool_name}",
                    error=f"工具 {tool_name} 不存在"
                )
            
            tool = self.all_available_tools[tool_name]
            
            # 检查服务器是否运行
            if not mcp_manager.is_running(tool.server_id):
                return ToolResult(
                    success=False,
                    result=f"服务器未运行: {tool.server_id}",
                    error=f"MCP服务器 {tool.server_id} 未运行"
                )
            
            # 调用工具
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
        return self.get_all_servers_info()
    
    async def cleanup(self):
        """异步清理资源（实现抽象方法）"""
        # 不再管理服务器生命周期，只清理内部状态
        self.enabled_tools.clear()
        self.enabled_servers.clear()
        self.tools.clear()
        self.all_available_tools.clear()
        logger.info("MCP工具管理器已清理")
    
    def cleanup_sync(self):
        """同步清理资源"""
        # 不再管理服务器生命周期，只清理内部状态
        self.enabled_tools.clear()
        self.enabled_servers.clear()
        self.tools.clear()
        self.all_available_tools.clear()
        logger.info("MCP工具管理器已清理") 