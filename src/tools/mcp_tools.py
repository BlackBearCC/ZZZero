"""
MCP工具管理器 - 集成MCP协议的工具
"""
import asyncio
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

from .base import ToolManager, BaseTool
from ..core.types import ToolConfig

# 使用现有的MCP客户端
sys.path.append('.')  # 添加根目录到路径
try:
    from mcp.client import MCPClient, MCPTool
except ImportError:
    # 如果导入失败，定义简单的占位类
    @dataclass
    class MCPTool:
        name: str
        description: str
        input_schema: Dict[str, Any]
        
    class MCPClient:
        def __init__(self, server_command: str, server_args: List[str] = None):
            self.server_command = server_command
            self.server_args = server_args or []
            self.tools = {}
            
        async def connect(self):
            pass
            
        async def list_tools(self):
            return []
            
        async def call_tool(self, name: str, arguments: Dict[str, Any]):
            return {"error": "MCP client not available"}


logger = logging.getLogger(__name__)


class MCPToolWrapper(BaseTool):
    """MCP工具包装器 - 将MCP工具包装为框架工具"""
    
    def __init__(self, mcp_tool: MCPTool, mcp_client: MCPClient):
        """
        初始化MCP工具包装器
        
        Args:
            mcp_tool: MCP工具定义
            mcp_client: MCP客户端实例
        """
        # 解析参数定义
        parameters = self._parse_mcp_schema(mcp_tool.input_schema)
        
        super().__init__(
            name=mcp_tool.name,
            description=mcp_tool.description,
            parameters=parameters
        )
        self.mcp_tool = mcp_tool
        self.mcp_client = mcp_client
        
    def _parse_mcp_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """解析MCP工具模式为框架参数格式"""
        parameters = {}
        
        if "properties" in schema:
            for param_name, param_info in schema["properties"].items():
                parameters[param_name] = {
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                    "required": param_name in schema.get("required", []),
                    "default": param_info.get("default")
                }
                
        return parameters
        
    async def execute(self, **kwargs) -> Any:
        """执行MCP工具"""
        try:
            result = await self.mcp_client.call_tool(self.name, kwargs)
            
            # 处理MCP响应
            if isinstance(result, dict):
                if result.get("success", True):
                    return result.get("result", result)
                else:
                    raise Exception(result.get("error", "Unknown error"))
            
            return result
            
        except Exception as e:
            logger.error(f"MCP工具 {self.name} 执行失败: {e}")
            raise


class MCPToolManager(ToolManager):
    """MCP工具管理器"""
    
    def __init__(self, mcp_server_url: Optional[str] = None):
        """
        初始化MCP工具管理器
        
        Args:
            mcp_server_url: MCP服务器URL（可选）
        """
        super().__init__()
        self.mcp_server_url = mcp_server_url
        self.mcp_clients: Dict[str, MCPClient] = {}
        self._initialized = False
        
        # 注册内置工具
        self._register_builtin_tools()
        
    def _register_builtin_tools(self):
        """注册内置工具"""
        # Web搜索工具
        self.register_tool(WebSearchTool())
        
        # 计算器工具
        self.register_tool(CalculatorTool())
        
        # 文件读取工具
        self.register_tool(FileReaderTool())
        
    async def initialize(self):
        """初始化工具管理器"""
        if self._initialized:
            return
            
        # 如果有MCP服务器URL，尝试连接
        if self.mcp_server_url:
            try:
                await self._connect_mcp_server(self.mcp_server_url)
            except Exception as e:
                logger.warning(f"连接MCP服务器失败: {e}")
                
        # 尝试加载本地MCP服务
        await self._load_local_mcp_services()
        
        self._initialized = True
        
    async def _connect_mcp_server(self, server_url: str):
        """连接到MCP服务器"""
        # TODO: 实现HTTP/WebSocket连接到远程MCP服务器
        logger.info(f"连接到MCP服务器: {server_url}")
        
    async def _load_local_mcp_services(self):
        """加载本地MCP服务"""
        # 检查是否有本地MCP服务定义
        try:
            import json
            with open("mcp/mcp_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                
            for service_name, service_config in config.get("services", {}).items():
                await self._load_mcp_service(service_name, service_config)
                
        except FileNotFoundError:
            logger.info("未找到mcp_config.json，跳过本地MCP服务加载")
        except Exception as e:
            logger.warning(f"加载本地MCP服务失败: {e}")
            
    async def _load_mcp_service(self, name: str, config: Dict[str, Any]):
        """加载单个MCP服务"""
        try:
            command = config.get("command", sys.executable)
            args = config.get("args", [])
            
            # 创建MCP客户端
            client = MCPClient(command, args)
            await client.connect()
            
            # 获取工具列表
            tools = await client.list_tools()
            
            # 注册每个工具
            for mcp_tool in tools:
                wrapper = MCPToolWrapper(mcp_tool, client)
                self.register_tool(wrapper)
                logger.info(f"从MCP服务 {name} 加载工具: {mcp_tool.name}")
                
            self.mcp_clients[name] = client
            
        except Exception as e:
            logger.error(f"加载MCP服务 {name} 失败: {e}")
            
    async def cleanup(self):
        """清理资源"""
        # 关闭所有MCP客户端
        for client in self.mcp_clients.values():
            try:
                await client.close()
            except:
                pass
                
        self.mcp_clients.clear()
        self._initialized = False


# 内置工具实现

class WebSearchTool(BaseTool):
    """Web搜索工具（模拟）"""
    
    def __init__(self):
        super().__init__(
            name="web_search",
            description="搜索网络获取信息",
            parameters={
                "query": {
                    "type": "string",
                    "description": "搜索查询",
                    "required": True
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数",
                    "required": False,
                    "default": 5
                }
            }
        )
        
    async def execute(self, query: str, max_results: int = 5) -> Any:
        """执行搜索（模拟）"""
        # 实际实现中，这里应该调用真实的搜索API
        await asyncio.sleep(0.5)  # 模拟网络延迟
        
        return {
            "results": [
                {
                    "title": f"搜索结果 {i+1}: {query}",
                    "snippet": f"这是关于'{query}'的搜索结果片段 {i+1}...",
                    "url": f"https://example.com/result{i+1}"
                }
                for i in range(min(max_results, 3))
            ],
            "total": 100,
            "query": query
        }


class CalculatorTool(BaseTool):
    """计算器工具"""
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="执行数学计算",
            parameters={
                "expression": {
                    "type": "string",
                    "description": "数学表达式",
                    "required": True
                }
            }
        )
        
    async def execute(self, expression: str) -> Any:
        """执行计算"""
        try:
            # 安全的数学表达式评估
            allowed_names = {
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow,
                "sqrt": __import__("math").sqrt,
                "sin": __import__("math").sin,
                "cos": __import__("math").cos,
                "tan": __import__("math").tan,
                "pi": __import__("math").pi,
                "e": __import__("math").e
            }
            
            # 评估表达式
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            
            return {
                "expression": expression,
                "result": result,
                "type": type(result).__name__
            }
            
        except Exception as e:
            return {
                "expression": expression,
                "error": str(e),
                "type": "error"
            }


class FileReaderTool(BaseTool):
    """文件读取工具"""
    
    def __init__(self):
        super().__init__(
            name="file_reader",
            description="读取文件内容",
            parameters={
                "file_path": {
                    "type": "string",
                    "description": "文件路径",
                    "required": True
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码",
                    "required": False,
                    "default": "utf-8"
                }
            }
        )
        
    async def execute(self, file_path: str, encoding: str = "utf-8") -> Any:
        """读取文件"""
        try:
            # 安全检查：只允许读取特定目录下的文件
            import os
            safe_path = os.path.abspath(file_path)
            allowed_dirs = [os.path.abspath("."), os.path.abspath("data")]
            
            if not any(safe_path.startswith(d) for d in allowed_dirs):
                raise PermissionError("不允许访问该文件路径")
                
            with open(safe_path, "r", encoding=encoding) as f:
                content = f.read()
                
            return {
                "file_path": file_path,
                "content": content,
                "size": len(content),
                "lines": content.count('\n') + 1
            }
            
        except Exception as e:
            return {
                "file_path": file_path,
                "error": str(e),
                "type": "error"
            } 