"""
工具模块 - 提供工具管理和集成
"""

try:
    from .base import ToolManager
    from .mcp_tools import MCPToolManager
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from tools.base import ToolManager
    from tools.mcp_tools import MCPToolManager

__all__ = [
    "ToolManager",
    "MCPToolManager"
] 