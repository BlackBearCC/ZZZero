#!/usr/bin/env python3
"""
简化版MCP工具管理器 - 直接管理服务器进程和工具调用
"""
import asyncio
import logging
import json
import subprocess
import sys
import os
import time
import atexit
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from tools.base import ToolManager
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
class MCPServerConfig:
    """MCP服务器配置"""
    name: str
    command: List[str]
    working_dir: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    description: str = ""


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
        # 构建参数描述
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
        return await self.tool_manager._call_mcp_tool(self.mcp_tool, kwargs)


class MCPToolManager(ToolManager):
    """统一的MCP工具管理器 - 管理服务器进程和工具调用"""
    
    def __init__(self):
        """初始化MCP工具管理器"""
        super().__init__()
        
        # 服务器管理
        self.servers: Dict[str, MCPServerConfig] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.project_root = Path(__file__).parent.parent.parent
        
        # 工具管理
        self.all_available_tools: Dict[str, MCPTool] = {}
        self.enabled_servers: set = set()
        
        # 注册服务器和工具
        self._register_servers_and_tools()
        
        # 注册退出清理
        atexit.register(self._cleanup_on_exit)
        
        logger.info("MCP工具管理器初始化完成")
    
    def _register_servers_and_tools(self):
        """注册服务器配置和工具定义"""
        python_exe = sys.executable
        
        # CSV服务器
        csv_server_path = self.project_root / "mcp_servers" / "csv_crud_server.py"
        if csv_server_path.exists():
            self.servers["csv"] = MCPServerConfig(
                name="CSV CRUD服务器",
                command=[python_exe, str(csv_server_path)],
                working_dir=str(self.project_root),
                description="CSV文件数据库CRUD操作服务器"
            )
            
            # 注册CSV工具
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
                # 创建BaseTool适配器并注册
                base_tool = MCPBaseTool(tool, self)
                self.register_tool(base_tool)
        
        # ChromaDB服务器
        chroma_server_path = self.project_root / "mcp_servers" / "chromadb_crud_server.py"
        if chroma_server_path.exists():
            self.servers["chromadb"] = MCPServerConfig(
                name="ChromaDB CRUD服务器",
                command=[python_exe, str(chroma_server_path)],
                working_dir=str(self.project_root),
                description="ChromaDB向量数据库操作服务器"
            )
            
            # 注册ChromaDB工具
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
                # 创建BaseTool适配器并注册
                base_tool = MCPBaseTool(tool, self)
                self.register_tool(base_tool)
        
        # 默认启用CSV服务器
        self.set_enabled_servers(["csv"])
    
    async def initialize(self):
        """初始化工具管理器 - 启动MCP服务器"""
        logger.info("开始启动MCP服务器...")
        results = {}
        
        for server_id in self.servers:
            try:
                results[server_id] = await self._start_server(server_id)
            except Exception as e:
                logger.error(f"启动服务器失败 {server_id}: {e}")
                results[server_id] = False
        
        running_count = sum(results.values())
        total_count = len(results)
        logger.info(f"MCP服务器启动完成：{running_count}/{total_count} 个服务器运行中")
        
        # 更新启用的工具
        self._update_enabled_tools()
    
    async def _start_server(self, server_id: str) -> bool:
        """启动MCP服务器"""
        if server_id not in self.servers:
            logger.error(f"未知服务器: {server_id}")
            return False
        
        # 如果已经在运行，跳过
        if self._is_server_running(server_id):
            logger.info(f"MCP服务器已在运行: {self.servers[server_id].name}")
            return True
        
        config = self.servers[server_id]
        
        try:
            logger.info(f"启动MCP服务器: {config.name}")
            logger.info(f"启动命令: {' '.join(config.command)}")
            logger.info(f"工作目录: {config.working_dir}")
            
            # 启动进程
            process = subprocess.Popen(
                config.command,
                cwd=config.working_dir,
                env={**os.environ, **(config.env or {})},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=0
            )
            
            # 等待进程启动
            await asyncio.sleep(0.5)
            
            # 检查进程是否还在运行
            poll_result = process.poll()
            if poll_result is None:
                self.processes[server_id] = process
                logger.info(f"✅ MCP服务器启动成功: {config.name} (PID: {process.pid})")
                
                # 尝试发送一个测试请求来验证服务器是否正常工作
                try:
                    test_request = {
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "params": {
                            "protocol_version": "2024-11-05",
                            "client_info": {
                                "name": "mcp-tool-manager",
                                "version": "1.0.0"
                            },
                            "capabilities": {}
                        },
                        "id": 1
                    }
                    
                    request_line = json.dumps(test_request) + '\n'
                    process.stdin.write(request_line)
                    process.stdin.flush()
                    
                    # 等待响应
                    await asyncio.sleep(0.3)
                    
                    # 尝试读取响应（非阻塞）
                    import select
                    if hasattr(select, 'select'):  # Unix系统
                        ready, _, _ = select.select([process.stdout], [], [], 0)
                        if ready:
                            response = process.stdout.readline()
                            if response:
                                logger.info(f"服务器 {server_id} 初始化响应: {response.strip()}")
                            else:
                                logger.warning(f"服务器 {server_id} 初始化无响应")
                    else:  # Windows系统
                        logger.info(f"Windows系统，跳过初始化测试")
                        
                except Exception as e:
                    logger.warning(f"服务器 {server_id} 初始化测试失败: {e}")
                
                return True
            else:
                # 进程已退出，获取错误信息
                stdout, stderr = process.communicate()
                logger.error(f"❌ MCP服务器启动失败: {config.name}")
                logger.error(f"退出码: {poll_result}")
                if stdout:
                    logger.error(f"stdout: {stdout}")
                if stderr:
                    logger.error(f"stderr: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"启动MCP服务器失败 {config.name}: {e}")
            return False
    
    def _is_server_running(self, server_id: str) -> bool:
        """检查服务器是否运行"""
        if server_id not in self.processes:
            return False
        
        process = self.processes[server_id]
        return process.poll() is None
    
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
        """调用MCP工具 - 真实的JSON-RPC通信"""
        # 添加详细调试信息
        logger.info(f"准备调用工具: {tool.name}, 服务器: {tool.server_id}")
        logger.info(f"当前运行的服务器进程: {list(self.processes.keys())}")
        
        # 检查服务器是否在进程列表中
        if tool.server_id not in self.processes:
            logger.error(f"服务器 {tool.server_id} 不在进程列表中")
            logger.error(f"可用进程: {list(self.processes.keys())}")
            raise RuntimeError(f"MCP服务器 {tool.server_id} 未运行 - 进程不存在")
        
        # 检查进程状态
        process = self.processes[tool.server_id]
        poll_result = process.poll()
        logger.info(f"服务器 {tool.server_id} 进程状态: poll()={poll_result} (None表示运行中)")
        
        if not self._is_server_running(tool.server_id):
            logger.error(f"服务器 {tool.server_id} 进程已退出，退出码: {poll_result}")
            raise RuntimeError(f"MCP服务器 {tool.server_id} 未运行 - 进程已退出")
        
        # 构造MCP工具调用请求
        request = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": "tools/call",
            "params": {
                "name": tool.name,
                "arguments": arguments
            }
        }
        
        logger.info(f"发送JSON-RPC请求: {json.dumps(request, ensure_ascii=False)}")
        
        try:
            # 发送请求
            request_line = json.dumps(request) + '\n'
            process.stdin.write(request_line)
            process.stdin.flush()
            logger.info("请求已发送，等待响应...")
            
            # 读取响应
            response_line = process.stdout.readline()
            if not response_line:
                logger.error("MCP服务器无响应")
                raise RuntimeError("MCP服务器无响应")
            
            logger.info(f"收到响应: {response_line.strip()}")
            response = json.loads(response_line.strip())
            
            # 检查响应
            if "error" in response:
                logger.error(f"MCP工具调用错误: {response['error']}")
                raise RuntimeError(f"MCP工具调用错误: {response['error']}")
            
            # 返回工具调用结果，提取content字段
            result = response.get("result", {})
            logger.info(f"工具调用成功，原始结果: {result}")
            
            if isinstance(result, dict) and "content" in result:
                # 如果结果包含content字段，提取文本内容
                content = result["content"]
                if isinstance(content, list) and len(content) > 0:
                    # 提取第一个content项的文本
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
            
            servers_status[server_id] = {
                'name': config.name,
                'description': config.description,
                'running': is_running,
                'enabled': server_id in self.enabled_servers,
                'total_tools': total_tools,
                'enabled_tools': enabled_tools
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
    
    async def cleanup(self):
        """清理资源"""
        logger.info("正在停止所有MCP服务器...")
        for server_id in list(self.processes.keys()):
            await self._stop_server(server_id)
        logger.info("MCP工具管理器已清理")
    
    def cleanup_sync(self):
        """同步清理资源"""
        logger.info("正在同步停止所有MCP服务器...")
        for server_id in list(self.processes.keys()):
            if server_id in self.processes:
                try:
                    process = self.processes[server_id]
                    process.terminate()
                    process.wait(timeout=5)
                except Exception as e:
                    logger.warning(f"停止服务器 {server_id} 时出错: {e}")
                    try:
                        process.kill()
                    except:
                        pass
                finally:
                    if server_id in self.processes:
                        del self.processes[server_id]
        
        # 清理内部状态
        self.enabled_tools.clear()
        self.enabled_servers.clear()
        self.tools.clear()
        self.all_available_tools.clear()
        logger.info("MCP工具管理器同步清理完成")
    
    async def _stop_server(self, server_id: str):
        """停止MCP服务器"""
        if server_id in self.processes:
            try:
                process = self.processes[server_id]
                process.terminate()
                
                # 等待进程结束
                try:
                    await asyncio.wait_for(asyncio.create_task(
                        asyncio.to_thread(process.wait)
                    ), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await asyncio.to_thread(process.wait)
                
                del self.processes[server_id]
                logger.info(f"MCP服务器已停止: {self.servers[server_id].name}")
            except Exception as e:
                logger.error(f"停止MCP服务器失败: {e}")
    
    def _cleanup_on_exit(self):
        """程序退出时的清理函数"""
        try:
            for server_id in list(self.processes.keys()):
                if server_id in self.processes:
                    self.processes[server_id].terminate()
        except:
            pass 