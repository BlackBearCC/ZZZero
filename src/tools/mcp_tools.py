"""
MCP工具管理器 - 直接调用服务器实例版本
"""
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.base import BaseTool
# 移除角色插件导入，现在使用MCP服务

logger = logging.getLogger(__name__)

@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    result: Any
    error: Optional[str] = None
    tool_name: Optional[str] = None

@dataclass
class MCPServerConfig:
    """MCP服务器配置"""
    name: str
    description: str = ""

@dataclass
class MCPTool:
    """MCP工具信息"""
    name: str
    description: str
    server_id: str
    schema: Optional[Dict[str, Any]] = None

class MCPBaseTool(BaseTool):
    """MCP工具基类"""
    
    def __init__(self, mcp_tool: MCPTool, tool_manager: 'MCPToolManager'):
        super().__init__(
            name=mcp_tool.name,
            description=mcp_tool.description,
            parameters=mcp_tool.schema or {}
        )
        self.mcp_tool = mcp_tool
        self.tool_manager = tool_manager
    
    async def execute(self, **kwargs) -> Any:
        """执行MCP工具"""
        return await self.tool_manager.execute_tool(self.mcp_tool.name, kwargs)

class MCPToolManager:
    """MCP工具管理器 - 直接调用服务器实例"""
    
    def __init__(self):
        
        # 服务器实例（直接实例化，不使用子进程）
        self.server_instances: Dict[str, Any] = {}
        
        # 服务器配置
        self.servers: Dict[str, MCPServerConfig] = {}
        
        # 工具注册
        self.tools: Dict[str, MCPBaseTool] = {}
        self.all_available_tools: Dict[str, MCPTool] = {}
        
        # 启用状态
        self.enabled_servers:  Set[str] = set()
        self.enabled_tools: Set[str] = set()
        
        # 移除角色插件管理器，现在通过MCP服务获取角色信息
        
        # 注册服务器和工具
        self._register_servers_and_tools()
        
        logger.info("MCP工具管理器（直接调用版）初始化完成，角色信息CRUD服务已集成")
    
    def _register_servers_and_tools(self):
        """注册服务器配置和工具"""
        
        # 注册CSV服务器
        csv_config = MCPServerConfig(
            name="CSV CRUD服务器",
            description="CSV文件数据库CRUD操作服务器"
        )
        self.servers["csv"] = csv_config
        
        # 注册CSV工具
        csv_tools = [
            MCPTool("create_table", "创建CSV表", "csv"),
            MCPTool("insert_records", "插入记录", "csv"),
            MCPTool("query_records", "查询记录", "csv"),
            MCPTool("update_records", "更新记录", "csv"),
            MCPTool("delete_records", "删除记录", "csv"),
            MCPTool("get_table_info", "获取表信息", "csv"),
            MCPTool("list_tables", "列出所有表", "csv"),
            MCPTool("drop_table", "删除表", "csv"),
        ]
        
        for tool in csv_tools:
            tool_key = f"csv_{tool.name}"
            self.all_available_tools[tool_key] = tool
        
        # 注册ChromaDB服务器
        chromadb_config = MCPServerConfig(
            name="ChromaDB CRUD服务器",
            description="ChromaDB向量数据库操作服务器"
        )
        self.servers["chromadb"] = chromadb_config
        
        # 注册ChromaDB工具
        chromadb_tools = [
            MCPTool("create_collection", "创建集合", "chromadb"),
            MCPTool("add_documents", "添加文档", "chromadb"),
            MCPTool("query_documents", "查询文档", "chromadb"),
            MCPTool("update_documents", "更新文档", "chromadb"),
            MCPTool("delete_documents", "删除文档", "chromadb"),
            MCPTool("get_collection_info", "获取集合信息", "chromadb"),
            MCPTool("list_collections", "列出所有集合", "chromadb"),
            MCPTool("delete_collection", "删除集合", "chromadb"),
        ]
        
        for tool in chromadb_tools:
            tool_key = f"chromadb_{tool.name}"
            self.all_available_tools[tool_key] = tool
        
        # 注册Python执行器服务器
        python_config = MCPServerConfig(
            name="Python代码执行服务器",
            description="安全的Python代码执行环境"
        )
        self.servers["python"] = python_config
        
        # 注册Python执行器工具
        python_tools = [
            MCPTool("execute_python", "执行Python代码", "python"),
            MCPTool("install_python_package", "安装Python包", "python"),
            MCPTool("list_installed_packages", "列出已安装的包", "python"),
            MCPTool("get_execution_history", "获取执行历史", "python"),
            MCPTool("clear_execution_history", "清空执行历史", "python"),
        ]
        
        for tool in python_tools:
            tool_key = f"python_{tool.name}"
            self.all_available_tools[tool_key] = tool
        
        # 注册角色信息CRUD服务器
        role_info_config = MCPServerConfig(
            name="角色信息CRUD服务器",
            description="支持角色人设、知识库和世界书的增删查改操作，集成向量数据库搜索"
        )
        self.servers["role_info"] = role_info_config
        
        # 注册角色信息CRUD工具
        role_info_tools = [
            # 角色人设工具
            MCPTool("create_profile", "创建新的角色人设", "role_info"),
            MCPTool("update_profile", "更新角色人设", "role_info"),
            MCPTool("query_profile", "查询角色人设", "role_info"),
            MCPTool("delete_profile", "删除角色人设", "role_info"),
            MCPTool("list_profiles", "列出所有角色人设", "role_info"),
            
            # 知识库工具
            MCPTool("add_knowledge", "添加知识条目", "role_info"),
            MCPTool("search_knowledge", "搜索知识库", "role_info"),
            MCPTool("update_knowledge", "更新知识条目", "role_info"),
            MCPTool("delete_knowledge", "删除知识条目", "role_info"),
            
            # 世界书工具
            MCPTool("add_world_entry", "添加世界书条目", "role_info"),
            MCPTool("search_world", "搜索世界书", "role_info"),
            MCPTool("update_world_entry", "更新世界书条目", "role_info"),
            MCPTool("delete_world_entry", "删除世界书条目", "role_info"),
            
            # 综合工具
            MCPTool("get_role_context", "获取完整的角色上下文（包含人设、知识库和世界书）", "role_info"),
        ]
        
        for tool in role_info_tools:
            tool_key = f"role_info_{tool.name}"
            self.all_available_tools[tool_key] = tool
        
        # 默认启用所有已注册的服务器
        self.set_enabled_servers(["csv", "chromadb", "python", "role_info"])
    
    async def initialize(self):
        """初始化工具管理器"""
        logger.info("开始启动MCP服务器...")
        
        # 启动启用的服务器
        started_servers = []
        failed_servers = []
        
        for server_id in self.enabled_servers:
            success = await self._start_server(server_id)
            if success:
                started_servers.append(server_id)
            else:
                failed_servers.append(server_id)
        
        logger.info(f"MCP服务器启动完成：{len(self.server_instances)}/{len(self.enabled_servers)} 个服务器运行中")
        
        if failed_servers:
            logger.warning(f"以下服务器启动失败: {failed_servers}")
            # 从启用列表中移除启动失败的服务器
            self.enabled_servers = self.enabled_servers - set(failed_servers)
        
        if started_servers:
            logger.info(f"成功启动的服务器: {started_servers}")
        
        self._update_enabled_tools()
    
    async def _start_server(self, server_id: str) -> bool:
        """启动MCP服务器实例"""
        if server_id not in self.servers:
            logger.error(f"未知服务器: {server_id}")
            return False
        
        # 如果已经在运行，跳过
        if server_id in self.server_instances:
            logger.info(f"MCP服务器已在运行: {self.servers[server_id].name}")
            return True
        
        config = self.servers[server_id]
        
        try:
            logger.info(f"启动MCP服务器: {config.name}")
            
            server_instance = None
            
            if server_id == "csv":
                # 直接导入并实例化CSV服务器
                from mcp_servers.csv_crud_server import CSVCRUDServer
                server_instance = CSVCRUDServer("./workspace/output")
                
            elif server_id == "chromadb":
                # 直接导入并实例化ChromaDB服务器
                try:
                    from mcp_servers.chromadb_crud_server import ChromaDBCRUDServer
                    server_instance = ChromaDBCRUDServer("./workspace/vectordb")
                except ImportError as e:
                    logger.warning(f"ChromaDB服务器启动失败，可能缺少依赖: {e}")
                    logger.warning(f"可以运行以下命令安装依赖: pip install chromadb")
                    return False
                except Exception as e:
                    logger.error(f"ChromaDB服务器启动失败: {e}")
                    return False
                    
            elif server_id == "python":
                # 直接导入并实例化Python执行器服务器
                try:
                    from mcp_servers.python_executor_server import PythonExecutorServer
                    server_instance = PythonExecutorServer("./workspace/python_executor")
                except Exception as e:
                    logger.error(f"Python执行器服务器启动失败: {e}")
                    return False
                    
            elif server_id == "role_info":
                # 直接导入并实例化角色信息CRUD服务器
                try:
                    from mcp_servers.role_info_crud_server import RoleInfoCRUDServer
                    server_instance = RoleInfoCRUDServer("./workspace")
                except Exception as e:
                    logger.error(f"角色信息CRUD服务器启动失败: {e}")
                    return False
                    
            else:
                logger.error(f"未知服务器类型: {server_id}")
                return False
            
            if server_instance is None:
                logger.error(f"服务器实例创建失败: {server_id}")
                return False
            
            self.server_instances[server_id] = server_instance
            
            # 获取并更新工具的真实schema信息
            await self._update_tools_schema(server_id, server_instance)
            
            logger.info(f"✅ MCP服务器启动成功: {config.name}")
            return True
                
        except Exception as e:
            logger.error(f"启动MCP服务器失败 {config.name}: {e}")
            return False
    
    async def _update_tools_schema(self, server_id: str, server_instance) -> None:
        """更新服务器工具的schema信息"""
        try:
            # 直接从服务器实例的_tools字典获取工具信息（MCP内部属性）
            if hasattr(server_instance, '_tools') and server_instance._tools:
                logger.info(f"从服务器 {server_id} 获取工具schema...")
                
                for tool_name, tool_def in server_instance._tools.items():
                    tool_key = f"{server_id}_{tool_name}"
                    
                    if tool_key in self.all_available_tools:
                        # 获取工具的inputSchema
                        input_schema = None
                        if hasattr(tool_def, 'inputSchema') and tool_def.inputSchema:
                            # 转换ToolInputSchema为普通字典
                            if hasattr(tool_def.inputSchema, 'type'):
                                input_schema = {
                                    "type": tool_def.inputSchema.type,
                                    "properties": getattr(tool_def.inputSchema, 'properties', {}),
                                    "required": getattr(tool_def.inputSchema, 'required', [])
                                }
                            elif isinstance(tool_def.inputSchema, dict):
                                input_schema = tool_def.inputSchema
                        
                        # 更新工具的schema
                        self.all_available_tools[tool_key].schema = input_schema
                        
                        logger.info(f"✅ 已更新工具 {tool_key} 的schema")
                        if input_schema:
                            properties_count = len(input_schema.get('properties', {}))
                            logger.debug(f"Schema: {properties_count} 个参数")
                    else:
                        logger.warning(f"服务器 {server_id} 中的工具 {tool_name} 未在注册列表中")
                        
                logger.info(f"服务器 {server_id} 的工具schema更新完成")
                
            # 备用方案：检查是否有tools属性（标准MCP）
            elif hasattr(server_instance, 'tools') and server_instance.tools:
                logger.info(f"使用标准MCP tools属性获取schema...")
                
                for tool_def in server_instance.tools:
                    tool_name = tool_def.name
                    tool_key = f"{server_id}_{tool_name}"
                    
                    if tool_key in self.all_available_tools:
                        # 处理标准MCP Tool对象
                        input_schema = None
                        if hasattr(tool_def, 'inputSchema') and tool_def.inputSchema:
                            if hasattr(tool_def.inputSchema, 'properties'):
                                input_schema = {
                                    "type": getattr(tool_def.inputSchema, 'type', 'object'),
                                    "properties": getattr(tool_def.inputSchema, 'properties', {}),
                                    "required": getattr(tool_def.inputSchema, 'required', [])
                                }
                            elif isinstance(tool_def.inputSchema, dict):
                                input_schema = tool_def.inputSchema
                        
                        self.all_available_tools[tool_key].schema = input_schema
                        logger.info(f"✅ 已更新工具 {tool_key} 的schema（标准MCP）")
                
                logger.info(f"服务器 {server_id} 的标准MCP工具schema更新完成")
            else:
                logger.warning(f"服务器 {server_id} 没有_tools或tools属性，尝试手动定义schema")
                
                # 手动定义已知工具的schema
                manual_schemas = self._get_manual_tool_schemas(server_id)
                for tool_key, schema in manual_schemas.items():
                    if tool_key in self.all_available_tools:
                        self.all_available_tools[tool_key].schema = schema
                        logger.info(f"✅ 已手动设置工具 {tool_key} 的schema")
                
        except Exception as e:
            logger.error(f"更新服务器 {server_id} 工具schema失败: {e}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
    
    def _get_manual_tool_schemas(self, server_id: str) -> Dict[str, Dict[str, Any]]:
        """手动定义工具schema（备用方案）"""
        schemas = {}
        
        
        return schemas
    
    def _is_server_running(self, server_id: str) -> bool:
        """检查服务器是否运行"""
        return server_id in self.server_instances
    
    def set_enabled_servers(self, server_ids: List[str]):
        """设置启用的服务器"""
        self.enabled_servers = set(server_ids)
        self._update_enabled_tools()
        logger.info(f"更新启用的MCP服务器: {server_ids}")
    
    def _update_enabled_tools(self):
        """根据启用的服务器更新可用工具列表"""
        self.enabled_tools.clear()
        
        for tool_key, tool in self.all_available_tools.items():
            if tool.server_id in self.enabled_servers:
                self.enabled_tools.add(tool_key)
        
        enabled_count = len(self.enabled_tools)
        total_count = len(self.all_available_tools)
        logger.info(f"工具暴露更新：{enabled_count}/{total_count} 个工具可用")
    
    async def _call_mcp_tool(self, tool: MCPTool, arguments: Dict[str, Any]) -> Any:
        """调用MCP工具 - 直接调用服务器实例方法"""
        if not self._is_server_running(tool.server_id):
            raise RuntimeError(f"MCP服务器 {tool.server_id} 未运行")
        
        # 使用原始参数（不再需要角色上下文注入，改为通过工具调用获取）
        enhanced_arguments = arguments
        
        server_instance = self.server_instances[tool.server_id]
        
        try:
            logger.info(f"直接调用工具: {tool.name}, 服务器: {tool.server_id}")
            logger.info(f"原始参数: {arguments}")
            logger.info(f"增强参数: {enhanced_arguments}")
            
            # 直接调用服务器的_call_tool方法，使用增强参数
            result = await server_instance._call_tool(tool.name, enhanced_arguments, None)
            
            logger.info(f"工具调用成功，原始结果: {result}")
            
            # 提取文本内容
            if isinstance(result, dict) and "content" in result:
                content = result["content"]
                if isinstance(content, list) and len(content) > 0:
                    first_content = content[0]
                    if isinstance(first_content, dict) and "text" in first_content:
                        extracted_text = first_content["text"]
                        logger.info(f"提取的文本内容: {extracted_text}")
                        return extracted_text
                return json.dumps(content, ensure_ascii=False)
            
            return result
            
        except Exception as e:
            logger.error(f"MCP工具调用失败 {tool.name}: {e}")
            raise
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具 - 供Agent调用的统一接口"""
        if tool_name not in self.enabled_tools:
            raise ValueError(f"工具未启用: {tool_name}")
        
        if tool_name not in self.all_available_tools:
            raise ValueError(f"工具不存在: {tool_name}")
        
        tool = self.all_available_tools[tool_name]
        return await self._call_mcp_tool(tool, arguments)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """调用工具 - 返回ToolResult格式（兼容接口）"""
        try:
            result = await self.execute_tool(tool_name, arguments)
            return ToolResult(
                success=True,
                result=result,
                tool_name=tool_name
            )
        except Exception as e:
            logger.error(f"工具调用失败 {tool_name}: {e}")
            return ToolResult(
                success=False,
                result=f"工具调用失败: {str(e)}",
                error=str(e),
                tool_name=tool_name
            )
    
    def list_tools(self) -> List[str]:
        """列出可用工具名称"""
        return [tool_name for tool_name in self.enabled_tools 
                if tool_name in self.all_available_tools and 
                self._is_server_running(self.all_available_tools[tool_name].server_id)]
    
    def get_tools_description(self) -> str:
        """获取工具描述 - 包含参数schema信息"""
        descriptions = []
        for tool_name in self.list_tools():
            tool = self.all_available_tools[tool_name]
            
            # 基础描述
            desc = f"- {tool_name}: {tool.description}"
            
            # 添加参数schema信息
            if tool.schema:
                desc += "\n  参数:"
                if isinstance(tool.schema, dict):
                    properties = tool.schema.get("properties", {})
                    required = tool.schema.get("required", [])
                    
                    for param_name, param_info in properties.items():
                        param_type = param_info.get("type", "unknown")
                        param_desc = param_info.get("description", "")
                        param_default = param_info.get("default")
                        param_min = param_info.get("minimum")
                        param_max = param_info.get("maximum")
                        
                        # 构建参数描述
                        param_line = f"    - {param_name} ({param_type})"
                        if param_name in required:
                            param_line += " [必填]"
                        else:
                            param_line += " [可选]"
                        
                        if param_desc:
                            param_line += f": {param_desc}"
                        
                        # 添加默认值和范围信息
                        extras = []
                        if param_default is not None:
                            extras.append(f"默认值={param_default}")
                        if param_min is not None and param_max is not None:
                            extras.append(f"范围={param_min}-{param_max}")
                        elif param_min is not None:
                            extras.append(f"最小值={param_min}")
                        elif param_max is not None:
                            extras.append(f"最大值={param_max}")
                        
                        if extras:
                            param_line += f" ({', '.join(extras)})"
                        
                        desc += f"\n{param_line}"
            else:
                desc += "\n  参数: 无参数"
            
            descriptions.append(desc)
        
        return "\n".join(descriptions)
    
    def check_server_dependencies(self, server_id: str) -> Dict[str, Any]:
        """检查服务器依赖"""
        if server_id == "chromadb":
            try:
                import chromadb
                return {"status": "ok", "message": "ChromaDB已安装"}
            except ImportError:
                return {
                    "status": "missing", 
                    "message": "ChromaDB未安装",
                    "install_command": "pip install chromadb"
                }
        elif server_id == "python":
            # Python执行器一般无额外依赖
            return {"status": "ok", "message": "Python执行器可用"}
        elif server_id == "csv":
            # CSV服务器无额外依赖
            return {"status": "ok", "message": "CSV服务器可用"}
        elif server_id == "role_info":
            # 角色信息CRUD服务器无额外依赖（除了可选的ChromaDB）
            return {"status": "ok", "message": "角色信息CRUD服务器可用"}
        else:
            return {"status": "unknown", "message": "未知服务器类型"}

    def get_servers_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有服务器状态"""
        servers_status = {}
        
        for server_id, config in self.servers.items():
            is_running = self._is_server_running(server_id)
            
            # 统计工具数量
            total_tools = len([t for t in self.all_available_tools.values() if t.server_id == server_id])
            enabled_tools = len([tool_name for tool_name in self.enabled_tools 
                               if tool_name in self.all_available_tools and 
                               self.all_available_tools[tool_name].server_id == server_id])
            
            # 检查依赖
            deps_info = self.check_server_dependencies(server_id)
            
            servers_status[server_id] = {
                'name': config.name,
                'description': config.description,
                'running': is_running,
                'enabled': server_id in self.enabled_servers,
                'total_tools': total_tools,
                'enabled_tools': enabled_tools,
                'dependencies': deps_info
            }
        
        return servers_status
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        tools = []
        for tool_name in self.enabled_tools:
            if tool_name in self.all_available_tools:
                tool = self.all_available_tools[tool_name]
                # 检查服务器是否运行
                if self._is_server_running(tool.server_id):
                    tools.append({
                        'name': tool_name,
                        'description': f"[{tool.server_id}] {tool.description}",
                        'server_id': tool.server_id,
                        'original_name': tool.name
                    })
                else:
                    logger.warning(f"服务器 {tool.server_id} 未运行，工具 {tool_name} 不可用")
        
        return tools
    
    # 移除角色插件权限检查功能，现在角色信息通过MCP服务管理
    
    async def cleanup(self):
        """清理资源"""
        logger.info("正在清理MCP服务器实例...")
        
        # 清理服务器实例
        for server_id in list(self.server_instances.keys()):
            try:
                server_instance = self.server_instances[server_id]
                # 如果服务器有cleanup方法，调用它
                if hasattr(server_instance, 'cleanup'):
                    await server_instance.cleanup()
                del self.server_instances[server_id]
                logger.info(f"服务器实例已清理: {server_id}")
            except Exception as e:
                logger.warning(f"清理服务器实例 {server_id} 时出错: {e}")
        
        # 清理内部状态
        self.enabled_tools.clear()
        self.enabled_servers.clear()
        self.tools.clear()
        self.all_available_tools.clear()
        
        logger.info("MCP工具管理器已清理")
    
    def cleanup_sync(self):
        """同步清理资源"""
        logger.info("正在同步清理MCP服务器实例...")
        
        # 清理服务器实例
        for server_id in list(self.server_instances.keys()):
            try:
                del self.server_instances[server_id]
                logger.info(f"服务器实例已清理: {server_id}")
            except Exception as e:
                logger.warning(f"清理服务器实例 {server_id} 时出错: {e}")
        
        # 清理内部状态
        self.enabled_tools.clear()
        self.enabled_servers.clear()
        self.tools.clear()
        self.all_available_tools.clear()
        
        logger.info("MCP工具管理器同步清理完成") 