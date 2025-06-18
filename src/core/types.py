"""
核心类型定义 - 使用Pydantic进行类型验证和序列化
"""
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AgentType(str, Enum):
    """Agent类型枚举"""
    REACT = "react"  # ReAct范式
    COT = "chain_of_thought"  # 思维链
    TOT = "tree_of_thought"  # 思维树
    REFLEXION = "reflexion"  # 反思范式
    PLAN_EXECUTE = "plan_execute"  # 计划执行
    MULTI_AGENT = "multi_agent"  # 多智能体
    CUSTOM = "custom"  # 自定义


class NodeType(str, Enum):
    """节点类型枚举"""
    INIT = "init"
    THINK = "think"
    ACT = "act"
    OBSERVE = "observe"
    REFLECT = "reflect"
    PLAN = "plan"
    EXECUTE = "execute"
    EVALUATE = "evaluate"
    FINALIZE = "finalize"
    ROUTER = "router"
    PARALLEL = "parallel"
    CUSTOM = "custom"


class MessageRole(str, Enum):
    """消息角色枚举"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    FUNCTION = "function"


class Message(BaseModel):
    """消息模型"""
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List["ToolCall"]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(use_enum_values=True)


class ToolCall(BaseModel):
    """工具调用模型"""
    id: str
    name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class TaskResult(BaseModel):
    """任务结果模型"""
    task_id: str
    query: str
    result: Optional[str] = None
    success: bool = False
    error: Optional[str] = None
    agent_type: Optional[AgentType] = None
    execution_trace: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    @property
    def duration(self) -> Optional[float]:
        """计算执行时长(秒)"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    model_config = ConfigDict(use_enum_values=True)


class BatchTask(BaseModel):
    """批量任务模型"""
    batch_id: str
    tasks: List[Dict[str, Any]]
    agent_type: AgentType
    parallel: bool = False
    max_workers: int = 5
    timeout: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(use_enum_values=True)


class ExecutionContext(BaseModel):
    """执行上下文"""
    task_id: str
    agent_type: AgentType
    available_tools: List[str]
    messages: List[Message] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(use_enum_values=True)


class NodeInput(BaseModel):
    """节点输入"""
    context: ExecutionContext
    previous_output: Optional[Any] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class NodeOutput(BaseModel):
    """节点输出"""
    data: Any
    next_node: Optional[str] = None
    should_continue: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


class GraphConfig(BaseModel):
    """图配置"""
    name: str
    description: Optional[str] = None
    nodes: List[Dict[str, Any]]
    connections: List[Dict[str, Any]]
    entry_point: str
    exit_points: List[str] = Field(default_factory=list)
    max_iterations: int = 10
    timeout: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    """LLM配置"""
    provider: Literal["openai", "anthropic", "doubao", "custom"]
    model_name: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    streaming: bool = False
    timeout: int = 30
    retry_times: int = 3
    extra_params: Dict[str, Any] = Field(default_factory=dict)


class ToolConfig(BaseModel):
    """工具配置"""
    name: str
    enabled: bool = True
    description: Optional[str] = None
    mcp_server: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict) 