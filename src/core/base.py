"""
核心基类定义 - 基于LangGraph设计理念重构
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Type, TypeVar, Generic, AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from enum import Enum

from pydantic import BaseModel
from .types import (
    NodeInput, NodeOutput, ExecutionContext, Message, 
    ToolCall, AgentType, NodeType, TaskResult, MessageRole
)


T = TypeVar('T')


class ExecutionState(str, Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Command:
    """命令对象 - 用于同时更新状态和控制流程"""
    def __init__(self, 
                 update: Optional[Dict[str, Any]] = None,
                 goto: Optional[Union[str, List[str]]] = None):
        self.update = update or {}
        self.goto = goto
    
    def __str__(self):
        return f"Command(update={self.update}, goto={self.goto})"


@dataclass
class NodeResult:
    """节点执行结果"""
    node_name: str
    node_type: NodeType
    state_update: Dict[str, Any]
    execution_state: ExecutionState
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """计算执行时长(秒)"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def is_success(self) -> bool:
        """检查是否执行成功"""
        return self.execution_state == ExecutionState.SUCCESS
    
    @property
    def is_failed(self) -> bool:
        """检查是否执行失败"""
        return self.execution_state == ExecutionState.FAILED


class BaseNode(ABC):
    """节点基类 - 基于LangGraph设计理念
    
    核心改进：
    1. 节点函数接收完整状态字典作为输入
    2. 返回状态更新字典（而不是复杂的NodeOutput）
    3. 支持返回Command对象进行流程控制
    4. 简化的执行接口
    """
    
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
    async def execute(self, state: Dict[str, Any]) -> Union[Dict[str, Any], Command]:
        """
        执行节点逻辑 - 基于LangGraph设计
        
        Args:
            state: 当前图状态字典
            
        Returns:
            Union[Dict[str, Any], Command]: 
            - Dict: 状态更新字典，会被合并到当前状态
            - Command: 同时包含状态更新和流程控制的命令对象
        """
        pass
        
    async def pre_execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行前钩子 - 可以修改状态"""
        return state
        
    async def post_execute(self, state_update: Dict[str, Any]) -> Dict[str, Any]:
        """执行后钩子 - 可以修改状态更新"""
        return state_update
    
    async def run(self, state: Dict[str, Any]) -> NodeResult:
        """执行节点并返回结果"""
        result = NodeResult(
            node_name=self.name,
            node_type=self.node_type,
            state_update={},
            execution_state=ExecutionState.RUNNING
        )
        
        try:
            # 执行前钩子
            state = await self.pre_execute(state)
            
            # 执行核心逻辑
            output = await self.execute(state)
            
            # 处理返回结果
            if isinstance(output, Command):
                result.state_update = output.update
                result.metadata["command"] = output
            elif isinstance(output, dict):
                result.state_update = output
            else:
                raise ValueError(f"节点 {self.name} 返回了无效的输出类型: {type(output)}")
            
            # 执行后钩子
            result.state_update = await self.post_execute(result.state_update)
            
            result.execution_state = ExecutionState.SUCCESS
            
        except Exception as e:
            result.execution_state = ExecutionState.FAILED
            result.error = str(e)
            
        finally:
            result.end_time = datetime.now()
            
        return result
    
    def get_state_value(self, state: Dict[str, Any], key: str, default: Any = None) -> Any:
        """安全获取状态值"""
        return state.get(key, default)
    
    def get_messages(self, state: Dict[str, Any]) -> List[Message]:
        """获取消息列表"""
        return self.get_state_value(state, "messages", [])
    
    def add_message(self, state_update: Dict[str, Any], message: Message):
        """添加消息到状态更新"""
        if "messages" not in state_update:
            state_update["messages"] = []
        state_update["messages"].append(message)
    
    def create_ai_message(self, content: str) -> Message:
        """创建AI消息"""
        return Message(role=MessageRole.ASSISTANT, content=content)
    
    def create_user_message(self, content: str) -> Message:
        """创建用户消息"""
        return Message(role=MessageRole.USER, content=content)


class BaseAgent(ABC):
    """Agent基类 - 基于StateGraph的智能代理"""
    
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
        """运行Agent"""
        pass
        
    @abstractmethod
    def build_graph(self) -> "StateGraph":
        """构建StateGraph"""
        pass
        
    async def initialize(self):
        """初始化Agent"""
        pass
        
    async def cleanup(self):
        """清理资源"""
        pass


class BaseExecutor(ABC):
    """执行器基类 - 基于StateGraph"""
    
    @abstractmethod
    async def execute(self, 
                     graph: "StateGraph", 
                     initial_state: Dict[str, Any],
                     config: Dict[str, Any]) -> Dict[str, Any]:
        """执行StateGraph"""
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