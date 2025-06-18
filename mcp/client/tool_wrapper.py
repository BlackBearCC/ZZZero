"""
MCP工具包装器 - 与现有框架兼容
"""
import json
import re
from typing import Dict, List, Any, Optional, Union
import logging

from .base import MCPClient
from ..types import Tool, ToolContent

logger = logging.getLogger(__name__)


class MCPTool:
    """MCP工具包装器 - 与现有框架兼容"""
    
    def __init__(self, tool: Tool, client: MCPClient):
        """
        初始化MCP工具包装器
        
        Args:
            tool: MCP工具定义
            client: MCP客户端
        """
        self.name = tool.name
        self.description = tool.description
        self.input_schema = tool.input_schema
        self._client = client
        self._tool = tool
    
    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        try:
            result = await self._client.call_tool(self.name, kwargs)
            
            # 提取内容
            if result:
                content = result[0]
                if content.type == "text" and content.text:
                    return content.text
                elif content.type == "image" and content.data:
                    return {
                        "type": "image", 
                        "data": content.data, 
                        "mime_type": content.mime_type
                    }
                elif content.type == "resource":
                    return {
                        "type": "resource",
                        "content": content.text or content.data,
                        "mime_type": content.mime_type
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error executing tool {self.name}: {e}")
            raise
    
    def to_prompt_description(self) -> str:
        """转换为提示词描述（兼容性方法）"""
        params = []
        if "properties" in self.input_schema.properties:
            properties = self.input_schema.properties.get("properties", {})
            required = self.input_schema.properties.get("required", [])
            
            for param_name, param_info in properties.items():
                is_required = param_name in required
                param_desc = f"  - {param_name}: {param_info.get('description', 'No description')} {'(required)' if is_required else '(optional)'}"
                params.append(param_desc)
        
        params_str = "\n".join(params) if params else "  No parameters"
        
        return f"""
Tool: {self.name}
Description: {self.description}
Parameters:
{params_str}
"""
    
    def __repr__(self) -> str:
        return f"MCPTool(name='{self.name}', description='{self.description}')"


class ToolExecutor:
    """MCP工具执行器 - 解析LLM输出并执行工具调用"""
    
    def __init__(self, client: MCPClient):
        """
        初始化工具执行器
        
        Args:
            client: MCP客户端实例
        """
        self.client = client
        self._tools: Dict[str, MCPTool] = {}
    
    async def load_tools(self) -> Dict[str, MCPTool]:
        """加载可用工具"""
        try:
            tools = await self.client.list_tools()
            
            self._tools.clear()
            for tool in tools:
                mcp_tool = MCPTool(tool, self.client)
                self._tools[tool.name] = mcp_tool
            
            logger.info(f"Loaded {len(self._tools)} MCP tools")
            return self._tools.copy()
            
        except Exception as e:
            logger.error(f"Error loading tools: {e}")
            raise
    
    def get_tools(self) -> Dict[str, MCPTool]:
        """获取已加载的工具"""
        return self._tools.copy()
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """获取指定工具"""
        return self._tools.get(name)
    
    def get_tools_prompt(self) -> str:
        """获取工具的提示词描述（兼容性方法）"""
        if not self._tools:
            return "No tools available"
        
        tools_desc = []
        for tool in self._tools.values():
            tools_desc.append(tool.to_prompt_description())
        
        return "\n".join(tools_desc)
    
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
                logger.warning(f"Unable to parse JSON block: {block[:100]}...")
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
            logger.info("No tool calls found in LLM output")
            return []
        
        results = []
        for call in tool_calls:
            tool_name = call.get("tool") or call.get("name") or call.get("tool_name")
            arguments = call.get("arguments") or call.get("params") or call.get("parameters")
            
            logger.info(f"Executing tool call: {tool_name} with {arguments}")
            
            try:
                # 检查工具是否存在
                if tool_name not in self._tools:
                    raise ValueError(f"Unknown tool: {tool_name}")
                
                tool = self._tools[tool_name]
                result = await tool.execute(**arguments)
                
                results.append({
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": {"success": True, "result": result}
                })
                
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                results.append({
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": {"success": False, "error": str(e)}
                })
        
        return results
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """直接调用工具（兼容性方法）"""
        if tool_name not in self._tools:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
        
        try:
            tool = self._tools[tool_name]
            result = await tool.execute(**arguments)
            
            return {
                "success": True,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def create_tools_system_prompt(executor: ToolExecutor) -> str:
    """创建包含工具描述的系统提示词（兼容性函数）"""
    tools_desc = executor.get_tools_prompt()
    
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