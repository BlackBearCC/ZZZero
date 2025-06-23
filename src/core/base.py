"""
核心基类定义 - 定义框架的抽象接口
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Type, TypeVar, Generic, AsyncIterator
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
    
    @property
    def is_success(self) -> bool:
        """检查是否执行成功"""
        return self.state == ExecutionState.SUCCESS
    
    @property
    def is_failed(self) -> bool:
        """检查是否执行失败"""
        return self.state == ExecutionState.FAILED
    
    def raise_if_failed(self):
        """如果执行失败则抛出异常 - 用于需要严格异常处理的场景"""
        if self.is_failed:
            raise RuntimeError(f"节点 {self.node_name} 执行失败: {self.error}")
    
    def get_error_summary(self) -> str:
        """获取错误摘要(不包含堆栈跟踪)"""
        if not self.error:
            return ""
        return self.error.split("\n堆栈跟踪:")[0]


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
    
    def parse_tool_arguments(self, tool_input: str) -> Dict[str, Any]:
        """
        通用工具参数解析方法 - 支持多种格式
        
        Args:
            tool_input: 工具输入字符串
            
        Returns:
            Dict[str, Any]: 解析后的参数字典
        """
        if not tool_input or not tool_input.strip():
            return {}
        
        tool_input = tool_input.strip()
        
        # 1. 尝试解析JSON格式
        try:
            import json
            # 检查是否是JSON对象格式
            if tool_input.startswith('{') and tool_input.endswith('}'):
                return json.loads(tool_input)
            # 检查是否是JSON数组格式
            elif tool_input.startswith('[') and tool_input.endswith(']'):
                return {"items": json.loads(tool_input)}
        except (json.JSONDecodeError, ValueError):
            pass
        
        # 2. 尝试解析键值对格式 (key=value, key2=value2 或换行分隔)
        try:
            if '=' in tool_input:
                arguments = {}
                # 支持逗号或换行分隔
                separators = [',', '\n', ';']
                lines = tool_input
                for sep in separators:
                    if sep in lines:
                        lines = lines.replace(sep, '\n')
                        break
                
                for line in lines.split('\n'):
                    line = line.strip()
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')  # 去除引号
                        
                        # 尝试智能类型转换
                        if value.lower() in ['true', 'false']:
                            arguments[key] = value.lower() == 'true'
                        elif value.isdigit():
                            arguments[key] = int(value)
                        elif '.' in value and value.replace('.', '').isdigit():
                            arguments[key] = float(value)
                        elif value.startswith('[') and value.endswith(']'):
                            # 尝试解析为列表
                            try:
                                import json
                                arguments[key] = json.loads(value)
                            except:
                                arguments[key] = value
                        else:
                            arguments[key] = value
                
                if arguments:
                    return arguments
        except Exception:
            pass
        
        # 3. 尝试解析YAML风格的键值对
        try:
            if ':' in tool_input and '\n' in tool_input:
                import re
                arguments = {}
                lines = tool_input.split('\n')
                for line in lines:
                    line = line.strip()
                    if ':' in line and not line.startswith('#'):
                        match = re.match(r'^([^:]+):\s*(.*)$', line)
                        if match:
                            key = match.group(1).strip()
                            value = match.group(2).strip().strip('"\'')
                            
                            # 智能类型转换
                            if value.lower() in ['true', 'false']:
                                arguments[key] = value.lower() == 'true'
                            elif value.isdigit():
                                arguments[key] = int(value)
                            elif '.' in value and value.replace('.', '').isdigit():
                                arguments[key] = float(value)
                            else:
                                arguments[key] = value
                
                if arguments:
                    return arguments
        except Exception:
            pass
        
        # 4. 默认处理：包装为input参数
        return {"input": tool_input}
        
    async def run(self, input_data: NodeInput, raise_on_error: bool = False) -> NodeResult:
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
            # 记录详细的异常信息，包含堆栈跟踪
            import traceback
            result.state = ExecutionState.FAILED
            result.error = f"{str(e)}\n堆栈跟踪:\n{traceback.format_exc()}"
            result.end_time = datetime.now()
            
            # 记录异常日志
            print(f"节点 {self.name} 执行失败: {e}")
            print(f"详细错误: {result.error}")
            
            # 根据参数决定是否抛出异常
            if raise_on_error:
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
        
    async def _build_system_prompt(self, query: Optional[str] = None) -> str:
        """构建系统提示（支持记忆上下文、角色插件和推理增强）"""
        base_prompt = ""
        
        # 添加角色插件上下文
        if hasattr(self, 'tool_manager') and self.tool_manager and hasattr(self.tool_manager, 'role_plugin_manager'):
            try:
                role_plugin_manager = self.tool_manager.role_plugin_manager
                
                # 获取角色资料
                profile_available = (role_plugin_manager.profile_plugin.enabled and 
                                   role_plugin_manager.profile_plugin.profile is not None and 
                                   bool(role_plugin_manager.profile_plugin.profile.content.strip()))
                if profile_available:
                    role_profile = await role_plugin_manager.profile_plugin.get_data()
                    if role_profile:
                        base_prompt += f"""=== 角色设定 ===
{role_profile}

"""
                
                # 获取角色知识库（如果有查询关键词）
                kb_available = (role_plugin_manager.knowledge_base_plugin.enabled and 
                               role_plugin_manager.knowledge_base_plugin.knowledge_base is not None)
                if query and kb_available:
                    # 提取关键词
                    import re
                    words = re.findall(r'\b\w+\b', query)
                    keywords = [word for word in words if len(word) > 2][:3]
                    
                    if keywords:
                        knowledge_results = await role_plugin_manager.knowledge_base_plugin.get_data(keywords=keywords)
                        if knowledge_results:
                            knowledge_content = "\n".join([
                                f"- {item['keyword']}: {item['content']}"
                                for item in knowledge_results
                            ])
                            base_prompt += f"""=== 角色专属知识 ===
{knowledge_content}

"""
            except Exception as e:
                print(f"获取角色插件上下文失败: {e}")
        
        # 添加记忆上下文
        if (hasattr(self, 'memory_enabled') and self.memory_enabled and 
            hasattr(self, 'memory_manager') and self.memory_manager and query):
            try:
                memory_context = await self.memory_manager.get_context_for_query(query, max_entries=5)
                if memory_context:
                    base_prompt += f"""=== 记忆上下文 ===
{memory_context}

"""
            except Exception as e:
                print(f"获取记忆上下文失败: {e}")
        
        # 检查是否支持推理功能
        has_reasoning = (hasattr(self, 'llm') and self.llm and 
                        (hasattr(self.llm, 'think') or hasattr(self.llm, 'stream_think')))
        
        # 检查是否有工具可用
        if hasattr(self, 'tool_manager') and self.tool_manager and self.tool_manager.list_tools():
            # 获取工具描述
            tools_desc = self.tool_manager.get_tools_description()
            tool_names = self.tool_manager.list_tools()
            
            base_prompt += f"""你是一个基于ReAct（Reasoning and Acting）范式的智能助手，具有记忆能力。"""
            
            # 如果支持推理功能，添加推理能力说明
            if has_reasoning:
                base_prompt += """

*推理增强模式已激活*
你具备强大的逻辑推理能力，能够：
- 深度分析复杂问题
- 进行多步骤逻辑推导
- 自我验证和反思
- 优化工具选择和使用策略"""

            base_prompt += f"""

可用工具：
{tools_desc}

必须使用以下格式进行推理和行动：

Question: 你需要回答的问题
Thought: 分析Question，你永远知道下一步要做什么
Action: 要采取的行动，应该是 [{', '.join(tool_names)}] 中的一个
Action Input: 行动的输入
Observation: 行动的结果
... (这个 Thought/Action/Action Input/Observation 可以重复N次，直到你认为你已经得到了最终答案)
Final Answer: 对原始问题的最终答案

重要规则：
1. 如果你有足够信息回答问题，直接给出 Final Answer
2. 如果需要更多信息，使用可用的工具
3. 每次只使用一个工具
4. 仔细分析工具的返回结果
5. 利用记忆上下文中的相关信息
6. 注意保持对话的连贯性"""

            # 如果支持推理功能，添加推理相关规则
            if has_reasoning:
                base_prompt += """
7. 充分利用推理能力深度分析问题
8. 在选择工具前进行充分的逻辑推导
9. 对工具结果进行批判性思考和验证
10. 基于推理结果优化后续行动策略"""

            base_prompt += "\n\n开始！"
        else:
            # 没有工具时的提示
            base_prompt += """你是一个智能助手，具有记忆能力。"""
            
            # 如果支持推理功能，强调推理能力
            if has_reasoning:
                base_prompt += """

*推理增强模式已激活*
你具备强大的逻辑推理能力，能够：
- 深度分析复杂问题
- 进行多步骤逻辑推导
- 自我验证和反思
- 提供更准确和全面的答案

由于当前没有可用的外部工具，你需要充分发挥推理优势："""
            else:
                base_prompt += """

由于当前没有可用的外部工具，你需要："""

            base_prompt += """
1. 仔细分析用户的问题
2. 基于你的知识库和记忆上下文提供最佳答案
3. 如果无法确定答案，诚实地说明情况
4. 提供清晰、有帮助的回复
5. 保持对话的连贯性和个性化"""

            if has_reasoning:
                base_prompt += """
6. 运用逻辑推理能力深入思考问题
7. 进行多角度分析和验证
8. 基于推理结果给出最优解答"""

            base_prompt += """

请保持友好、专业的态度回答用户问题。"""
        
        return base_prompt
        
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