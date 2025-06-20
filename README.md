# ZZZero AI Agent Framework

基于节点编排的AI Agent框架，支持多种Agent范式、MCP工具集成和批量任务处理。

## 🌟 特性

- **节点式编排**：参考LangGraph的节点编排方式，但完全自主实现
- **多种Agent范式**：支持ReAct、Chain of Thought、Plan-Execute等
- **灵活的工具集成**：支持MCP (Model Context Protocol) 工具
- **ChatGPT风格界面**：基于Gradio的友好用户界面
- **批量任务处理**：支持并行/串行批量任务执行
- **多LLM支持**：支持OpenAI、Anthropic、豆包等多种LLM
- **强大的解析器**：支持JSON、工具调用、结构化输出等多种解析方式
- **Python代码执行**：安全的Python代码执行环境，支持自动依赖管理

## ✨ 新功能

### 高级节点类型

- **路由节点 (RouterNode)**
  - 支持条件路由：基于表达式、函数或模式匹配
  - 循环控制：支持while循环和最大循环次数限制
  - 灵活配置：可设置默认路由和回退路由

- **并行节点 (ParallelNode)**
  - 并行执行多个子节点
  - 多种聚合策略：all（等待所有）、first（第一个完成）、majority（多数完成）
  - 超时控制和错误处理

- **最终化节点 (FinalizeNode)**
  - 智能生成最终答案
  - 答案质量评估
  - 执行摘要生成

### 流程可视化

- **实时状态监控**：查看每个节点的执行状态、耗时和输出预览
- **流程图展示**：使用Mermaid自动生成执行流程图
- **性能指标**：显示详细的执行指标和统计信息

### Python执行器MCP服务器

- **安全代码执行**：在隔离的虚拟环境中执行Python代码
- **自动依赖管理**：智能检测并安装代码所需的Python包
- **安全检查机制**：自动检测危险函数和模块，防止恶意代码执行
- **执行历史记录**：记录所有代码执行历史，便于调试和审计
- **包管理功能**：支持包安装、列表查看等操作
- **超时控制**：防止代码无限循环或长时间运行

## 📁 项目结构

```
ZZZero/
├── src/
│   ├── core/              # 核心框架
│   │   ├── base.py        # 基类定义
│   │   ├── types.py       # 类型定义(Pydantic)
│   │   └── graph.py       # 图执行引擎
│   ├── agents/            # Agent实现
│   │   ├── react_agent.py # ReAct Agent
│   │   └── ...           
│   ├── nodes/             # 节点实现
│   │   ├── think_node.py  # 思考节点
│   │   ├── act_node.py    # 行动节点
│   │   └── ...
│   ├── llm/               # LLM接口
│   │   ├── base.py        # LLM基类和工厂
│   │   ├── doubao.py      # 豆包实现
│   │   └── openai.py      # OpenAI实现
│   ├── parsers/           # 输出解析器
│   │   ├── json_parser.py # JSON解析
│   │   └── tool_parser.py # 工具调用解析
│   ├── tools/             # 工具集成
│   │   └── mcp_tools.py   # MCP工具管理
│   ├── prompts/           # 提示模板
│   └── web/               # Web界面
│       └── app.py         # Gradio应用
├── mcp_servers/          # MCP服务器实现
│   ├── csv_crud_server.py # CSV数据操作服务器
│   ├── chromadb_crud_server.py # 向量数据库服务器
│   └── python_executor_server.py # Python代码执行服务器
├── examples/              # 使用示例
│   └── 
├── tests/                 # 测试文件
├── config/                # 配置文件
├── main.py               # 主入口
└── pyproject.toml        # 项目配置
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install poetry
poetry install
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# LLM API密钥
OPENAI_API_KEY=your_openai_key
ARK_API_KEY=your_doubao_key
ANTHROPIC_API_KEY=your_anthropic_key

# MCP服务器配置（可选）
MCP_SERVER_URL=http://localhost:3000
```

### 3. 启动应用

```bash
python main.py
```

访问 http://localhost:7860 即可使用界面。

## 💡 使用示例

### 基本使用

```python
from src.llm.factory import LLMFactory
from src.agents.react_agent import ReactAgent

from src.core.types import LLMConfig

# 创建LLM
llm_config = LLMConfig(
    provider="doubao",
    model_name="your-model",
    api_key="your-key"
)
llm = LLMFactory.create(llm_config)

# 创建工具管理器
tool_manager = MCPToolManager()

# 创建Agent
agent = ReactAgent(llm=llm, tool_manager=tool_manager)

# 运行任务
result = await agent.run("帮我搜索最新的AI发展趋势")
print(result.result)
```

### 自定义节点

```python
from src.core.base import BaseNode
from src.core.types import NodeInput, NodeOutput, NodeType

class CustomNode(BaseNode):
    def __init__(self, name: str):
        super().__init__(name, NodeType.CUSTOM)
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        # 实现你的逻辑
        return NodeOutput(
            data={"processed": "data"},
            next_node="next_node_name"
        )
```

### 自定义Agent

```python
from src.core.base import BaseAgent
from src.core.graph import GraphBuilder

class CustomAgent(BaseAgent):
    def build_graph(self) -> Graph:
        builder = GraphBuilder("custom_graph")
        
        # 添加节点和连接
        return (builder
            .add_node(node1)
            .add_node(node2)
            .connect("node1", "node2")
            .entry("node1")
            .exit("node2")
            .build()
        )
```

### 使用路由节点

```python
from src.nodes import RouterNode, create_conditional_route, create_loop_route

# 创建路由节点
router = RouterNode(
    "decision_router",
    routes=[
        # 循环路由：继续处理直到满足条件
        create_loop_route(
            target="process_node",
            while_condition="len(results) < 5",
            max_loops=10,
            fallback="finalize_node"
        ),
        # 条件路由：根据成功率决定下一步
        create_conditional_route(
            condition="success_rate > 0.8",
            target="success_node"
        )
    ],
    default_route="error_handler"
)
```

### 使用并行节点

```python
from src.nodes import ParallelNode, ActNode

# 创建并行搜索节点
parallel_search = ParallelNode(
    "multi_source_search",
    sub_nodes=[
        ActNode("web_search", llm, tool_manager),
        ActNode("db_search", llm, tool_manager),
        ActNode("doc_search", llm, tool_manager)
    ],
    aggregation_strategy="all",  # 等待所有搜索完成
    timeout=10.0,  # 10秒超时
    max_workers=3  # 最多3个并行任务
)
```

### 使用Python执行器

```python
from src.tools.mcp_tools import MCPToolManager
from src.nodes.stream_react_agent_node import StreamReactAgentNode

# 创建工具管理器并启用Python执行器
tool_manager = MCPToolManager()
tool_manager.set_enabled_servers(["python"])
await tool_manager.initialize()

# 创建React Agent
agent = StreamReactAgentNode(
    model_name="deepseek-chat",
    tool_manager=tool_manager,
    max_iterations=5
)

# 使用Agent执行Python代码
input_data = {
    "messages": [
        {
            "role": "user",
            "content": "请帮我计算斐波那契数列的前10项，并用Python实现"
        }
    ]
}

async for chunk in agent.stream(input_data):
    if chunk.get("type") == "tool_result":
        result = chunk.get("result", {})
        if "stdout" in result:
            print(f"执行结果: {result['stdout']}")
```

### 运行Python执行器示例

```bash
# 演示模式 - 运行预设的演示用例
python examples/python_executor_example.py --mode demo

# 交互模式 - 与Python执行器进行交互
python examples/python_executor_example.py --mode interactive
```

## 🔧 核心概念

### 1. 节点 (Node)
- 执行图中的基本单元
- 每个节点负责特定的任务（思考、行动、观察等）
- 可以自定义节点实现特定功能

### 2. 图 (Graph)
- 由节点和连接组成的执行流程
- 支持条件连接和并行执行
- 自动验证图的有效性（无环、可达性等）

### 3. Agent
- 高级抽象，封装了特定的工作流程
- 不同的Agent实现不同的范式（ReAct、CoT等）
- 可以轻松切换和组合

### 4. 解析器 (Parser)
- 将LLM输出转换为结构化数据
- 支持多种格式（JSON、XML、Markdown等）
- 可扩展的解析器体系

## 🛠 高级功能

### 批量任务处理

界面支持批量任务输入，可以选择并行或串行执行：

1. 在界面中展开"批量任务"面板
2. 每行输入一个任务
3. 选择执行方式（并行/串行）
4. 查看执行结果和耗时

### MCP工具集成

支持通过MCP协议集成外部工具：

1. 启动MCP服务器
2. 在界面中配置MCP服务器地址
3. 选择要启用的工具
4. Agent会自动使用这些工具

### 执行轨迹可视化

每次执行都会记录详细的执行轨迹：

- 节点执行顺序
- 每个节点的输入输出
- 执行时间和状态
- 错误信息（如果有）

## 📝 设计模式

项目采用了多种设计模式确保代码的可维护性和可扩展性：

1. **工厂模式**：LLMFactory用于创建不同的LLM实例
2. **策略模式**：不同的Agent和Parser实现
3. **模板方法**：BaseNode定义了执行流程模板
4. **观察者模式**：执行轨迹记录
5. **建造者模式**：GraphBuilder用于构建执行图

## 🤝 贡献

欢迎贡献代码！请遵循以下步骤：

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。