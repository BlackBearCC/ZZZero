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

### 创建新节点
```python
from src.core.base import BaseNode
from src.core.types import NodeInput, NodeOutput, NodeType

class CustomNode(BaseNode):
    def __init__(self, name: str):
        super().__init__(name, NodeType.CUSTOM)
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        # 实现异步逻辑
        return NodeOutput(
            data={"processed": "data"},
            next_node="next_node_name"
        )
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

### 1. 高级节点类型
- **RouterNode**: 条件路由和循环控制
- **ParallelNode**: 并行执行，支持all/first/majority策略
- **FinalizeNode**: 智能生成最终答案和执行摘要

### 2. 流式处理
- 支持实时流式输出和状态更新
- `stream_react_agent_node.py` 提供流式Agent实现

### 3. Python代码执行
- 安全的虚拟环境隔离
- 自动依赖检测和安装
- 危险代码检测和阻止
- 执行历史记录和审计

### 4. 批量任务处理
- 支持CSV批量输入
- 并行/串行处理模式选择
- 实时进度监控和结果导出

### 5. 多模态工作流
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