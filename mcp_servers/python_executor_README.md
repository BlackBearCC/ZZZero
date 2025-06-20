# Python执行器MCP服务器

## 概述

Python执行器MCP服务器是一个安全的Python代码执行环境，基于Model Context Protocol (MCP)协议实现。它允许大模型在隔离的虚拟环境中安全执行Python代码，支持自动依赖管理、安全检查、执行历史记录等功能。

## 主要特性

### 🔒 安全执行
- **代码安全检查**: 自动检测危险函数和模块导入
- **虚拟环境隔离**: 在独立的Python虚拟环境中执行代码
- **超时控制**: 防止代码无限循环或长时间运行
- **资源限制**: 限制代码对系统资源的访问

### 📦 智能包管理
- **自动依赖检测**: 分析代码中的import语句
- **动态包安装**: 自动安装缺失的Python包
- **包版本管理**: 列出和管理已安装的包
- **常见包映射**: 智能映射包名（如cv2→opencv-python）

### 📊 执行监控
- **执行历史**: 记录代码执行历史和结果
- **性能统计**: 跟踪执行时间和资源使用
- **错误诊断**: 详细的错误信息和调试支持
- **日志记录**: 完整的执行日志和审计跟踪

## 工具列表

### 1. execute_python_code
在安全的隔离环境中执行Python代码

**参数:**
- `code` (string, 必需): 要执行的Python代码
- `timeout` (integer, 可选): 执行超时时间(秒)，默认30秒
- `allow_unsafe` (boolean, 可选): 是否允许执行不安全的代码，默认false

**返回:**
```json
{
  "execution_id": "exec_1703123456",
  "success": true,
  "stdout": "执行结果输出",
  "stderr": "错误信息",
  "return_code": 0,
  "execution_time": 0.123,
  "dependencies_info": "成功安装依赖: numpy, pandas",
  "executed_at": "2023-12-21T10:30:45.123456",
  "completed_at": "2023-12-21T10:30:45.246789"
}
```

### 2. install_python_package
安装Python包到虚拟环境

**参数:**
- `package_name` (string, 必需): 要安装的包名

**返回:**
```json
{
  "package_name": "numpy",
  "success": true,
  "message": "安装成功",
  "installed_at": "2023-12-21T10:30:45.123456"
}
```

### 3. list_installed_packages
列出虚拟环境中已安装的Python包

**返回:**
```json
{
  "packages": [
    {"name": "numpy", "version": "1.24.3"},
    {"name": "pandas", "version": "2.0.3"}
  ],
  "total_count": 2,
  "retrieved_at": "2023-12-21T10:30:45.123456"
}
```

### 4. get_execution_history
获取代码执行历史记录

**参数:**
- `limit` (integer, 可选): 返回的历史记录数量限制，默认20

**返回:**
```json
{
  "history": [
    {
      "execution_id": "exec_1703123456",
      "code": "print('Hello, World!')",
      "success": true,
      "execution_time": 0.123,
      "executed_at": "2023-12-21T10:30:45.123456"
    }
  ],
  "total_count": 1,
  "retrieved_at": "2023-12-21T10:30:45.123456"
}
```

### 5. clear_execution_history
清空代码执行历史记录

**返回:**
```json
{
  "cleared_count": 15,
  "cleared_at": "2023-12-21T10:30:45.123456"
}
```

### 6. check_code_safety
检查Python代码的安全性

**参数:**
- `code` (string, 必需): 要检查的Python代码

**返回:**
```json
{
  "code": "print('Hello, World!')",
  "is_safe": true,
  "warnings": [],
  "checked_at": "2023-12-21T10:30:45.123456"
}
```

## 使用示例

### 基础数学计算
```python
# 通过MCP调用
result = await mcp_client.call_tool("execute_python_code", {
    "code": """
import math

# 计算圆的面积
radius = 5
area = math.pi * radius ** 2
print(f"半径为 {radius} 的圆的面积是: {area:.2f}")

# 计算阶乘
n = 5
factorial = math.factorial(n)
print(f"{n} 的阶乘是: {factorial}")
"""
})
```

### 数据分析
```python
# 自动安装pandas并执行数据分析
result = await mcp_client.call_tool("execute_python_code", {
    "code": """
import pandas as pd
import numpy as np

# 创建示例数据
data = {
    'name': ['Alice', 'Bob', 'Charlie', 'Diana'],
    'age': [25, 30, 35, 28],
    'salary': [50000, 60000, 70000, 55000]
}

df = pd.DataFrame(data)
print("员工数据:")
print(df)

print(f"\\n平均年龄: {df['age'].mean():.1f}")
print(f"平均薪资: ${df['salary'].mean():,.0f}")
print(f"薪资中位数: ${df['salary'].median():,.0f}")
"""
})
```

### 网络请求
```python
# 自动安装requests并执行HTTP请求
result = await mcp_client.call_tool("execute_python_code", {
    "code": """
import requests
import json

try:
    response = requests.get("https://httpbin.org/json", timeout=5)
    print(f"HTTP状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("响应数据:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"请求失败: {response.status_code}")
        
except Exception as e:
    print(f"请求异常: {e}")
"""
})
```

## 安全特性

### 代码安全检查
系统会自动检测以下危险操作：
- 危险函数调用：`exec`, `eval`, `__import__`, `open`, `file`等
- 危险模块导入：`os`, `sys`, `subprocess`, `socket`等
- 危险操作模式：系统命令执行、文件操作等

### 执行环境隔离
- 使用独立的Python虚拟环境
- 限制文件系统访问
- 控制网络访问权限
- 设置执行超时限制

### 资源管理
- 内存使用限制
- CPU时间限制
- 磁盘空间限制
- 进程数量限制

## 配置选项

### 初始化参数
```python
server = PythonExecutorServer(
    workspace_dir="./workspace/python_executor"  # 工作空间目录
)
```

### 环境变量
- `PYTHON_EXECUTOR_TIMEOUT`: 默认执行超时时间(秒)
- `PYTHON_EXECUTOR_MAX_HISTORY`: 最大历史记录数量
- `PYTHON_EXECUTOR_ALLOW_UNSAFE`: 是否允许不安全代码(生产环境应设为false)

## 故障排除

### 常见问题

1. **虚拟环境创建失败**
   - 确保Python版本 >= 3.7
   - 检查磁盘空间是否充足
   - 验证Python venv模块是否可用

2. **包安装失败**
   - 检查网络连接
   - 验证包名是否正确
   - 查看pip源配置

3. **代码执行超时**
   - 增加timeout参数值
   - 优化代码性能
   - 检查是否存在无限循环

4. **权限错误**
   - 检查工作目录权限
   - 确保虚拟环境路径可写
   - 验证Python解释器权限

### 日志调试
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 最佳实践

### 代码编写建议
1. **使用类型提示**: 提高代码可读性
2. **异常处理**: 妥善处理可能的异常
3. **资源清理**: 及时释放资源
4. **模块化设计**: 将复杂逻辑分解为函数

### 安全建议
1. **最小权限原则**: 只授予必要的权限
2. **输入验证**: 验证所有外部输入
3. **定期更新**: 保持依赖包的最新版本
4. **监控审计**: 记录和监控所有执行活动

### 性能优化
1. **缓存机制**: 合理使用执行历史缓存
2. **批量操作**: 减少频繁的小操作
3. **资源监控**: 监控内存和CPU使用情况
4. **定期清理**: 清理临时文件和历史记录

## 版本历史

- **v1.0.0**: 初始版本，基础代码执行功能
- **v1.1.0**: 添加安全检查和虚拟环境支持
- **v1.2.0**: 增加自动依赖管理和执行历史
- **v1.3.0**: 完善错误处理和日志记录

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 贡献指南

欢迎提交问题报告和功能请求！请遵循以下步骤：

1. Fork项目仓库
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交GitHub Issue
- 发送邮件至项目维护者
- 参与社区讨论 