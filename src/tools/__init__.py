"""
工具模块 - 提供工具管理和集成
"""

import sys
import os
# 确保能找到父目录
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# 使用绝对导入
from tools.base import ToolManager
from tools.mcp_tools import MCPToolManager

__all__ = [
    "ToolManager",
    "MCPToolManager"
] 