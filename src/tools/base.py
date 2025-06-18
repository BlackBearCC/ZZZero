"""
工具基类和管理器
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import asyncio

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from core.base import BaseTool


class ToolManager(ABC):
    """工具管理器基类"""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self.enabled_tools: set = set()
        
    @abstractmethod
    async def initialize(self):
        """初始化工具管理器"""
        pass
        
    @abstractmethod
    async def cleanup(self):
        """清理资源"""
        pass
        
    def register_tool(self, tool: BaseTool):
        """注册工具"""
        self.tools[tool.name] = tool
        
    def enable_tool(self, tool_name: str):
        """启用工具"""
        if tool_name in self.tools:
            self.enabled_tools.add(tool_name)
        else:
            raise ValueError(f"工具 {tool_name} 未注册")
            
    def disable_tool(self, tool_name: str):
        """禁用工具"""
        self.enabled_tools.discard(tool_name)
        
    def list_tools(self) -> List[str]:
        """列出所有启用的工具"""
        return list(self.enabled_tools)
        
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具实例"""
        if tool_name in self.enabled_tools:
            return self.tools.get(tool_name)
        return None
        
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具"""
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"工具 {tool_name} 未启用或不存在")
            
        # 验证参数
        if not tool.validate_parameters(**arguments):
            raise ValueError(f"工具 {tool_name} 参数验证失败")
            
        # 执行工具
        return await tool.execute(**arguments)
        
    def get_tools_description(self) -> str:
        """获取所有启用工具的描述"""
        descriptions = []
        for tool_name in sorted(self.enabled_tools):
            tool = self.tools[tool_name]
            desc = f"### {tool.name}\n{tool.description}"
            
            # 添加参数说明
            if tool.parameters:
                desc += "\n参数："
                for param_name, param_info in tool.parameters.items():
                    required = param_info.get("required", False)
                    param_type = param_info.get("type", "string")
                    param_desc = param_info.get("description", "")
                    
                    desc += f"\n- {param_name} ({param_type}){' [必需]' if required else ''}: {param_desc}"
                    
            descriptions.append(desc)
            
        return "\n\n".join(descriptions) if descriptions else "没有可用的工具" 