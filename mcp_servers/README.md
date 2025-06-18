# MCP 服务器集合

这个目录包含了各种 MCP (Model Context Protocol) 服务器的实现。

## ✅ 当前可用状态

- ✅ **simple_csv_server.py** - 完全独立，立即可用
- ✅ **simple_launcher.py** - 简化启动器，无依赖问题
- ❌ **launcher.py** - 需要已删除的mcp框架（暂不可用）
- ❌ **csv_mcp_server.py** - 需要已删除的mcp框架（暂不可用）
- ❌ **vector_server.py** - 需要已删除的mcp框架（暂不可用）

## 🚀 快速开始（推荐）

### 方法1: 使用简化启动器

```bash
# 1. 进入目录
cd mcp_servers

# 2. 创建示例数据
python simple_launcher.py --create-sample

# 3. 启动服务器
python simple_launcher.py
```

### 方法2: 直接使用简单服务器

```bash
# 启动独立CSV服务器
cd mcp_servers
python simple_csv_server.py
```

## 📁 目录结构

```
mcp_servers/
├── README.md                 # 本文档
├── simple_csv_server.py     # ✅ 简单独立的CSV服务器
├── simple_launcher.py       # ✅ 简化启动器
├── test_server.py           # ✅ 测试脚本
├── sample_data.csv          # 示例CSV数据（自动生成）
├── mcp_types.py             # MCP协议类型定义
├── csv_mcp_server.py        # ❌ 完整版（需要框架）
├── vector_server.py         # ❌ 向量服务器（需要框架）
├── launcher.py              # ❌ 原启动器（需要框架）
└── __init__.py              # 包初始化文件
```

## 🛠 解决的问题

### 原问题
```bash
ModuleNotFoundError: No module named 'mcp.server.stdio_server'
```

### 解决方案
1. **创建了独立服务器**: `simple_csv_server.py` 不依赖外部框架
2. **提供了简化启动器**: `simple_launcher.py` 避免导入错误
3. **保留了完整版本**: 供将来框架恢复后使用

## 📊 支持的功能

### SimpleCSVServer（推荐使用）

**功能特性：**
- ✅ 列出目录中的CSV文件
- ✅ 查询CSV数据（支持限制行数）
- ✅ 支持中文编码（UTF-8和GBK）
- ✅ 完全符合MCP协议标准
- ✅ 独立运行，无外部依赖（除pandas）
- ✅ 完善的错误处理

**支持的MCP方法：**
- `initialize` - 服务器初始化
- `tools/list` - 列出可用工具
- `tools/call` - 调用工具

**支持的工具：**
- `csv_list_files` - 列出CSV文件
- `csv_query` - 查询CSV数据

## 🔧 使用示例

### 1. 基本使用

```bash
# 启动服务器
python simple_launcher.py

# 创建测试数据
python simple_launcher.py --create-sample

# 指定目录启动
python simple_launcher.py --csv-dir ./data
```

### 2. 测试验证

```bash
# 运行测试脚本
python test_server.py
```

### 3. 手动测试MCP协议

```bash
# 启动服务器
python simple_csv_server.py

# 在另一个终端发送测试请求
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python simple_csv_server.py
```

## 💡 开发指南

### 添加新功能到简单服务器

1. 编辑 `simple_csv_server.py`
2. 在 `tools/list` 方法中添加新工具定义
3. 在 `tools/call` 方法中添加处理逻辑
4. 实现对应的处理函数

### 扩展到其他数据源

可以参考 `simple_csv_server.py` 的结构创建：
- `simple_json_server.py`
- `simple_excel_server.py`
- `simple_database_server.py`

## 🚨 故障排除

### 问题1: 模块导入错误
**错误**: `ModuleNotFoundError: No module named 'mcp.server'`  
**解决**: 使用 `simple_launcher.py` 而不是 `launcher.py`

### 问题2: 启动没反应
**解决**: 确保使用了 `simple_csv_server.py`

### 问题3: 中文编码错误
**解决**: 服务器自动处理UTF-8和GBK编码

### 问题4: pandas未安装
```bash
pip install pandas
```

## 📈 性能特点

- **启动时间**: < 1秒
- **内存使用**: 最小化（仅加载需要的CSV）
- **并发支持**: 单线程异步处理
- **文件缓存**: 避免重复加载相同文件

## 🔮 未来计划

1. 当mcp框架恢复后，启用完整功能版本
2. 添加更多数据源支持
3. 增强查询能力（SQL语法支持）
4. 添加数据可视化功能

## 📞 支持

如果遇到问题：
1. 检查是否使用了正确的启动器（`simple_launcher.py`）
2. 确认pandas已安装
3. 查看错误日志获取详细信息 