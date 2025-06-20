# 角色扮演数据生成服务 (RolePlay Data Server)

基于MCP协议的AI驱动的角色扮演数据生成服务，专门用于生成各种日程规划和时间管理相关的数据。

## 🌟 核心功能

### 1. 日程计划框架生成
- **功能**: 根据用户需求生成基础的日程规划框架
- **支持类型**: 
  - `basic`: 基础日常规划
  - `work`: 工作日程规划  
  - `study`: 学习计划规划

### 2. 详细5阶段日程生成
- **功能**: 基于计划框架生成详细的分时段日程安排
- **时间阶段**: 
  - 上午（06:00-11:00）
  - 中午（11:00-14:00）
  - 下午（14:00-18:00）
  - 晚上（18:00-23:00）
  - 夜间（23:00-06:00）

## 🔧 工具列表

### `generate_schedule_plan`
生成日程计划框架

**参数:**
- `requirements` (string): 用户的具体要求和需求描述
- `plan_type` (string): 计划类型 ["basic", "work", "study"]

**返回:** 包含计划框架的详细结果

### `generate_detailed_schedule`
生成详细的5阶段日程

**参数:**
- `plan_framework` (string): 计划框架内容
- `requirements` (string): 用户补充要求
- `schedule_type` (string): 日程类型 ["basic", "flexible"]

**返回:** 包含5个时间阶段详细安排的结果

### `get_time_phases`
获取5阶段时间规划信息

**返回:** 5个时间阶段的详细信息

### `get_generation_history`
获取生成历史记录

**参数:**
- `limit` (integer): 返回记录数量限制 (1-50)

### `clear_generation_history`
清空生成历史记录

## 🚀 使用示例

### 1. 生成基础日程计划
```json
{
  "tool": "generate_schedule_plan",
  "arguments": {
    "requirements": "我需要安排明天的工作日程，包括3个会议和项目开发时间",
    "plan_type": "work"
  }
}
```

### 2. 生成详细5阶段日程
```json
{
  "tool": "generate_detailed_schedule",
  "arguments": {
    "plan_framework": "上一步生成的计划框架内容",
    "requirements": "需要在下午安排一个重要的客户演示",
    "schedule_type": "basic"
  }
}
```

### 3. 获取时间阶段信息
```json
{
  "tool": "get_time_phases",
  "arguments": {}
}
```

## ⚙️ 环境配置

### LLM提供商配置
支持多种LLM提供商，通过环境变量灵活配置：

#### 1. 豆包(Doubao) - 默认推荐
```bash
LLM_PROVIDER=doubao
ARK_API_KEY=your_ark_api_key                    # 豆包API密钥
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3  # 可选
LLM_MODEL_NAME=ep-20250221154410-vh78x          # 可选，默认模型
```

#### 2. OpenAI
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1      # 可选
LLM_MODEL_NAME=gpt-3.5-turbo                   # 可选
```

### 通用配置
```bash
LLM_PROVIDER=doubao                             # 默认使用豆包
LLM_MODEL_NAME=your_model_name                  # 覆盖默认模型
```

### 配置优先级
1. **豆包**: ARK_API_KEY > DOUBAO_API_KEY
2. **OpenAI**: OPENAI_API_KEY
3. **自动设置**: 根据LLM_PROVIDER自动选择合适的默认值
4. **兼容性**: 完全兼容项目现有的LLM框架

## 🏗️ 系统架构

```
RolePlayDataServer
├── RolePlayDataGenerator          # 核心生成器
│   ├── generate_schedule_plan()   # 计划框架生成
│   ├── generate_detailed_schedule() # 详细日程生成
│   └── _parse_schedule_phases()   # 阶段解析
├── PromptManager                  # 提示词管理
│   ├── schedule_plan_prompts      # 计划生成提示词
│   └── detailed_schedule_prompts  # 详细日程提示词
├── LLMCaller                      # LLM调用器
│   ├── call_openai_api()         # OpenAI API调用
│   └── call_llm()               # 统一LLM接口
└── TimePhase(Enum)               # 时间阶段定义
```

## 📝 提示词模板

### 计划框架生成提示词类型
1. **basic**: 通用日常规划提示词
2. **work**: 专业工作规划提示词  
3. **study**: 学习计划专用提示词

### 详细日程生成提示词类型
1. **basic**: 标准详细日程生成
2. **flexible**: 灵活可调整日程生成

## 🔒 安全特性

- 自动请求超时控制
- API密钥安全管理
- 错误处理和异常捕获
- 生成历史记录管理

## 📊 返回数据格式

### 成功响应示例
```json
{
  "generation_id": "plan_1703123456",
  "type": "schedule_plan",
  "success": true,
  "content": "生成的日程计划内容...",
  "plan_type": "work",
  "requirements": "用户要求",
  "generation_time": 2.5,
  "generated_at": "2023-12-21T10:30:00",
  "completed_at": "2023-12-21T10:30:02"
}
```

### 错误响应示例
```json
{
  "generation_id": "plan_1703123456",
  "type": "schedule_plan", 
  "success": false,
  "error": "API调用失败: 无效的API密钥",
  "plan_type": "work",
  "requirements": "用户要求",
  "generated_at": "2023-12-21T10:30:00"
}
```

## 🔧 启动服务器

### 独立启动
```bash
cd mcp_servers
python roleplay_data_server.py
```

### 通过MCP工具管理器启动
服务器会自动通过ReactAgent的MCP工具管理器启动和管理。

## 🤝 与ReactAgent集成

该服务已经集成到ReactAgent的MCP工具生态系统中，可以直接在对话中使用：

1. **自动服务发现**: ReactAgent会自动发现并连接该服务
2. **工具调用**: 在对话中可以直接请求生成日程计划
3. **结果展示**: 生成的日程会格式化显示在聊天界面

## 📋 注意事项

1. **API配置**: 确保正确配置OpenAI API密钥
2. **网络连接**: 需要稳定的网络连接访问API服务
3. **生成时间**: 复杂日程生成可能需要较长时间
4. **内容质量**: LLM生成的内容质量取决于提示词和模型能力

## 🔄 版本历史

- **v1.0.0**: 初始版本，支持基础日程规划生成
- 支持5阶段时间管理原则
- 集成多种提示词模板
- 完整的错误处理和历史记录功能 