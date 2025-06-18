"""
核心基类定义 - 定义框架的抽象接口
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Type, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from enum import Enum

from pydantic import BaseModel
from .types import (
    NodeInput, NodeOutput, ExecutionContext, Message, 
    ToolCall, AgentType, NodeType, TaskResult
)


T = TypeVar('T')


class ExecutionState(str, Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class NodeResult:
    """节点执行结果"""
    node_name: str
    node_type: NodeType
    output: NodeOutput
    state: ExecutionState
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    
    @property
    def duration(self) -> Optional[float]:
        """计算执行时长(秒)"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


@dataclass
class AgentContext:
    """Agent执行上下文"""
    task_id: str
    agent_type: AgentType
    available_tools: List[str]
    messages: List[Message] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    node_results: List[NodeResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_execution_context(self) -> ExecutionContext:
        """转换为ExecutionContext"""
        return ExecutionContext(
            task_id=self.task_id,
            agent_type=self.agent_type,
            available_tools=self.available_tools,
            messages=self.messages,
            variables=self.variables,
            metadata=self.metadata
        )


class BaseNode(ABC):
    """节点基类 - 所有节点必须继承此类"""
    
    def __init__(self, 
                 name: str,
                 node_type: NodeType = NodeType.CUSTOM,
                 description: Optional[str] = None,
                 **kwargs):
        self.name = name
        self.node_type = node_type
        self.description = description
        self.config = kwargs
        
    @abstractmethod
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """
        执行节点逻辑
        
        Args:
            input_data: 节点输入数据
            
        Returns:
            NodeOutput: 节点输出结果
        """
        pass
        
    async def pre_execute(self, input_data: NodeInput) -> NodeInput:
        """执行前钩子 - 可以修改输入数据"""
        return input_data
        
    async def post_execute(self, output: NodeOutput) -> NodeOutput:
        """执行后钩子 - 可以修改输出数据"""
        return output
        
    async def run(self, input_data: NodeInput) -> NodeResult:
        """运行节点 - 包含前后处理逻辑"""
        result = NodeResult(
            node_name=self.name,
            node_type=self.node_type,
            output=None,
            state=ExecutionState.RUNNING
        )
        
        try:
            # 前处理
            input_data = await self.pre_execute(input_data)
            
            # 执行核心逻辑
            output = await self.execute(input_data)
            
            # 后处理
            output = await self.post_execute(output)
            
            result.output = output
            result.state = ExecutionState.SUCCESS
            result.end_time = datetime.now()
            
        except Exception as e:
            result.state = ExecutionState.FAILED
            result.error = str(e)
            result.end_time = datetime.now()
            raise
            
        return result


class BaseAgent(ABC):
    """Agent基类 - 所有Agent必须继承此类"""
    
    def __init__(self,
                 agent_type: AgentType,
                 name: Optional[str] = None,
                 description: Optional[str] = None,
                 **kwargs):
        self.agent_type = agent_type
        self.name = name or f"{agent_type.value}_agent"
        self.description = description
        self.config = kwargs
        
    @abstractmethod
    async def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> TaskResult:
        """
        运行Agent
        
        Args:
            query: 用户查询
            context: 额外上下文
            
        Returns:
            TaskResult: 任务执行结果
        """
        pass
        
    @abstractmethod
    def build_graph(self) -> "Graph":
        """构建执行图"""
        pass
        
    async def initialize(self):
        """初始化Agent"""
        pass
        
    async def cleanup(self):
        """清理资源"""
        pass


class BaseExecutor(ABC):
    """执行器基类 - 负责执行图"""
    
    @abstractmethod
    async def execute(self, 
                     graph: "Graph", 
                     context: AgentContext,
                     **kwargs) -> List[NodeResult]:
        """
        执行图
        
        Args:
            graph: 要执行的图
            context: 执行上下文
            
        Returns:
            List[NodeResult]: 节点执行结果列表
        """
        pass


class BaseParser(ABC, Generic[T]):
    """解析器基类 - 解析LLM输出"""
    
    @abstractmethod
    def parse(self, text: str) -> T:
        """
        解析文本
        
        Args:
            text: 要解析的文本
            
        Returns:
            T: 解析结果
        """
        pass
        
    @abstractmethod
    async def aparse(self, text: str) -> T:
        """异步解析文本"""
        pass
        
    def validate(self, result: T) -> bool:
        """验证解析结果"""
        return True


class BasePromptTemplate(ABC):
    """提示模板基类"""
    
    def __init__(self, template: str, **kwargs):
        self.template = template
        self.variables = kwargs
        
    @abstractmethod
    def format(self, **kwargs) -> str:
        """
        格式化模板
        
        Args:
            **kwargs: 模板变量
            
        Returns:
            str: 格式化后的提示
        """
        pass
        
    @abstractmethod
    def get_variables(self) -> List[str]:
        """获取模板变量列表"""
        pass
        
    def validate_variables(self, **kwargs) -> bool:
        """验证变量是否完整"""
        required_vars = self.get_variables()
        provided_vars = set(kwargs.keys())
        missing_vars = set(required_vars) - provided_vars
        return len(missing_vars) == 0


class BaseLLM(ABC):
    """LLM基类 - 所有LLM提供者必须实现此接口"""
    
    @abstractmethod
    async def generate(self, 
                      messages: List[Message],
                      **kwargs) -> Message:
        """
        生成回复
        
        Args:
            messages: 消息历史
            **kwargs: 额外参数
            
        Returns:
            Message: AI回复消息
        """
        pass
        
    @abstractmethod
    async def stream_generate(self,
                            messages: List[Message],
                            **kwargs) -> AsyncIterator[str]:
        """流式生成回复"""
        pass
        
    def count_tokens(self, text: str) -> int:
        """计算token数量 - 默认实现"""
        return len(text) // 4  # 粗略估算


class BaseTool(ABC):
    """工具基类"""
    
    def __init__(self, 
                 name: str,
                 description: str,
                 parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters
        
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        pass
        
    def validate_parameters(self, **kwargs) -> bool:
        """验证参数"""
        required_params = [
            key for key, value in self.parameters.items()
            if value.get("required", False)
        ]
        return all(param in kwargs for param in required_params)


# 避免循环导入，这里只定义接口
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .graph import Graph 