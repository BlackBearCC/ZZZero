# MCP (Model Context Protocol) 集成

MCP是一个用于AI模型和工具之间通信的协议，本目录包含MCP相关的实现。

## 目录结构

```
mcp/
├── client.py              # MCP客户端实现
├── mcp_launcher.py        # MCP服务启动器
├── csv_mcp_server.py      # CSV工具MCP服务
├── vector_mcp_server.py   # 向量搜索MCP服务
├── mcp_config.json        # MCP配置文件
└── README.md              # 本文档
```

## 组件说明

### 1. MCP客户端 (client.py)

MCP客户端负责：
- 连接到MCP服务器
- 发现可用工具
- 调用工具并处理响应

使用示例：
```python
from mcp.client import MCPClient

# 创建客户端
client = MCPClient(
    server_command=sys.executable,
    server_args=["-m", "mcp.csv_mcp_server"]
)

# 连接并获取工具
await client.connect()
tools = await client.list_tools()

# 调用工具
result = await client.call_tool("csv_query", {
    "file_path": "data.csv",
    "query": "age > 25"
})
```

### 2. MCP服务启动器 (mcp_launcher.py)

统一的MCP服务启动器，支持：
- 启动不同类型的MCP服务
- 组合多个MCP服务
- 服务管理和监控

启动方式：
```bash
# 启动CSV服务
python -m mcp.mcp_launcher --service csv

# 启动向量搜索服务
python -m mcp.mcp_launcher --service vector

# 启动组合服务
python -m mcp.mcp_launcher --service combined
```

### 3. CSV工具服务 (csv_mcp_server.py)

提供CSV文件操作工具：
- `csv_query`: 查询CSV文件
- `csv_aggregate`: 聚合统计
- `csv_join`: 连接多个CSV文件

### 4. 向量搜索服务 (vector_mcp_server.py)

提供向量相似度搜索功能：
- `vector_search`: 基础向量搜索
- `vector_enhanced_search`: 增强搜索（支持过滤）
- `create_collection`: 创建向量集合
- `add_documents`: 添加文档

## 配置文件 (mcp_config.json)

定义了可用的MCP服务和工具配置：

```json
{
  "services": {
    "csv_tools": {
      "command": "python",
      "args": ["-m", "mcp.csv_mcp_server"],
      "description": "CSV文件处理工具"
    },
    "vector_tools": {
      "command": "python", 
      "args": ["-m", "mcp.vector_mcp_server"],
      "description": "向量搜索工具"
    }
  }
}
```

## 集成到Agent框架

MCP工具通过`src/tools/mcp_tools.py`集成到Agent框架中：

1. **自动发现**：框架启动时自动加载配置的MCP服务
2. **工具包装**：MCP工具被包装为框架标准工具
3. **统一接口**：通过ToolManager统一管理所有工具

## 扩展MCP服务

创建新的MCP服务步骤：

1. 继承MCP服务基类
2. 实现工具方法
3. 注册到启动器
4. 更新配置文件

示例：
```python
from mcp import Server, Tool

class MyMCPServer(Server):
    @Tool(description="我的工具")
    async def my_tool(self, param: str) -> dict:
        # 实现工具逻辑
        return {"result": f"处理了: {param}"}
```

## 调试和测试

1. **测试单个服务**：
```bash
python -m mcp.csv_mcp_server --test
```

2. **查看可用工具**：
```bash
python -m mcp.client --list-tools
```

3. **交互式测试**：
```bash
python -m mcp.client --interactive
```

## 注意事项

1. MCP服务运行在独立进程中，通过标准输入输出通信
2. 确保服务启动时有足够的资源（内存、CPU）
3. 长时间运行的工具应该实现超时机制
4. 敏感数据处理需要额外的安全措施 