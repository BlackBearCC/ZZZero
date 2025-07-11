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

# 为了避免循环导入，使用TYPE_CHECKING
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..llm.base import ThinkResult, BaseLLMProvider
else:
    # 运行时动态导入
    try:
        from ..llm.base import ThinkResult, BaseLLMProvider
    except ImportError:
        # 如果导入失败，定义临时类型
        ThinkResult = Any
        BaseLLMProvider = Any


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


class NodeInfoStream:
    """节点信息流系统 - 全局单例模式"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.events = []
            cls._instance.callbacks = []
        return cls._instance
    
    def emit(self, event_type: str, node_name: str, content: str, metadata: Dict[str, Any] = None):
        """发射事件到信息流"""
        event = {
            "type": event_type,
            "node_name": node_name,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        self.events.append(event)
        
        # 通知所有回调（异步处理）
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event))
                else:
                    callback(event)
            except Exception as e:
                print(f"[信息流错误] 回调处理失败: {e}")
    
    def add_callback(self, callback):
        """添加事件回调"""
        self.callbacks.append(callback)
        
    def remove_callback(self, callback):
        """移除事件回调"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
        
    def get_events(self) -> List[Dict[str, Any]]:
        """获取所有事件"""
        return self.events.copy()
        
    def clear_events(self):
        """清空事件历史"""
        self.events.clear()


class BaseNode(ABC):
    """节点基类 - 集成常用功能的智能节点
    
    集成功能：
    1. LLM调用 (node.llm.generate)
    2. 数据解析 (node.parse)
    3. 提示构建 (node.build_prompt)
    4. 向量搜索 (node.vector_search)
    5. 状态管理 (基于LangGraph设计)
    6. 信息流输出 (node.emit_info)
    """
    
    def __init__(self, 
                 name: str,
                 node_type: NodeType = NodeType.CUSTOM,
                 description: Optional[str] = None,
                 llm: Optional['BaseLLMProvider'] = None,
                 stream: bool = True,  # 默认启用流式执行
                 **kwargs):
        self.name = name
        self.node_type = node_type
        self.description = description
        self.stream = stream  # 是否支持流式执行
        self.config = kwargs
        
        # 集成的功能组件
        self.llm = llm
        self._vector_client = None
        self._parsers = {}
        self._prompt_templates = {}
        
        # 信息流系统
        self.info_stream = NodeInfoStream()
        
    def emit_info(self, event_type: str, content: str, metadata: Dict[str, Any] = None):
        """发射节点信息到信息流"""
        self.info_stream.emit(event_type, self.name, content, metadata)
        
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
    
    async def execute_stream(self, state: Dict[str, Any]):
        """
        流式执行节点逻辑 - 支持实时更新
        
        Args:
            state: 当前图状态字典
            
        Yields:
            Dict[str, Any]: 中间状态更新，用于实时反馈
        """
        # 默认实现：如果节点不支持流式，直接调用execute
        if not self.stream:
            result = await self.execute(state)
            yield result
        else:
            # 子类应该重写此方法来实现真正的流式执行
            # 如果子类没有重写execute_stream但开启了stream，
            # 则调用execute方法作为兜底
            result = await self.execute(state)
            yield result
        
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
            
            # 如果支持流式执行，使用流式执行并取最后结果
            if self.stream:
                last_output = None
                async for output in self.execute_stream(state):
                    last_output = output
                output = last_output
            else:
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
    
    async def run_stream(self, state: Dict[str, Any]):
        """流式执行节点并逐步返回结果"""
        try:
            # 执行前钩子
            state = await self.pre_execute(state)
            
            # 流式执行核心逻辑
            async for output in self.execute_stream(state):
                # 处理返回结果并yield中间状态
                intermediate_result = NodeResult(
                    node_name=self.name,
                    node_type=self.node_type,
                    state_update={},
                    execution_state=ExecutionState.SUCCESS  # 设置为SUCCESS
                )
                
                if isinstance(output, Command):
                    intermediate_result.state_update = output.update
                    intermediate_result.metadata["command"] = output
                elif isinstance(output, dict):
                    intermediate_result.state_update = output
                else:
                    # 对于无效输出，跳过此次yield
                    continue
                
                # 执行后钩子
                intermediate_result.state_update = await self.post_execute(intermediate_result.state_update)
                
                yield intermediate_result
                
        except Exception as e:
            # 发送错误结果
            error_result = NodeResult(
                node_name=self.name,
                node_type=self.node_type,
                state_update={},
                execution_state=ExecutionState.FAILED,
                error=str(e)
            )
            error_result.end_time = datetime.now()
            yield error_result
    
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
    
    # ==================== 集成功能方法 ====================
    
    async def generate(self, 
                      messages: List[Message], 
                      system_prompt: Optional[str] = None,
                      mode: str = "normal",
                      **kwargs) -> Message:
        """调用LLM生成回复
        
        Args:
            messages: 消息历史
            system_prompt: 系统提示（可选）
            mode: 生成模式，'normal' 或 'think'
            **kwargs: LLM参数
            
        Returns:
            Message: AI回复
        """
        if not self.llm:
            raise ValueError(f"节点 {self.name} 未配置LLM")
        
        # 准备消息列表
        llm_messages = messages.copy()
        
        # 添加系统提示
        if system_prompt and not any(msg.role == MessageRole.SYSTEM for msg in llm_messages):
            llm_messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ))
        
        return await self.llm.generate(llm_messages, mode=mode, **kwargs)
    
    async def stream_generate(self, 
                             messages: List[Message], 
                             system_prompt: Optional[str] = None,
                             mode: str = "normal",
                             **kwargs):
        """流式调用LLM生成回复
        
        Args:
            messages: 消息历史
            system_prompt: 系统提示（可选）
            mode: 生成模式，'normal' 或 'think'
            **kwargs: LLM参数
        """
        if not self.llm:
            raise ValueError(f"节点 {self.name} 未配置LLM")
        
        # 准备消息列表
        llm_messages = messages.copy()
        
        # 添加系统提示
        if system_prompt and not any(msg.role == MessageRole.SYSTEM for msg in llm_messages):
            llm_messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ))
        
        async for chunk in self.llm.stream_generate(llm_messages, mode=mode, **kwargs):
            yield chunk
    

    
    def parse(self, text: str, format_type: str = "json", **kwargs) -> Any:
        """解析文本数据
        
        Args:
            text: 要解析的文本
            format_type: 解析格式 (json, yaml, xml, regex, structured)
            **kwargs: 解析参数
            
        Returns:
            Any: 解析结果
        """
        if format_type == "json":
            return self._parse_json(text, **kwargs)
        elif format_type == "yaml":
            return self._parse_yaml(text, **kwargs)
        elif format_type == "xml":
            return self._parse_xml(text, **kwargs)
        elif format_type == "regex":
            return self._parse_regex(text, **kwargs)
        elif format_type == "structured":
            return self._parse_structured(text, **kwargs)
        else:
            raise ValueError(f"不支持的解析格式: {format_type}")
    
    def build_prompt(self, 
                    template_name: str, 
                    **variables) -> str:
        """构建提示词
        
        Args:
            template_name: 模板名称
            **variables: 模板变量
            
        Returns:
            str: 格式化的提示词
        """
        if template_name not in self._prompt_templates:
            # 如果没有找到模板，尝试从预设模板获取
            template = self._get_default_template(template_name)
            if not template:
                raise ValueError(f"未找到提示模板: {template_name}")
            self._prompt_templates[template_name] = template
        
        template = self._prompt_templates[template_name]
        return template.format(**variables)
    
    async def vector_search(self, 
                           query: str, 
                           collection_name: str = "default",
                           top_k: int = 5,
                           **kwargs) -> List[Dict[str, Any]]:
        """向量搜索
        
        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回结果数量
            **kwargs: 搜索参数
            
        Returns:
            List[Dict]: 搜索结果
        """
        if not self._vector_client:
            self._init_vector_client()
        
        if not self._vector_client:
            raise ValueError(f"节点 {self.name} 未配置向量数据库")
        
        # 调用向量搜索
        return await self._vector_client.search(
            query=query,
            collection_name=collection_name,
            top_k=top_k,
            **kwargs
        )
    
    def set_llm(self, llm: 'BaseLLMProvider'):
        """设置LLM提供者"""
        self.llm = llm
    
    def set_vector_client(self, client):
        """设置向量数据库客户端"""
        self._vector_client = client
    
    def add_prompt_template(self, name: str, template: str):
        """添加提示模板"""
        self._prompt_templates[name] = template
    
    def add_parser(self, name: str, parser):
        """添加自定义解析器"""
        self._parsers[name] = parser
    
    # ==================== 内部解析方法 ====================
    
    def _parse_json(self, text: str, **kwargs) -> Dict[str, Any]:
        """解析JSON"""
        import json
        import re
        
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取JSON块
        json_pattern = r'```json\s*\n(.*?)\n```'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试查找JSON对象
        json_pattern = r'\{.*\}'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"无法解析JSON: {text[:100]}...")
    
    def _parse_yaml(self, text: str, **kwargs) -> Dict[str, Any]:
        """解析YAML"""
        try:
            import yaml
            return yaml.safe_load(text)
        except ImportError:
            raise ValueError("需要安装yaml库: pip install pyyaml")
        except yaml.YAMLError as e:
            raise ValueError(f"YAML解析失败: {e}")
    
    def _parse_xml(self, text: str, **kwargs) -> Dict[str, Any]:
        """解析XML"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(text)
            return self._xml_to_dict(root)
        except ET.ParseError as e:
            raise ValueError(f"XML解析失败: {e}")
    
    def _parse_regex(self, text: str, pattern: str, **kwargs) -> Dict[str, Any]:
        """正则表达式解析"""
        import re
        match = re.search(pattern, text, **kwargs)
        if match:
            return match.groupdict() if match.groupdict() else {"match": match.group(0)}
        return {}
    
    def _parse_structured(self, text: str, **kwargs) -> Dict[str, Any]:
        """结构化文本解析"""
        result = {}
        lines = text.split('\n')
        current_key = None
        current_value = []
        
        for line in lines:
            line = line.strip()
            if ':' in line and not line.startswith(' '):
                # 保存前一个键值对
                if current_key:
                    result[current_key] = '\n'.join(current_value).strip()
                
                # 开始新的键值对
                key, value = line.split(':', 1)
                current_key = key.strip()
                current_value = [value.strip()] if value.strip() else []
            elif current_key and line:
                current_value.append(line)
        
        # 保存最后一个键值对
        if current_key:
            result[current_key] = '\n'.join(current_value).strip()
        
        return result
    
    def _xml_to_dict(self, element) -> Dict[str, Any]:
        """XML元素转字典"""
        result = {}
        
        # 处理属性
        if element.attrib:
            result.update(element.attrib)
        
        # 处理文本内容
        if element.text and element.text.strip():
            if len(element) == 0:
                return element.text.strip()
            result['text'] = element.text.strip()
        
        # 处理子元素
        for child in element:
            child_data = self._xml_to_dict(child)
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        
        return result
    
    def _get_default_template(self, template_name: str) -> Optional[str]:
        """获取默认模板"""
        default_templates = {
            "system": "你是一个专业的AI助手，请根据用户需求提供帮助。",
            "thought": """请分析当前问题并制定解决方案：

问题：{query}
可用工具：{tools}
历史信息：{context}

请提供：
1. 分析：对问题的理解
2. 策略：解决方案
3. 工具需求：是否需要使用工具
4. 信心评估：1-10分""",
            "action": """基于分析结果，请选择合适的工具并提供参数：

分析结果：{thought}
可用工具：{tools}

请选择工具并提供参数。""",
            "final_answer": """基于所有信息，请提供最终回答：

问题：{query}
分析过程：{thought}
工具结果：{observations}

请提供完整、准确的最终回答。"""
        }
        
        return default_templates.get(template_name)
    
    def _init_vector_client(self):
        """初始化向量数据库客户端"""
        try:
            # 尝试从工具管理器获取向量搜索功能
            from tools.mcp_tools import MCPToolManager
            # 这里可以根据实际情况初始化向量客户端
            pass
        except ImportError:
            pass


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