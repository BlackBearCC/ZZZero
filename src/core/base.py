"""
简化的核心基类定义 - 基于钩子函数API设计
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import sqlite3
import json
import os
from enum import Enum

from .types import (
    NodeInput, NodeOutput, ExecutionContext, Message, 
    ToolCall, AgentType, NodeType, TaskResult, MessageRole
)

# 为了避免循环导入，使用TYPE_CHECKING
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..llm.base import ThinkResult, BaseLLMProvider
else:
    try:
        from ..llm.base import ThinkResult, BaseLLMProvider
    except ImportError:
        ThinkResult = Any
        BaseLLMProvider = Any


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
        
    def clear_events(self):
        """清空事件历史"""
        self.events.clear()


class BaseNode(ABC):
    """简化的节点基类 - 基于钩子函数API设计
    
    核心钩子函数：
    1. node.prompt(template, **kwargs) - 构建提示词
    2. node.astream(prompt, mode, ui_handler) - 异步流式LLM调用
    3. node.parse(content, format_type) - 解析响应内容
    """
    
    def __init__(self, 
                 name: str,
                 node_type: NodeType = NodeType.CUSTOM,
                 description: Optional[str] = None,
                 llm: Optional['BaseLLMProvider'] = None,
                 stream: bool = True,
                 enable_recording: bool = True,
                 **kwargs):
        self.name = name
        self.node_type = node_type
        self.description = description
        self.stream = stream
        self.enable_recording = enable_recording
        self.config = kwargs
        self.llm = llm
        self.info_stream = NodeInfoStream()
        
        # 记录相关属性
        self._execution_start_time = None
        self._execution_input_data = None
        self._execution_output_data = None
        self._node_results = []
        self._graph_name = None
        
    def set_graph_context(self, graph_name: str, input_data: Dict[str, Any]):
        """设置图执行上下文"""
        self._graph_name = graph_name
        self._execution_input_data = input_data.copy()
        self._execution_start_time = datetime.now()
        
    def add_node_result(self, result_data: Dict[str, Any]):
        """添加节点执行结果"""
        self._node_results.append({
            "node_name": self.name,
            "timestamp": datetime.now().isoformat(),
            "result": result_data
        })
        
    def _record_execution(self, output_data: Dict[str, Any], success: bool = True, error_message: str = None):
        """记录执行结果到SQLite"""
        if not self.enable_recording or not self._graph_name:
            return
            
        try:
            recorder = get_graph_recorder()
            recorder.record_execution(
                graph_name=self._graph_name,
                input_data=self._execution_input_data or {},
                output_result=output_data,
                node_results=self._node_results,
                start_time=self._execution_start_time or datetime.now(),
                end_time=datetime.now(),
                success=success,
                error_message=error_message
            )
        except Exception as e:
            print(f"[BaseNode] 记录执行结果失败: {e}")
        
    def emit_info(self, event_type: str, content: str, metadata: Dict[str, Any] = None):
        """发射节点信息到信息流"""
        self.info_stream.emit(event_type, self.name, content, metadata)
        
        # 如果是重要事件，记录到节点结果中
        if event_type in ["start", "complete", "error", "fatal_error"]:
            self.add_node_result({
                "event_type": event_type,
                "content": content,
                "metadata": metadata or {}
            })
        
    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> Union[Dict[str, Any], Command]:
        """执行节点逻辑"""
        pass
    
    async def run(self, state: Dict[str, Any]) -> NodeResult:
        """运行节点并返回NodeResult"""
        start_time = datetime.now()
        
        # 设置图执行上下文
        if '_graph_name' in state:
            self.set_graph_context(state['_graph_name'], state)
        
        try:
            result = await self.execute(state)
            end_time = datetime.now()
            
            # 如果返回的是Command，提取状态更新
            if isinstance(result, Command):
                state_update = result.update
                metadata = {"command": result}
            else:
                state_update = result if isinstance(result, dict) else {}
                metadata = {}
            
            # 记录成功执行
            if self.enable_recording:
                self._record_execution(state_update, success=True)
            
            return NodeResult(
                node_name=self.name,
                node_type=self.node_type,
                state_update=state_update,
                execution_state=ExecutionState.SUCCESS,
                start_time=start_time,
                end_time=end_time,
                metadata=metadata
            )
            
        except Exception as e:
            end_time = datetime.now()
            
            # 记录失败执行
            if self.enable_recording:
                self._record_execution({}, success=False, error_message=str(e))
            
            return NodeResult(
                node_name=self.name,
                node_type=self.node_type,
                state_update={},
                execution_state=ExecutionState.FAILED,
                start_time=start_time,
                end_time=end_time,
                error=str(e)
            )
    
    async def execute_stream(self, state: Dict[str, Any]):
        """流式执行节点逻辑"""
        if not self.stream:
            result = await self.execute(state)
            yield result
        else:
            result = await self.execute(state)
            yield result
    
    async def run_stream(self, state: Dict[str, Any]):
        """流式运行节点并返回NodeResult"""
        start_time = datetime.now()
        
        # 设置图执行上下文
        if '_graph_name' in state:
            self.set_graph_context(state['_graph_name'], state)
        
        try:
            final_result = None
            async for result in self.execute_stream(state):
                final_result = result
                # 对于中间结果，也包装成NodeResult格式
                if isinstance(result, Command):
                    state_update = result.update
                    metadata = {"command": result}
                else:
                    state_update = result if isinstance(result, dict) else {}
                    metadata = {}
                
                yield NodeResult(
                    node_name=self.name,
                    node_type=self.node_type,
                    state_update=state_update,
                    execution_state=ExecutionState.SUCCESS,
                    start_time=start_time,
                    end_time=datetime.now(),
                    metadata=metadata
                )
            
            # 记录最终成功执行
            if self.enable_recording and final_result:
                final_state = final_result if isinstance(final_result, dict) else {}
                self._record_execution(final_state, success=True)
            
        except Exception as e:
            end_time = datetime.now()
            
            # 记录失败执行
            if self.enable_recording:
                self._record_execution({}, success=False, error_message=str(e))
            
            yield NodeResult(
                node_name=self.name,
                node_type=self.node_type,
                state_update={},
                execution_state=ExecutionState.FAILED,
                start_time=start_time,
                end_time=end_time,
                error=str(e)
            )
    
    # ==================== 核心钩子函数API ====================
    
    def prompt(self, template: str, **kwargs) -> str:
        """钩子函数 - 构建提示词"""
        try:
            if '{' in template and '}' in template:
                return template.format(**kwargs)
            else:
                return template
        except KeyError as e:
            raise ValueError(f"提示词模板缺少变量: {e}")
        except Exception as e:
            raise ValueError(f"提示词构建失败: {e}")
    
    async def astream(self, 
                     prompt: str,
                     mode: str = "think",
                     ui_handler=None,
                     **kwargs):
        """钩子函数 - 异步流式LLM调用"""
        if not self.llm:
            raise ValueError(f"节点 {self.name} 未配置LLM")
        
        message = Message(role=MessageRole.USER, content=prompt)
        messages = [message]
        
        chunk_count = 0
        think_content = ""
        final_content = ""
        
        try:
            async for chunk_data in self.llm.stream_generate(
                messages, 
                mode=mode,
                return_dict=True,
                **kwargs
            ):
                chunk_count += 1
                
                think_part = chunk_data.get("think", "")
                content_part = chunk_data.get("content", "")
                
                think_content += think_part
                final_content += content_part
                
                # 实时UI更新
                if ui_handler:
                    await self._update_ui_streaming(ui_handler, think_content, final_content)
                
                yield {
                    "think": think_content,
                    "content": final_content,
                    "chunk_count": chunk_count,
                    "current_think": think_part,
                    "current_content": content_part
                }
                
        except Exception as e:
            if ui_handler:
                await ui_handler.add_node_message(
                    self.name,
                    f"❌ LLM调用失败: {str(e)}",
                    "error"
                )
            raise Exception(f"LLM流式调用失败: {str(e)}")
    
    def parse(self, content: str, format_type: str = "json", **kwargs) -> Any:
        """钩子函数 - 解析响应内容"""
        if format_type == "json":
            return self._parse_json_enhanced(content, **kwargs)
        elif format_type == "yaml":
            return self._parse_yaml(content, **kwargs)
        elif format_type == "structured":
            return self._parse_structured(content, **kwargs)
        else:
            raise ValueError(f"不支持的解析格式: {format_type}")
    
    # ==================== 内部辅助方法 ====================
    
    async def _update_ui_streaming(self, ui_handler, think_content: str, final_content: str):
        """内部方法 - 更新流式UI"""
        try:
            display_content = ""
            if think_content.strip():
                display_content += f"""
<div style="background: #f8f9fa; border-left: 4px solid #6c757d; padding: 10px; margin: 10px 0; border-radius: 4px;">
🤔 思考过程：<br>
{think_content}
</div>"""
            
            if final_content.strip():
                display_content += f"""
<div style="background: #e8f5e9; border-left: 4px solid #28a745; padding: 10px; margin: 10px 0; border-radius: 4px;">
✨ 生成内容：<br>
{final_content}
</div>"""
            
            await ui_handler.add_node_message(
                self.name,
                display_content,
                "streaming"
            )
        except Exception:
            pass
    
    def _parse_json_enhanced(self, content: str, **kwargs) -> Dict[str, Any]:
        """增强的JSON解析 - 使用专门的JSONParser工具类"""
        from ..parsers.json_parser import JSONParser
        
        # 创建JSON解析器实例，允许部分匹配和非严格模式
        parser = JSONParser(strict=False, allow_partial=True)
        
        try:
            return parser.parse(content)
        except ValueError as e:
            # 如果解析失败，提供更详细的错误信息
            raise ValueError(f"JSON解析失败: {str(e)} (内容: {content[:200]}...)")
    
    
    def _parse_yaml(self, text: str, **kwargs) -> Dict[str, Any]:
        """解析YAML"""
        try:
            import yaml
            return yaml.safe_load(text)
        except ImportError:
            raise ValueError("需要安装yaml库: pip install pyyaml")
        except Exception as e:
            raise ValueError(f"YAML解析失败: {e}")
    
    def _parse_structured(self, text: str, **kwargs) -> Dict[str, Any]:
        """结构化文本解析"""
        result = {}
        lines = text.split('\n')
        current_key = None
        current_value = []
        
        for line in lines:
            line = line.strip()
            if ':' in line and not line.startswith(' '):
                if current_key:
                    result[current_key] = '\n'.join(current_value).strip()
                
                key, value = line.split(':', 1)
                current_key = key.strip()
                current_value = [value.strip()] if value.strip() else []
            elif current_key and line:
                current_value.append(line)
        
        if current_key:
            result[current_key] = '\n'.join(current_value).strip()
        
        return result
    
    def set_llm(self, llm: 'BaseLLMProvider'):
        """设置LLM提供者"""
        self.llm = llm


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


class BaseExecutor(ABC):
    """执行器基类 - 基于StateGraph"""
    
    @abstractmethod
    async def execute(self, 
                     graph: "StateGraph", 
                     initial_state: Dict[str, Any],
                     config: Dict[str, Any]) -> Dict[str, Any]:
        """执行StateGraph"""
        pass


class BaseTool(ABC):
    """工具基类 - 所有工具必须实现此接口"""
    
    def __init__(self, 
                 name: str,
                 description: str,
                 parameters: Optional[Dict[str, Any]] = None):
        self.name = name
        self.description = description
        self.parameters = parameters or {}
        
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        pass
        
    def validate_parameters(self, **kwargs) -> bool:
        """验证参数"""
        # 检查必需参数
        for param_name, param_info in self.parameters.items():
            if param_info.get("required", False) and param_name not in kwargs:
                return False
        return True
        
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的JSON Schema"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class BaseLLM(ABC):
    """LLM基类 - 所有LLM提供者必须实现此接口"""
    
    @abstractmethod
    async def generate(self, 
                      messages: List[Message],
                      **kwargs) -> Message:
        """生成回复"""
        pass
        
    @abstractmethod
    async def stream_generate(self,
                            messages: List[Message],
                            **kwargs) -> AsyncIterator[str]:
        """流式生成回复"""
        pass


class GraphExecutionRecorder:
    """Graph执行记录器 - SQLite实现"""
    
    def __init__(self, db_path: str = "workspace/graph_executions.db"):
        self.db_path = db_path
        self._ensure_dir()
        self._init_db()
    
    def _ensure_dir(self):
        """确保数据库目录存在"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS graph_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    graph_name TEXT NOT NULL,
                    input_data TEXT NOT NULL,
                    output_result TEXT NOT NULL,
                    node_results TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds REAL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_graph_name ON graph_executions(graph_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_start_time ON graph_executions(start_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_success ON graph_executions(success)")
            conn.commit()
    
    def record_execution(self, 
                        graph_name: str,
                        input_data: Dict[str, Any],
                        output_result: Dict[str, Any],
                        node_results: List[Dict[str, Any]],
                        start_time: datetime,
                        end_time: datetime = None,
                        success: bool = True,
                        error_message: str = None) -> int:
        """记录graph执行结果"""
        end_time = end_time or datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO graph_executions 
                    (graph_name, input_data, output_result, node_results, 
                     start_time, end_time, duration_seconds, success, error_message, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    graph_name,
                    json.dumps(input_data, ensure_ascii=False, default=str),
                    json.dumps(output_result, ensure_ascii=False, default=str),
                    json.dumps(node_results, ensure_ascii=False, default=str),
                    start_time.isoformat(),
                    end_time.isoformat(),
                    duration,
                    success,
                    error_message,
                    datetime.now().isoformat()
                ))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"[GraphExecutionRecorder] 记录执行失败: {e}")
            return -1
    
    def get_recent_executions(self, graph_name: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的执行记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                if graph_name:
                    cursor = conn.execute("""
                        SELECT * FROM graph_executions 
                        WHERE graph_name = ? 
                        ORDER BY start_time DESC 
                        LIMIT ?
                    """, (graph_name, limit))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM graph_executions 
                        ORDER BY start_time DESC 
                        LIMIT ?
                    """, (limit,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"[GraphExecutionRecorder] 获取记录失败: {e}")
            return []


# 全局记录器实例
_global_recorder = None

def get_graph_recorder() -> GraphExecutionRecorder:
    """获取全局graph记录器实例"""
    global _global_recorder
    if _global_recorder is None:
        _global_recorder = GraphExecutionRecorder()
    return _global_recorder