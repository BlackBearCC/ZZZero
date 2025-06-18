"""
MCP客户端 - 遵循Model Context Protocol最佳实践
"""

import asyncio
import json
import sys
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """MCP工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    
    def to_prompt_description(self) -> str:
        """转换为提示词描述"""
        params = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                required = param_name in self.input_schema.get("required", [])
                param_desc = f"  - {param_name}: {param_info.get('description', 'No description')} {'(required)' if required else '(optional)'}"
                params.append(param_desc)
        
        params_str = "\n".join(params) if params else "  No parameters"
        
        return f"""
Tool: {self.name}
Description: {self.description}
Parameters:
{params_str}
"""


class MCPClient:
    """MCP客户端 - 处理与MCP服务器的通信"""
    
    def __init__(self, server_command: str, server_args: List[str] = None):
        """
        初始化MCP客户端
        
        Args:
            server_command: 服务器命令
            server_args: 服务器参数
        """
        self.server_command = server_command
        self.server_args = server_args or []
        self.session: Optional[ClientSession] = None
        self.tools: Dict[str, MCPTool] = {}
        
    async def connect(self) -> None:
        """连接到MCP服务器"""
        try:
            server_params = StdioServerParameters(
                command=self.server_command,
                args=self.server_args
            )
            
            # 使用stdio传输连接服务器
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session
                    
                    # 初始化会话
                    await session.initialize()
                    logger.info("MCP客户端已连接并初始化")
                    
                    # 获取可用工具
                    await self._load_tools()
                    
                    # 保持会话活跃
                    await self._keep_alive()
                    
        except Exception as e:
            logger.error(f"连接MCP服务器失败: {e}")
            raise
    
    async def _load_tools(self) -> None:
        """加载可用工具"""
        if not self.session:
            raise RuntimeError("客户端未连接")
            
        try:
            # 获取工具列表
            tools_response = await self.session.list_tools()
            
            # 解析工具定义
            for tool in tools_response.tools:
                mcp_tool = MCPTool(
                    name=tool.name,
                    description=tool.description or "No description",
                    input_schema=tool.inputSchema
                )
                self.tools[tool.name] = mcp_tool
                
            logger.info(f"已加载 {len(self.tools)} 个MCP工具")
            
        except Exception as e:
            logger.error(f"加载工具失败: {e}")
            raise
    
    async def _keep_alive(self) -> None:
        """保持会话活跃"""
        # 这里可以实现心跳或其他保活机制
        while self.session:
            await asyncio.sleep(30)
    
    def get_tools_prompt(self) -> str:
        """获取工具的提示词描述"""
        if not self.tools:
            return "No tools available"
            
        tools_desc = []
        for tool in self.tools.values():
            tools_desc.append(tool.to_prompt_description())
            
        return "\n".join(tools_desc)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用MCP工具"""
        if not self.session:
            raise RuntimeError("客户端未连接")
            
        if tool_name not in self.tools:
            raise ValueError(f"未知工具: {tool_name}")
            
        try:
            # 调用工具
            result = await self.session.call_tool(tool_name, arguments)
            
            # 处理结果
            if result.content:
                # 提取文本内容
                text_contents = []
                for content in result.content:
                    if hasattr(content, 'text'):
                        text_contents.append(content.text)
                
                return {
                    "success": True,
                    "result": "\n".join(text_contents) if text_contents else str(result.content)
                }
            else:
                return {
                    "success": True,
                    "result": "Tool executed successfully"
                }
                
        except Exception as e:
            logger.error(f"调用工具 {tool_name} 失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def close(self) -> None:
        """关闭客户端连接"""
        if self.session:
            # Session会在上下文管理器退出时自动关闭
            self.session = None
            logger.info("MCP客户端已关闭")


class MCPToolExecutor:
    """MCP工具执行器 - 解析LLM输出并执行工具调用"""
    
    def __init__(self, mcp_client: MCPClient):
        """
        初始化工具执行器
        
        Args:
            mcp_client: MCP客户端实例
        """
        self.mcp_client = mcp_client
        
    def parse_tool_calls(self, llm_output: str) -> List[Dict[str, Any]]:
        """
        解析LLM输出中的工具调用
        
        支持多种格式:
        1. JSON代码块: ```json { "tool": "name", "arguments": {...} } ```
        2. 多个工具调用: 每个调用独立的JSON块
        3. 工具调用数组: [{"tool": "name1", ...}, {"tool": "name2", ...}]
        """
        tool_calls = []
        
        # 尝试提取JSON代码块
        import re
        json_blocks = re.findall(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', llm_output, re.DOTALL)
        
        for block in json_blocks:
            try:
                parsed = json.loads(block)
                
                # 处理数组格式
                if isinstance(parsed, list):
                    for item in parsed:
                        if self._is_valid_tool_call(item):
                            tool_calls.append(item)
                # 处理单个工具调用
                elif self._is_valid_tool_call(parsed):
                    tool_calls.append(parsed)
                    
            except json.JSONDecodeError:
                logger.warning(f"无法解析JSON块: {block[:100]}...")
                continue
        
        # 如果没有找到JSON块，尝试直接解析整个输出
        if not tool_calls:
            try:
                parsed = json.loads(llm_output)
                if isinstance(parsed, list):
                    tool_calls = [item for item in parsed if self._is_valid_tool_call(item)]
                elif self._is_valid_tool_call(parsed):
                    tool_calls = [parsed]
            except:
                pass
        
        return tool_calls
    
    def _is_valid_tool_call(self, obj: Any) -> bool:
        """检查对象是否是有效的工具调用"""
        if not isinstance(obj, dict):
            return False
            
        # 支持多种格式
        tool_name = obj.get("tool") or obj.get("name") or obj.get("tool_name")
        arguments = obj.get("arguments") or obj.get("params") or obj.get("parameters")
        
        return bool(tool_name and isinstance(arguments, dict))
    
    async def execute_tool_calls(self, llm_output: str) -> List[Dict[str, Any]]:
        """执行LLM输出中的所有工具调用"""
        tool_calls = self.parse_tool_calls(llm_output)
        
        if not tool_calls:
            logger.info("未找到工具调用")
            return []
        
        results = []
        for call in tool_calls:
            tool_name = call.get("tool") or call.get("name") or call.get("tool_name")
            arguments = call.get("arguments") or call.get("params") or call.get("parameters")
            
            logger.info(f"执行工具调用: {tool_name} with {arguments}")
            result = await self.mcp_client.call_tool(tool_name, arguments)
            
            results.append({
                "tool": tool_name,
                "arguments": arguments,
                "result": result
            })
        
        return results


def create_tools_system_prompt(mcp_client: MCPClient) -> str:
    """创建包含工具描述的系统提示词"""
    tools_desc = mcp_client.get_tools_prompt()
    
    return f"""你是一个智能助手，可以使用以下MCP工具来帮助用户：

{tools_desc}

当你需要调用工具时，请使用以下JSON格式输出：

```json
{{
    "tool": "工具名称",
    "arguments": {{
        "参数名": "参数值"
    }}
}}
```

你可以在一次回复中调用多个工具，每个工具调用使用独立的JSON代码块。

重要提示：
1. 确保工具名称与上述列表中的名称完全匹配
2. 提供所有必需的参数
3. 参数类型要正确（字符串、数字、布尔值等）
4. 可以根据需要组合使用多个工具
"""


# 使用示例
async def example_usage():
    """示例：如何使用MCP客户端"""
    
    # 创建客户端
    client = MCPClient(
        server_command=sys.executable,
        server_args=["-m", "src.mcp_services.mcp_launcher", "--service", "combined"]
    )
    
    # 连接到服务器
    await client.connect()
    
    try:
        # 获取工具提示词
        tools_prompt = create_tools_system_prompt(client)
        print("系统提示词:")
        print(tools_prompt)
        
        # 创建工具执行器
        executor = MCPToolExecutor(client)
        
        # 模拟LLM输出
        llm_output = """
        我来帮你查询角色信息。
        
        ```json
        {
            "tool": "csv_query",
            "arguments": {
                "file_path": "processed_attributes.csv",
                "query": "character_name == '方知衡'",
                "limit": 1
            }
        }
        ```
        
        现在让我搜索相关的文档：
        
        ```json
        {
            "tool": "vector_enhanced_search",
            "arguments": {
                "collection_name": "documents",
                "base_query": "工作日程规划",
                "character_traits": ["理性", "高效"],
                "n_results": 3
            }
        }
        ```
        """
        
        # 执行工具调用
        results = await executor.execute_tool_calls(llm_output)
        
        # 打印结果
        for result in results:
            print(f"\n工具: {result['tool']}")
            print(f"参数: {result['arguments']}")
            print(f"结果: {result['result']}")
            
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(example_usage()) 