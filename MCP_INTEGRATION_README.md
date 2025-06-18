# ZZZero MCP集成功能

## 🎯 概述

本项目已成功集成Model Context Protocol (MCP)，为ReactAgent提供了强大的本地和远程服务访问能力。用户可以通过Web界面轻松管理和使用各种MCP服务器。

## ✨ 主要功能

### 🔌 MCP服务器管理
- **本地服务器**: 支持stdio方式启动本地MCP服务器
  - CSV CRUD服务器 - 高级CSV数据库操作
  - ChromaDB服务器 - 向量数据库和语义搜索
- **远程服务器**: 支持HTTP方式连接远程MCP服务器
- **实时状态监控**: 显示服务器连接状态、可用工具等
- **动态添加**: 用户可在界面中添加新的远程服务器

### 🤖 ReactAgent集成
- 将MCP服务器的工具、资源、提示统一集成到Agent工具系统
- 支持多服务器工具组合使用
- 工具调用统计和执行监控

### 🌐 用户界面
- **MCP服务器面板**: 可视化管理所有MCP服务器
- **工具选择**: 勾选启用需要的MCP服务器
- **远程添加**: 支持添加自定义远程MCP服务器
- **状态显示**: 实时显示连接状态和可用功能

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动演示
```bash
python start_mcp_demo.py
```

### 3. 访问界面
打开浏览器访问: http://localhost:7860

### 4. 配置使用
1. **配置LLM**: 在左侧面板配置LLM提供商和API密钥
2. **选择Agent**: 选择ReactAgent类型
3. **启用MCP服务器**: 在MCP服务器面板中勾选需要的服务器
4. **添加远程服务器**: 可选择添加自定义远程MCP服务器
5. **应用配置**: 点击"应用配置"按钮
6. **开始对话**: 在右侧聊天界面开始使用

## 🛠️ 架构设计

### 核心组件

1. **MCPManager** (`src/tools/mcp_manager.py`)
   - 统一管理本地和远程MCP服务器
   - 处理服务器连接、断开、状态监控
   - 支持动态添加远程服务器

2. **MCPToolManager** (`src/tools/mcp_tools.py`)
   - 将MCP服务器功能包装为Agent工具
   - 支持工具、资源、提示的统一管理
   - 与ReactAgent无缝集成

3. **Web界面** (`src/web/app.py`)
   - 用户友好的MCP服务器管理界面
   - 实时状态显示和配置面板
   - 支持远程服务器动态添加

### MCP服务器类型

1. **本地stdio服务器**
   - CSV CRUD服务器: 处理CSV文件的增删改查
   - ChromaDB服务器: 向量数据库操作和语义搜索

2. **远程HTTP服务器**
   - 支持标准MCP HTTP协议
   - 可连接任何兼容的远程MCP服务器

3. **本地HTTP服务器**
   - 支持本地HTTP方式的MCP服务器

## 🔧 使用示例

### 添加远程MCP服务器
```python
from tools.mcp_manager import mcp_manager

# 添加远程服务器
mcp_manager.add_remote_server(
    server_id="my_remote_server",
    name="我的远程服务器",
    url="http://example.com:3000",
    description="自定义远程MCP服务器"
)
```

### 在Agent中使用MCP工具
```python
from tools.mcp_tools import MCPToolManager
from agents.react_agent import ReactAgent

# 创建工具管理器，启用指定的MCP服务器
tool_manager = MCPToolManager(enabled_servers=["csv", "chromadb"])
await tool_manager.initialize()

# 创建ReactAgent
agent = ReactAgent(
    llm=llm,
    tool_manager=tool_manager,
    max_iterations=5
)

# 运行Agent
result = await agent.run("请分析CSV文件中的数据")
```

## 📁 文件结构

```
src/
├── tools/
│   ├── mcp_manager.py      # MCP服务器管理器
│   ├── mcp_tools.py        # MCP工具集成
│   └── base.py             # 工具基类
├── web/
│   └── app.py              # Web界面（包含MCP界面）
├── agents/
│   └── react_agent.py      # ReactAgent实现
└── core/
    └── base.py             # 核心基类

mcp_servers/                # 本地MCP服务器实现
├── csv_crud_server.py      # CSV CRUD服务器
├── chromadb_crud_server.py # ChromaDB服务器
└── advanced_launcher.py    # 高级启动器

start_mcp_demo.py           # 演示启动脚本
```

## 🎮 界面功能详解

### MCP服务器面板
- **服务器状态**: 显示所有可用MCP服务器及其连接状态
- **服务器类型**: 图标区分本地(💻)、远程(🌐)、本地HTTP(🏠)服务器
- **工具预览**: 显示每个服务器提供的工具列表
- **启用选择**: 勾选框选择要启用的服务器

### 远程服务器添加
- **服务器名称**: 为远程服务器设置友好的名称
- **服务器URL**: MCP服务器的HTTP地址
- **一键添加**: 自动验证并添加到可用服务器列表

### 配置状态显示
- **实时反馈**: 显示配置成功/失败状态
- **工具统计**: 显示启用的工具总数
- **服务器计数**: 区分传统工具和MCP服务器数量

## 🔒 安全考虑

1. **远程连接验证**: 添加远程服务器时进行连接测试
2. **错误处理**: 完善的异常处理和用户反馈
3. **资源清理**: 自动清理断开的连接和资源
4. **输入验证**: 验证用户输入的服务器地址和参数

## 🚀 扩展能力

- **支持更多MCP服务器**: 可轻松添加新的MCP服务器类型
- **自定义工具包装**: 支持自定义MCP工具的包装和集成
- **高级配置**: 支持MCP服务器的高级配置选项
- **批量管理**: 支持批量启用/禁用MCP服务器

## 📝 使用建议

1. **本地服务器**: 优先使用本地服务器，性能更好、更可靠
2. **远程服务器**: 适用于共享服务和云端资源
3. **工具组合**: 可以同时启用多个服务器，组合使用不同类型的工具
4. **监控状态**: 注意观察服务器连接状态，及时处理连接问题

## 🎯 特色亮点

✅ **统一接口**: 本地和远程MCP服务器使用统一的管理接口  
✅ **可视化管理**: 直观的Web界面管理所有MCP服务器  
✅ **实时状态**: 实时显示服务器状态和可用工具  
✅ **动态扩展**: 支持运行时添加新的远程服务器  
✅ **完整集成**: 与ReactAgent完全集成，无缝使用  
✅ **错误恢复**: 完善的错误处理和自动重连机制  

---

*这个MCP集成方案为ZZZero AI Agent系统提供了强大的扩展能力，让用户可以轻松接入各种本地和远程的MCP服务，大大丰富了Agent的功能范围。* 