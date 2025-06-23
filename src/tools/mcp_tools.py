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
from core.plugins import get_role_plugin_manager, RolePluginManager

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
        
        # 角色插件管理器
        self.role_plugin_manager: RolePluginManager = get_role_plugin_manager()
        
        # 注册服务器和工具
        self._register_servers_and_tools()
        
        logger.info("MCP工具管理器（直接调用版）初始化完成，角色插件已集成")
    
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
            MCPTool("check_code_safety", "检查代码安全性", "python"),
        ]
        
        for tool in python_tools:
            tool_key = f"python_{tool.name}"
            self.all_available_tools[tool_key] = tool
        
        # 注册角色扮演数据生成服务器
        roleplay_config = MCPServerConfig(
            name="角色扮演数据生成服务器",
            description="基于AI的角色扮演数据生成服务，支持日程规划等功能"
        )
        self.servers["roleplay"] = roleplay_config
        
        # 注册角色扮演数据生成工具
        roleplay_tools = [
            MCPTool("generate_schedule_plan", "生成日程计划框架", "roleplay"),
            MCPTool("generate_detailed_schedule", "生成详细5阶段日程", "roleplay"),
            MCPTool("get_time_phases", "获取5阶段时间规划信息", "roleplay"),
            MCPTool("get_generation_history", "获取生成历史记录", "roleplay"),
            MCPTool("clear_generation_history", "清空生成历史记录", "roleplay"),
        ]
        
        for tool in roleplay_tools:
            tool_key = f"roleplay_{tool.name}"
            self.all_available_tools[tool_key] = tool
        
        # 默认启用所有已注册的服务器
        self.set_enabled_servers(["csv", "chromadb", "python", "roleplay"])
    
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
            
            if server_id == "csv":
                # 直接导入并实例化CSV服务器
                from mcp_servers.csv_crud_server import CSVCRUDServer
                server_instance = CSVCRUDServer("./workspace/output")
                self.server_instances[server_id] = server_instance
                logger.info(f"✅ MCP服务器启动成功: {config.name}")
                return True
                
            elif server_id == "chromadb":
                # 直接导入并实例化ChromaDB服务器
                try:
                    from mcp_servers.chromadb_crud_server import ChromaDBCRUDServer
                    server_instance = ChromaDBCRUDServer("./workspace/vectordb")
                    self.server_instances[server_id] = server_instance
                    logger.info(f"✅ MCP服务器启动成功: {config.name}")
                    return True
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
                    self.server_instances[server_id] = server_instance
                    logger.info(f"✅ MCP服务器启动成功: {config.name}")
                    return True
                except Exception as e:
                    logger.error(f"Python执行器服务器启动失败: {e}")
                    return False
                    
            elif server_id == "roleplay":
                # 直接导入并实例化角色扮演数据生成服务器
                try:
                    from mcp_servers.roleplay_data_server import RolePlayDataServer
                    server_instance = RolePlayDataServer()
                    self.server_instances[server_id] = server_instance
                    logger.info(f"✅ MCP服务器启动成功: {config.name}")
                    return True
                except Exception as e:
                    logger.error(f"角色扮演数据生成服务器启动失败: {e}")
                    return False
            else:
                logger.error(f"未知服务器类型: {server_id}")
                return False
                
        except Exception as e:
            logger.error(f"启动MCP服务器失败 {config.name}: {e}")
            return False
    
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
        
        # 为有权限的服务器注入角色上下文
        enhanced_arguments = await self.inject_role_context_to_arguments(
            tool.server_id, tool.name, arguments
        )
        
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
        """获取工具描述"""
        descriptions = []
        for tool_name in self.list_tools():
            tool = self.all_available_tools[tool_name]
            descriptions.append(f"- {tool_name}: {tool.description}")
        
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
        elif server_id == "roleplay":
            # 角色扮演服务器无额外依赖
            return {"status": "ok", "message": "角色扮演服务器可用"}
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
    
    def has_role_plugin_permission(self, server_id: str) -> bool:
        """检查指定服务器是否有角色插件权限
        
        目前只有角色扮演数据生成服务器（roleplay）有权限使用角色插件
        """
        return server_id == "roleplay"
    
    async def get_role_context_for_server(self, server_id: str, keywords: List[str] = None) -> Dict[str, Any]:
        """为指定服务器获取角色上下文"""
        if not self.has_role_plugin_permission(server_id):
            return {}
        
        return await self.role_plugin_manager.get_role_context(keywords)
    
    async def inject_role_context_to_arguments(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """为工具调用注入角色上下文"""
        # 检查是否有权限使用角色插件
        if not self.has_role_plugin_permission(server_id):
            return arguments
        
        # 提取关键词（从需求描述中）
        keywords = []
        requirements = arguments.get("requirements", "")
        if requirements:
            # 简单的关键词提取（可以根据需要改进）
            import re
            words = re.findall(r'\b\w+\b', requirements)
            keywords = [word for word in words if len(word) > 2][:3]  # 取前3个有效关键词
        
        # 获取角色上下文
        role_context = await self.get_role_context_for_server(server_id, keywords)
        
        if not role_context:
            logger.info(f"服务器 {server_id} 未获取到角色上下文")
            return arguments
        
        # 注入角色上下文到参数中
        enhanced_arguments = arguments.copy()
        
        # 如果有角色资料，注入到character_description中
        if "profile" in role_context:
            profile_content = role_context["profile"]
            if "character_description" not in enhanced_arguments or not enhanced_arguments["character_description"].strip():
                enhanced_arguments["character_description"] = profile_content
                logger.info(f"已注入角色资料到工具 {tool_name}")
            else:
                # 如果已有角色描述，在前面添加插件角色资料
                enhanced_arguments["character_description"] = f"{profile_content}\n\n=== 补充角色描述 ===\n{enhanced_arguments['character_description']}"
                logger.info(f"已补充角色资料到工具 {tool_name}")
        
        # 如果有知识库结果，注入到requirements中
        if "knowledge" in role_context and role_context["knowledge"]:
            knowledge_content = "\n".join([
                f"- {item['keyword']}: {item['content']}" 
                for item in role_context["knowledge"]
            ])
            
            knowledge_section = f"\n\n=== 动态角色知识 ===\n{knowledge_content}"
            
            if "requirements" in enhanced_arguments:
                enhanced_arguments["requirements"] += knowledge_section
            else:
                enhanced_arguments["requirements"] = f"基础要求{knowledge_section}"
            
            logger.info(f"已注入 {len(role_context['knowledge'])} 条知识库结果到工具 {tool_name}")
        
        return enhanced_arguments
    
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