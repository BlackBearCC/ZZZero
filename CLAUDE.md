# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**ZZZero AI Agent Framework** 是一个基于节点编排的智能代理框架，采用 StateGraph 设计理念，支持多种 Agent 范式、MCP 工具集成和批量任务处理。

### 重要工作指南
- 不使用复杂变量名，保持变量名通用易用无需特别适用_精确细分
- 永远使用中文交流
- 所有I/O密集型操作必须使用 async/await 实现
- 所有数据模型必须使用 Pydantic 进行类型定义
- 配置通过 .env 文件管理，禁止硬编码敏感信息
- 新功能必须继承自 src/core/base.py 中的相应基类

## 开发环境

### 依赖安装
```bash
pip install -r requirements.txt
```

### 数据库启动
```bash
./start_database.sh  # Linux/Mac
start_database.bat   # Windows
```

### 启动应用
```bash
python3 main.py
```

### 测试命令
```bash
pytest tests/              # 运行所有测试
pytest tests/ -v           # 详细输出
pytest-asyncio            # 异步测试支持
```

### 代码规范检查
```bash
black src/ tests/          # 代码格式化
flake8 src/ tests/         # 代码风格检查
mypy src/                  # 类型检查
```

## 核心架构

### StateGraph执行引擎
项目核心是基于状态字典的图执行引擎，支持：
- **条件路由**: 基于表达式、函数或模式匹配的智能路由
- **并行执行**: 多节点并行处理，支持多种聚合策略
- **循环控制**: while循环和最大循环次数限制
- **错误处理**: 完善的异常处理和重试机制

### 关键文件和目录结构

#### 核心模块 (`src/core/`)
- `graph.py`: StateGraph执行引擎，项目的核心执行逻辑
- `types.py`: 使用Pydantic的完整类型定义体系
- `base.py`: 所有节点、Agent、LLM的基类定义
- `batch_processor.py`: 批量任务处理器，支持并行/串行执行

#### 智能体系统 (`src/agents/`)
- `react_agent.py`: 标准React Agent实现，支持思考-行动-观察循环

#### 节点系统 (`src/nodes/`)
- `router_node.py`: 路由节点，支持条件路由和循环控制
- `parallel_node.py`: 并行节点，支持多种聚合策略
- `react_agent_node.py`: React代理节点
- `stream_react_agent_node.py`: 流式React代理节点

#### LLM集成 (`src/llm/`)
- `base.py`: LLM基类和工厂模式实现
- `openai.py`: OpenAI接口实现
- 支持 OpenAI、Anthropic、豆包等多种LLM提供商

#### 工具集成 (`src/tools/`)
- `mcp_tools.py`: MCP工具管理器，直接调用服务器实例

#### Web界面 (`src/web/`)
- `app.py`: 基于Gradio的主应用入口
- `components/`: 模块化UI组件
- `handlers/`: 事件处理器

#### MCP服务器生态 (`mcp_servers/`)
- `python_executor_server.py`: 安全的Python代码执行环境
- `csv_crud_server.py`: CSV文件操作服务
- `chromadb_crud_server.py`: 向量数据库服务
- `role_info_crud_server.py`: 角色信息管理服务

#### 数据库系统 (`database/`)
- `db_service.py`: PostgreSQL数据库服务管理
- `managers/`: 各种数据管理器（角色、剧情、日程等）
- `init/01-init-database.sql`: 数据库初始化脚本

#### 工作空间管理 (`workspace/`)
- `input/`: 用户输入文件存储
- `output/`: Agent生成结果存储
- `vectordb/`: ChromaDB向量数据库文件
- 各种专业化输出目录：story_output、schedule_output等

### 设计模式应用
- **工厂模式**: LLMFactory用于创建不同LLM实例
- **策略模式**: 不同Agent和Parser实现
- **模板方法**: BaseNode定义执行流程模板
- **建造者模式**: GraphBuilder构建执行图

## 开发指南

### BaseNode 核心钩子函数API
BaseNode 提供三个核心钩子函数，简化节点开发流程：

#### 1. `prompt()` - 构建提示词
```python
# 基本用法
prompt_text = self.prompt("请分析: {content}", content=data)

# 支持复杂变量替换
prompt_text = self.prompt(
    "角色: {role}\n任务: {task}\n数据: {data}",
    role="分析师", task="数据分析", data=input_data
)
```

#### 2. `astream()` - 异步流式LLM调用
```python
# 流式调用LLM
async for chunk in self.astream(prompt_text, mode="think", ui_handler=ui):
    think_content = chunk["think"]      # 思考过程
    final_content = chunk["content"]    # 最终内容
    chunk_count = chunk["chunk_count"]  # 块计数
```

#### 3. `parse()` - 智能内容解析
```python
# JSON解析（默认）
result = self.parse(llm_response, format_type="json")

# YAML解析
result = self.parse(llm_response, format_type="yaml")

# 结构化文本解析
result = self.parse(llm_response, format_type="structured")
```

### 完整节点开发示例
```python
from src.core.base import BaseNode
from src.core.types import NodeType

class DataAnalysisNode(BaseNode):
    def __init__(self, name: str, llm):
        super().__init__(name, NodeType.CUSTOM, llm=llm)
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 构建提示词
        prompt_text = self.prompt("""
        请分析以下数据：{data}
        输出JSON格式：{{"analysis": "分析结果", "confidence": 0.95}}
        """, data=state.get("input_data"))
        
        # 2. 流式调用LLM
        final_result = None
        async for chunk in self.astream(prompt_text, mode="think"):
            final_result = chunk["content"]
        
        # 3. 解析响应
        parsed_result = self.parse(final_result, format_type="json")
        
        # 4. 返回状态更新
        return {
            "analysis_result": parsed_result,
            "processed": True
        }
```

### 信息流系统
BaseNode 集成全局信息流系统，用于实时监控和调试：
```python
# 发射自定义事件
self.emit_info("processing", "开始数据处理", {"input_size": len(data)})
self.emit_info("result", "处理完成", {"output_size": len(result)})

# 添加全局事件监听
info_stream = NodeInfoStream()
info_stream.add_callback(lambda event: print(f"事件: {event}"))
```

### 创建新节点（简化版）
```python
from src.core.base import BaseNode
from src.core.types import NodeType

class CustomNode(BaseNode):
    def __init__(self, name: str, llm=None):
        super().__init__(name, NodeType.CUSTOM, llm=llm)
        
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # 使用钩子函数API实现逻辑
        prompt = self.prompt("处理: {input}", input=state.get("data"))
        
        result_content = ""
        async for chunk in self.astream(prompt):
            result_content = chunk["content"]
        
        parsed = self.parse(result_content, format_type="json")
        return {"result": parsed}
```

### 创建新Agent
```python
from src.core.base import BaseAgent
from src.core.graph import GraphBuilder

class CustomAgent(BaseAgent):
    def build_graph(self) -> Graph:
        builder = GraphBuilder("custom_graph")
        return (builder
            .add_node(node1)
            .connect("node1", "node2")
            .entry("node1")
            .exit("node2")
            .build()
        )
```

### 使用MCP工具
Agent优先使用项目封装的MCP工具进行文件操作：
- `list_input_files`: 列出输入文件
- `write_output_file`: 写入输出文件
- 避免直接使用os或Path库

### 文件和目录放置规则
- 新节点 → `src/nodes/`
- 新Agent → `src/agents/`
- 新LLM对接 → `src/llm/`
- 新MCP服务器 → `mcp_servers/`
- 新工作流 → `src/workflow/`
- 测试文件 → `tests/`
- 使用示例 → `examples/`

### 环境配置 (.env)
```env
# LLM API密钥
OPENAI_API_KEY=your_openai_key
ARK_API_KEY=your_doubao_key
ANTHROPIC_API_KEY=your_anthropic_key

# 数据库配置
SQLITE_DB_PATH=./workspace/database/zzzero.db

# MCP服务器配置
MCP_SERVER_URL=http://localhost:3000
```

## 核心特性

### 1. BaseNode 钩子函数架构
- **prompt()**: 智能提示词构建，支持变量替换和模板格式化
- **astream()**: 异步流式LLM调用，支持思考模式和实时UI更新
- **parse()**: 多格式内容解析（JSON/YAML/结构化文本），集成专门的解析器
- **emit_info()**: 全局信息流系统，实时事件监控和调试

### 2. 高级节点类型
- **RouterNode**: 条件路由和循环控制
- **ParallelNode**: 并行执行，支持all/first/majority策略
- **FinalizeNode**: 智能生成最终答案和执行摘要

### 3. 流式处理
- 支持实时流式输出和状态更新
- `stream_react_agent_node.py` 提供流式Agent实现

### 4. Python代码执行
- 安全的虚拟环境隔离
- 自动依赖检测和安装
- 危险代码检测和阻止
- 执行历史记录和审计

### 5. 批量任务处理
- 支持CSV批量输入
- 并行/串行处理模式选择
- 实时进度监控和结果导出

### 6. 多模态工作流
- 图像识别处理
- 剧情生成系统
- 智能日程规划
- 数据分析和处理

## 性能和监控

### 执行轨迹可视化
- 实时状态监控
- Mermaid流程图自动生成
- 详细的执行指标和统计

### 错误处理
- 完善的异常处理机制
- 自动重试策略
- 详细的错误日志记录

## StateGraph和Node调用细节

### StateGraph执行流程
1. **图构建**: 使用StateGraph类构建工作流图，定义节点间的连接关系
2. **节点添加**: 通过`add_node(name, node_instance)`添加节点到图中
3. **连接定义**: 使用`add_edge()`或`add_conditional_edges()`定义节点连接和路由
4. **执行入口**: 通过`set_entry_point(node_name)`设置图的执行起点
5. **图编译**: 使用`graph.compile()`编译为可执行图
6. **图执行**: 通过`compiled_graph.invoke(state)`执行整个图

### Graph运行机制
- **StateGraphExecutor**: 图执行器，负责按图结构迭代执行节点
- **状态管理**: 维护全局状态字典，节点通过返回字典更新状态
- **路由决策**: 根据节点返回值或条件函数确定下一个执行节点
- **并行支持**: 支持并行执行多个独立节点，然后合并结果

### BaseNode在Graph中的角色
- **封装LLM调用**: Node内部封装LLM交互逻辑，不直接执行
- **状态转换**: Node处理输入状态，返回状态更新字典
- **被动调用**: Node由Graph执行器调用，自身不主动执行
- **流式支持**: Node可选择性支持流式输出，由Graph协调流式执行

#### Node的核心职责
```python
class CustomNode(BaseNode):
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 使用钩子函数处理LLM交互
        prompt = self.prompt("处理: {input}", input=state.get("data"))
        
        result_content = ""
        async for chunk in self.astream(prompt):
            result_content = chunk["content"]
        
        parsed = self.parse(result_content, format_type="json")
        
        # 2. 返回状态更新，由Graph管理状态合并
        return {"processed_data": parsed, "step_completed": True}
```

### 错误处理器集成
- **execute_with_retry()**: 错误处理器的核心方法
- **参数传递**: 必须将state作为第一个参数传递给节点的run()方法
- **重试机制**: 支持自动重试和断路器模式
- **错误恢复**: 提供跳过、重试、回退等错误处理策略

### 最佳实践
```python
# 正确的节点实现 - Node专注于状态转换
class DataProcessNode(BaseNode):
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Node内部封装LLM调用，使用钩子函数
        prompt = self.prompt("分析数据: {data}", data=state.get('input'))
        
        result = ""
        async for chunk in self.astream(prompt):
            result = chunk["content"]
        
        parsed = self.parse(result, format_type="json")
        
        # 返回状态更新，不执行自身
        return {'analysis': parsed, 'processed': True}

# 正确的图构建和执行
graph = StateGraph('workflow')
graph.add_node('process', DataProcessNode('process'))
graph.set_entry_point('process')

# Graph负责执行和协调
compiled_graph = graph.compile()
result = await compiled_graph.invoke({'input': 'data'})
```