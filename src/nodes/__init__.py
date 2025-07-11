"""
节点模块 - 提供各种预定义节点

注意：SimpleChatNode已废弃，所有AI回复都必须从"Thought:"开始。
请使用ReactAgentNode或StreamReactAgentNode代替。
"""

from .parallel_node import ParallelNode
from .react_agent_node import ReactAgentNode
from .react_tool_node import ReactToolNode
from .router_node import RouterNode
# from .simple_chat_node import SimpleChatNode  # 已废弃 - 不允许直接回答，必须从Thought开始
from .stream_react_agent_node import StreamReactAgentNode
from .thought_node import ThoughtNode
from .action_node import ActionNode
from .observation_node import ObservationNode
from .final_answer_node import FinalAnswerNode

__all__ = [
    "ParallelNode",
    "ReactAgentNode", 
    "ReactToolNode",
    "RouterNode",
    # "SimpleChatNode",  # 已废弃 - 所有AI回复都必须从Thought开始
    "StreamReactAgentNode",
    "ThoughtNode",
    "ActionNode",
    "ObservationNode",
    "FinalAnswerNode"
]
