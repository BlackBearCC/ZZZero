# ReactAgent系统级批处理功能使用指南

## 概述

ReactAgent现在支持系统级批处理功能，允许用户通过前端配置开关和CSV文档上传，实现大规模的批量任务处理。系统会自动解析CSV数据，使用LLM生成批处理指令，然后并发执行多个ReactAgent实例来处理每行数据。

## 核心架构

```
前端配置栏 → 批量执行开关 → CSV文档上传 → 用户消息 → LLM生成批处理指令 → 并发ReactAgent执行
```

## 主要组件

### 1. BatchProcessor（系统级批处理器）
- **位置**: `src/core/batch_processor.py`
- **功能**: 主控制器，管理整个批处理流程
- **核心方法**:
  - `configure_batch_mode()`: 配置批处理模式
  - `process_batch_request()`: 处理批处理请求
  - `get_batch_status()`: 获取批处理状态

### 2. CSVDataManager（CSV数据管理器）
- **功能**: 验证和解析CSV文件
- **支持格式**: UTF-8编码，必须包含列头
- **返回数据**: 包含行索引的字典列表

### 3. BatchInstructionGenerator（批处理指令生成器）
- **功能**: 使用LLM分析用户意图，生成批处理指令
- **输入**: 用户消息 + CSV结构信息
- **输出**: BatchInstruction对象

### 4. ReactAgentTaskExecutor（任务执行器）
- **功能**: 模拟ReactAgent处理单个任务
- **支持**: 自动识别任务类型，调用相应MCP工具
- **并发控制**: 支持可配置的并发数量

## 使用流程

### 第一步：准备CSV文件

创建符合格式的CSV文件，示例：

```csv
character_name,description,duration_days,special_requirements
张三,古代书生性格温和喜欢读书写字,7,需要包含科举考试准备
李四,现代程序员工作忙碌热爱技术,5,工作日程要包含编程项目
王五,中世纪骑士勇敢正直保护领土,10,要有训练和巡逻任务
```

**CSV要求**：
- 必须使用UTF-8编码
- 必须包含列头行
- 至少包含一列数据
- 支持任意列名和列数

### 第二步：配置批处理模式

```python
# 在ReactAgent中集成
batch_processor = BatchProcessor(llm_caller=llm_caller, mcp_tool_manager=mcp_manager)

# 启用批处理模式
config_result = batch_processor.configure_batch_mode(
    enabled=True,
    csv_file_path="path/to/your/file.csv",
    batch_size=20,          # 每批处理行数
    concurrent_tasks=5      # 并发任务数
)
```

### 第三步：发送用户消息

用户发送任何消息，系统会自动检测批处理模式：

```python
user_message = "帮我为这些角色生成详细的日程安排"

# 系统检测到批处理模式开启 + CSV已加载
if batch_processor.is_batch_mode_enabled():
    result = await batch_processor.process_batch_request(user_message)
```

### 第四步：LLM生成批处理指令

系统自动调用LLM分析用户意图和CSV结构：

```json
{
    "task_type": "schedule_generation",
    "batch_description": "为每个角色生成个性化的日程安排",
    "per_row_template": "为角色{character_name}（{description}）生成{duration_days}天的日程，特殊要求：{special_requirements}",
    "expected_output": "详细的角色日程安排"
}
```

### 第五步：并发执行任务

系统自动：
1. 将CSV数据分批（每批20行）
2. 为每行生成具体任务提示词
3. 并发创建ReactAgent实例执行任务
4. 汇总所有结果

## 配置参数

### BatchConfig配置项

```python
@dataclass
class BatchConfig:
    enabled: bool = False           # 批处理开关
    csv_file_path: str = None      # CSV文件路径
    batch_size: int = 20           # 每批处理行数
    concurrent_tasks: int = 5      # 并发任务数
    max_rows: int = 1000          # 最大处理行数限制
```

### 性能调优建议

- **batch_size**: 根据内存和处理速度调整，推荐10-50
- **concurrent_tasks**: 根据LLM API限制调整，推荐3-10
- **max_rows**: 防止超大文件处理，推荐500-2000

## 返回结果格式

```python
{
    "success": True,
    "batch_instruction": {
        "task_type": "schedule_generation",
        "description": "为每个角色生成个性化的日程安排",
        "template": "为角色{character_name}..."
    },
    "execution_summary": {
        "total_tasks": 100,
        "successful_tasks": 95,
        "failed_tasks": 5,
        "success_rate": "95.0%",
        "total_execution_time": "45.32秒",
        "average_task_time": "0.45秒"
    },
    "detailed_results": [
        {
            "row_index": 1,
            "success": True,
            "task_prompt": "为角色张三...",
            "result": "✅ 日程生成成功:\n详细内容...",
            "execution_time": 0.8,
            "row_data": {...}
        }
    ]
}
```

## 支持的任务类型

### 1. 日程生成任务
- **关键词**: "日程", "schedule", "计划", "安排"
- **自动调用**: roleplay_generate_schedule_plan工具
- **适用场景**: 角色日程规划、活动安排

### 2. 通用任务
- **扩展点**: 可在ReactAgentTaskExecutor中添加新的任务类型
- **识别机制**: 基于关键词或CSV列名自动识别

## 错误处理

### 常见错误类型
1. **CSV格式错误**: 文件不存在、编码错误、格式不正确
2. **LLM调用失败**: API限制、网络问题、提示词错误
3. **任务执行失败**: MCP工具不可用、参数错误

### 容错机制
- **单任务失败不影响整体**: 继续处理其他任务
- **自动重试**: 暂时性错误会自动重试
- **详细错误日志**: 记录每个任务的具体错误信息

## 扩展指南

### 添加新的任务类型

1. 在`ReactAgentTaskExecutor`中添加处理方法：

```python
async def _handle_new_task_type(self, task_prompt: str, row_data: Dict[str, Any]) -> str:
    # 调用相应的MCP工具
    result = await self.mcp_tool_manager.call_tool("new_tool_name", {...})
    return result
```

2. 在`_simulate_react_process`中添加识别逻辑：

```python
if any(keyword in task_prompt.lower() for keyword in ['新任务关键词']):
    return await self._handle_new_task_type(task_prompt, row_data)
```

### 集成到ReactAgent主流程

```python
class ReactAgent:
    def __init__(self):
        self.batch_processor = BatchProcessor(
            llm_caller=self.llm_caller,
            mcp_tool_manager=self.mcp_tool_manager
        )
    
    async def process_user_message(self, message: str):
        # 检查批处理模式
        if self.batch_processor.is_batch_mode_enabled():
            return await self.batch_processor.process_batch_request(message)
        else:
            # 正常单次处理
            return await self.process_single_message(message)
```

## 测试示例

运行测试脚本验证功能：

```bash
python test_batch_processor.py
```

测试包含：
- CSV文件创建和解析
- 批处理模式配置
- LLM指令生成
- 并发任务执行
- 结果汇总和清理

## 注意事项

1. **资源管理**: 及时清理MCP工具管理器和临时文件
2. **API限制**: 注意LLM API的调用频率限制
3. **内存使用**: 大文件处理时注意内存消耗
4. **错误监控**: 监控失败率，及时调整配置参数
5. **数据安全**: 确保CSV文件中不包含敏感信息

## 总结

系统级批处理功能为ReactAgent提供了强大的批量处理能力，通过简单的前端配置和CSV文件上传，就能实现复杂的批量任务处理。这个功能特别适用于：

- 大规模角色日程生成
- 批量内容创建
- 数据批量分析
- 自动化测试场景

通过合理的配置和扩展，可以满足各种批量处理需求。 