# MCP 服务器集合

这个目录包含了各种 MCP (Model Context Protocol) 服务器的实现。

## 目录结构

```
mcp_servers/
├── README.md                 # 本文档
├── mcp_types.py             # MCP协议类型定义（避免与Python标准库冲突）
├── simple_csv_server.py     # 简单独立的CSV服务器 ✅ 可用
├── csv_mcp_server.py        # 完整的CSV服务器（需要mcp框架）
├── vector_server.py         # 向量查询服务器（需要ChromaDB）
├── launcher.py              # 服务启动器
└── __init__.py              # 包初始化文件
```

## 快速开始

### 1. 简单CSV服务器（推荐）

这是一个独立的、不依赖复杂架构的CSV查询服务器：

```bash
# 启动服务器
python simple_csv_server.py

# 或者指定CSV目录
cd your_csv_directory
python path/to/simple_csv_server.py
```

**功能特性：**
- 列出目录中的CSV文件
- 查询CSV数据
- 支持中文编码（UTF-8和GBK）
- 独立运行，无外部依赖（除pandas）

### 2. 安装依赖

```bash
pip install pandas
pip install chromadb  # 仅向量服务器需要
```

### 3. 使用启动器

```bash
# 启动CSV服务器
python launcher.py --service csv --csv-dir ./data

# 启动向量服务器
python launcher.py --service vector --chroma-db ./chroma_db
```

## 服务器详情

### SimpleCSVServer（simple_csv_server.py）

**优点：**
- ✅ 独立运行，无复杂依赖
- ✅ 符合MCP协议标准
- ✅ 支持中文CSV文件
- ✅ 错误处理完善

**支持的工具：**
- `csv_list_files`: 列出CSV文件
- `csv_query`: 查询CSV数据

### CSVMCPServer（csv_mcp_server.py）

完整功能的CSV服务器，需要mcp框架支持。

### VectorMCPServer（vector_server.py）

向量查询服务器，需要ChromaDB。

## 解决的问题

1. **名称冲突解决**: 将 `types.py` 重命名为 `mcp_types.py` 避免与Python标准库冲突
2. **目录重组**: 独立的 `mcp_servers` 目录，便于管理
3. **简化启动**: 提供独立的简单服务器，减少依赖
4. **编码支持**: 自动处理UTF-8和GBK编码的CSV文件

## 故障排除

### 问题1: types模块冲突
```
ImportError: cannot import name 'GenericAlias' from partially initialized module 'types'
```
**解决方案**: 使用新的 `mcp_types.py` 文件

### 问题2: 启动没反应
**解决方案**: 使用 `simple_csv_server.py`，它是独立的，不依赖复杂架构

### 问题3: 中文编码错误
**解决方案**: 服务器自动尝试UTF-8和GBK编码

## 开发指南

要添加新的MCP服务器：

1. 在 `mcp_servers/` 目录下创建新文件
2. 导入 `mcp_types.py` 中的类型
3. 实现MCP协议的标准方法
4. 更新 `__init__.py` 和启动器

## 测试

```bash
# 测试CSV服务器
cd mcp_servers
python simple_csv_server.py

# 在另一个终端测试（需要MCP客户端）
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python simple_csv_server.py
``` 