"""
ZZZero Agent Framework Core Components
"""

import sys
import os
# 确保能找到父目录
current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from core.base import (
    BaseNode,
    BaseAgent,
    BaseExecutor,
    BaseParser,
    BasePromptTemplate,
    NodeResult,
    ExecutionState,
    Command
)

from core.graph import (
    StateGraph,
    GraphBuilder,
    StateGraphExecutor,
    Edge,
    ConditionalEdge,
    RouteResult,
    Send
)

from core.types import (
    AgentType,
    NodeType,
    MessageRole,
    ToolCall,
    Message,
    TaskResult,
    BatchTask
)

__all__ = [
    # Base classes
    "BaseNode",
    "BaseAgent", 
    "BaseExecutor",
    "BaseParser",
    "BasePromptTemplate",
    "NodeResult",
    "ExecutionState",
    "Command",
    
    # Graph components
    "StateGraph",
    "GraphBuilder",
    "StateGraphExecutor",
    "Edge",
    "ConditionalEdge",
    "RouteResult",
    "Send",
    
    # Types
    "AgentType",
    "NodeType",
    "MessageRole",
    "ToolCall",
    "Message",
    "TaskResult",
    "BatchTask"
] 