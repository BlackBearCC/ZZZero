# CLAUDE.md - 项目指南

## 项目概述

**ZZZero AI Agent Framework** 是一个基于节点编排的智能代理框架，采用 StateGraph 设计理念，支持多种 Agent 范式、MCP 工具集成和批量任务处理。

### 核心特性
- 🧠 **多种 Agent 范式**: ReAct、Chain of Thought、Plan-Execute 等
- 🔄 **节点式编排**: 灵活的工作流构建，支持条件路由和并行执行
- 🛠️ **MCP 工具集成**: 支持 Model Context Protocol 工具生态
- 🎯 **批量任务处理**: 高效的并行/串行任务执行
- 🌐 **ChatGPT 风格界面**: 基于 Gradio 的用户友好界面
- 📊 **强大的监控**: 实时执行跟踪和性能指标
- 🎨 **多格式可视化**: Mermaid、HTML、D3.js 等多种图表支持

## 项目结构

```
ZZZero/
├── src/                          # 源代码目录
│   ├── core/                     # 核心框架
│   │   ├── base.py              # 基类定义 (BaseNode, BaseAgent 等)
│   │   ├── types.py             # 类型定义 (Pydantic 模型)
│   │   ├── graph.py             # StateGraph 执行引擎
│   │   ├── executor.py          # 状态管理和执行器
│   │   ├── error_handling.py    # 错误处理和重试机制
│   │   ├── compiler.py          # 图编译器和优化
│   │   ├── monitoring.py        # 执行监控和性能指标
│   │   └── visualization.py     # 多格式可视化系统
│   ├── agents/                   # Agent 实现
│   │   └── react_agent.py       # ReAct Agent 实现
│   ├── nodes/                    # 节点实现
│   │   ├── parallel_node.py     # 并行执行节点
│   │   ├── router_node.py       # 路由决策节点
│   │   ├── react_agent_node.py  # ReAct Agent 节点
│   │   └── stream_react_agent_node.py  # 流式 ReAct 节点
│   ├── llm/                      # LLM 接口
│   │   ├── base.py              # LLM 基类和工厂
│   │   ├── openai.py            # OpenAI 实现
│   │   └── doubao.py            # 豆包 AI 实现
│   ├── tools/                    # 工具集成
│   │   └── mcp_tools.py         # MCP 工具管理器
│   ├── parsers/                  # 输出解析器
│   │   ├── json_parser.py       # JSON 解析
│   │   └── tool_parser.py       # 工具调用解析
│   ├── web/                      # Web 界面
│   │   ├── app.py               # Gradio 应用主文件
│   │   ├── components/          # UI 组件
│   │   └── handlers/            # 事件处理器
│   └── workflow/                 # 预定义工作流
│       ├── story_workflow.py    # 剧情生成工作流
│       ├── schedule_workflow.py # 日程安排工作流
│       └── joke_workflow.py     # 笑话生成工作流
├── mcp/                          # MCP 协议实现
│   ├── client/                   # MCP 客户端
│   ├── server/                   # MCP 服务端
│   └── types.py                  # MCP 类型定义
├── mcp_servers/                  # MCP 服务器实现
│   ├── csv_crud_server.py       # CSV 数据操作服务器
│   ├── chromadb_crud_server.py  # 向量数据库服务器
│   ├── python_executor_server.py # Python 代码执行服务器
│   └── role_info_crud_server.py # 角色信息 CRUD 服务器
├── database/                     # 数据库管理
│   └── managers/                 # 数据库管理器
├── config/                       # 配置文件
│   ├── yunhub_characters.json   # 角色配置
│   ├── yunhub_locations.json    # 地点配置
│   └── 基础人设.txt             # 主角人设
├── workspace/                    # 工作空间
│   ├── input/                   # 输入文件
│   ├── output/                  # 输出文件
│   ├── databases/               # 数据库文件
│   ├── checkpoints/             # 状态检查点
│   ├── monitoring/              # 监控数据
│   └── visualizations/          # 可视化输出
├── examples/                     # 使用示例
│   ├── enhanced_stategraph_demo.py  # 增强版 StateGraph 演示
│   └── quick_start.py           # 快速开始示例
├── main.py                      # 主入口文件
├── requirements.txt             # Python 依赖
├── pyproject.toml              # 项目配置
└── README.md                   # 项目说明
```

## 技术栈

### 核心依赖
- **Python**: 3.9+
- **Pydantic**: 2.5+ (类型验证和数据模型)
- **AsyncIO**: 异步编程支持
- **NetworkX**: 图算法和分析
- **Gradio**: Web 界面框架

### LLM 集成
- **OpenAI API**: GPT 系列模型
- **豆包 API**: 字节跳动大模型
- **Anthropic API**: Claude 系列模型 (推荐使用 Claude 4 Sonnet)

### 数据处理
- **SQLite**: 轻量级数据库
- **ChromaDB**: 向量数据库
- **Pandas**: 数据分析
- **NumPy**: 数值计算

### 可视化
- **Mermaid**: 文本图表
- **D3.js**: 交互式可视化
- **Graphviz**: 专业图形绘制

## 环境配置

### 1. 安装依赖
```bash
# 使用 pip 安装
pip install -r requirements.txt

# 或使用 Poetry (推荐)
pip install poetry
poetry install
```

### 2. 环境变量配置
创建 `.env` 文件：
```env
# LLM API 配置
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key  # Claude 4 Sonnet
ARK_API_KEY=your_doubao_key

# 推荐的 Claude 4 Sonnet 配置
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_MAX_TOKENS=4096
CLAUDE_TEMPERATURE=0.7

# MCP 服务器配置 (可选)
MCP_SERVER_URL=http://localhost:3000
MCP_TIMEOUT=30

# 工作空间配置
WORKSPACE_DIR=./workspace
CHECKPOINT_STORAGE=file
ENABLE_MONITORING=true
```

## 快速开始

### 1. 基本使用
```python
import asyncio
from src.llm.base import LLMFactory
from src.core.types import LLMConfig

# 配置 Claude 4 Sonnet
llm_config = LLMConfig(
    provider="anthropic",
    model_name="claude-sonnet-4-20250514",
    api_key="your_api_key",
    temperature=0.7,
    max_tokens=4096
)

# 创建 LLM 实例
llm = LLMFactory.create(llm_config)

# 简单对话
async def chat_example():
    from src.core.types import Message, MessageRole
    
    messages = [
        Message(role=MessageRole.USER, content="你好，请介绍一下自己")
    ]
    
    response = await llm.generate(messages)
    print(response.content)

# 运行示例
asyncio.run(chat_example())
```

### 2. StateGraph 使用
```python
from src.core.graph import StateGraph, StateGraphExecutor
from src.nodes.simple_chat_node import SimpleChatNode

# 创建图
graph = StateGraph(name="simple_chat_graph")

# 添加节点
chat_node = SimpleChatNode("chat", llm)
graph.add_node("chat", chat_node)
graph.set_entry_point("chat")

# 执行图
executor = StateGraphExecutor()
initial_state = {
    "messages": [
        Message(role=MessageRole.USER, content="创建一个简单的故事")
    ]
}

result = await executor.execute(graph, initial_state, {})
```

### 3. 启动 Web 界面
```bash
python main.py
```
访问 http://localhost:7860 使用 ChatGPT 风格的界面。

## 核心概念

### 1. StateGraph (状态图)
- **节点 (Node)**: 执行特定任务的基本单元
- **边 (Edge)**: 连接节点的路径
- **状态 (State)**: 在节点间传递的数据
- **执行器 (Executor)**: 管理图的执行流程

### 2. Agent 范式
- **ReAct**: Reasoning + Acting，推理与行动结合
- **Chain of Thought**: 思维链，逐步推理
- **Plan-Execute**: 计划执行，先计划后执行

### 3. MCP 工具
- **CSV CRUD**: 表格数据操作
- **ChromaDB**: 向量搜索和存储
- **Python Executor**: 安全的 Python 代码执行
- **Role Info**: 角色信息管理

## 最佳实践

### 1. LLM 使用建议
```python
# 推荐使用 Claude 4 Sonnet 进行复杂推理任务
llm_config = LLMConfig(
    provider="anthropic",
    model_name="claude-sonnet-4-20250514",
    temperature=0.7,  # 平衡创造性和一致性
    max_tokens=4096,  # 支持长文本生成
    streaming=True    # 启用流式输出
)
```

### 2. 错误处理配置
```python
from src.core.error_handling import ErrorHandler, RetryPolicy

error_handler = ErrorHandler()
error_handler.add_retry_policy("critical_node", RetryPolicy(
    max_retries=3,
    initial_delay=1.0,
    backoff_multiplier=2.0
))
```

### 3. 监控和可视化
```python
from src.core.monitoring import ExecutionMonitor, TraceContext
from src.core.visualization import save_visualization, VisualizationFormat

# 启用监控
monitor = ExecutionMonitor(enable_metrics=True, enable_tracing=True)
await monitor.start()

# 执行时使用轨迹上下文
async with TraceContext("trace-1", graph.name, monitor):
    result = await executor.execute(graph, initial_state, config)

# 生成可视化
save_visualization(
    graph, 
    "output/graph.html", 
    VisualizationFormat.HTML,
    include_performance=True
)
```

### 4. 状态管理最佳实践
```python
from src.core.executor import StateManager, add_reducer, priority_reducer

state_manager = StateManager(
    reducers={
        "messages": add_reducer,      # 消息列表追加
        "tasks": priority_reducer,    # 基于优先级合并
    },
    enable_checkpoints=True,          # 启用检查点
    enable_versioning=True            # 启用版本控制
)
```

## 常见任务

### 1. 创建自定义节点
```python
# -*- coding: utf-8 -*-
"""
自定义节点示例模块

@author leo
@description 演示如何创建自定义节点的示例代码
@classes CustomNode - 自定义节点实现类
@functions execute - 异步执行节点逻辑
@example 
    node = CustomNode("my_node")
    result = await node.execute({"input": "data"})
@dependencies src.core.base, src.core.types
"""
from src.core.base import BaseNode
from src.core.types import NodeType

class CustomNode(BaseNode):
    def __init__(self, name: str):
        super().__init__(name, NodeType.CUSTOM, "自定义节点描述")
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # 实现你的逻辑
        return {"result": "处理完成"}
```

### 2. 添加新的 LLM 提供商
```python
# -*- coding: utf-8 -*-
"""
自定义LLM提供商示例模块

@author leo
@description 演示如何添加新的LLM提供商的示例代码
@classes CustomLLM - 自定义LLM提供商实现类
@functions generate - 异步生成LLM响应
@example 
    llm = CustomLLM()
    response = await llm.generate(messages)
    LLMFactory.register("custom", CustomLLM)
@dependencies src.llm.base
"""
from src.llm.base import BaseLLMProvider, LLMFactory

class CustomLLM(BaseLLMProvider):
    async def generate(self, messages, **kwargs):
        # 实现 LLM 调用逻辑
        pass

# 注册到工厂
LLMFactory.register("custom", CustomLLM)
```

### 3. 创建自定义工作流
```python
# -*- coding: utf-8 -*-
"""
自定义工作流示例模块

@author leo
@description 演示如何创建自定义工作流的示例代码
@functions create_custom_workflow - 创建自定义工作流
@example 
    workflow = create_custom_workflow(llm)
    result = await workflow.execute(initial_state)
@dependencies src.core.graph
"""
from src.core.graph import GraphBuilder

def create_custom_workflow(llm):
    builder = GraphBuilder("custom_workflow")
    
    return (builder
        .add_node(CustomNode("step1"))
        .add_node(CustomNode("step2"))
        .connect("step1", "step2")
        .entry("step1")
        .build())
```

## 故障排除

### 常见问题

1. **API 密钥问题**
   - 确保 `.env` 文件中的 API 密钥正确
   - 检查密钥是否有足够的权限和额度

2. **依赖安装问题**
   - 使用 `pip install -r requirements.txt --upgrade`
   - 确保 Python 版本 >= 3.9

3. **MCP 服务器连接问题**
   - 检查 MCP 服务器是否正确启动
   - 验证网络连接和端口配置

4. **内存不足**
   - 调整 `max_concurrent_nodes` 参数
   - 启用检查点功能减少内存使用

### 调试技巧

1. **启用详细日志**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **使用监控查看执行流程**
```python
# 查看执行轨迹
trace = monitor.get_trace("trace_id")
print(f"执行状态: {trace.status}")
print(f"访问节点: {[e.node_name for e in trace.events]}")
```

3. **可视化调试**
```python
# 生成执行流程图
visualization = visualize_graph(graph, execution_trace=trace)
```

## 贡献指南

### 开发环境设置
1. Fork 项目仓库
2. 创建开发分支: `git checkout -b feature/amazing-feature`
3. 安装开发依赖: `poetry install --dev`
4. 运行测试: `pytest`

### 代码规范
- 使用 Black 进行代码格式化
- 使用 Flake8 进行代码检查
- 添加类型注解和文档字符串
- 遵循 PEP 8 编码规范
- **每个Python文件头部必须包含详细的模块注释**，包括：
  - 作者信息（@author leo）
  - 模块功能描述
  - 主要类和函数的说明
  - 使用示例
  - 依赖关系说明
  - 这些注释应详尽到足以替代其他功能介绍文档

### 提交规范
- 功能: `feat: 添加新功能描述`
- 修复: `fix: 修复问题描述`
- 文档: `docs: 更新文档`
- 重构: `refactor: 重构代码`

## 联系方式

- 项目地址: [GitHub Repository]
- 问题反馈: [GitHub Issues]
- 文档地址: [Project Documentation]

---

**注意**: 本项目推荐使用 Claude 4 Sonnet 模型以获得最佳的推理和生成效果。确保在 `.env` 文件中正确配置 Anthropic API 密钥。