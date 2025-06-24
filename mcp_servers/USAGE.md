# 角色扮演数据生成服务使用指南

## 🚀 快速开始

### 1. 本地测试模式
```bash
cd mcp_servers
python roleplay_data_server.py --test
```

这将启动本地测试模式，自动演示完整的日程生成流程：
- 自动配置知识库（加载 roleplay_data_README.md）
- 生成日程计划框架
- 生成详细5阶段日程
- 展示角色插件的使用效果

### 2. MCP服务器模式
```bash
cd mcp_servers
python roleplay_data_server.py
```

启动标准的MCP服务器，可以通过MCP协议与其他应用集成。

## 🎭 角色信息集成

### 自动功能
服务启动时会自动：
1. **配置知识库**：将 `roleplay_data_README.md` 加载为知识库
2. **启用向量搜索**：支持基于关键词的智能搜索
3. **集成MCP角色信息服务**：支持通过MCP协议访问角色资料和知识库

### 增强效果
- **角色资料**：通过MCP角色信息服务获取角色设定
- **知识库搜索**：根据 `requirements` 提取关键词，搜索相关知识并注入

## 📋 生成流程

### 第一步：日程计划框架
```python
# 调用 generate_schedule_plan
result = await generator.generate_schedule_plan(
    character_description="角色设定...",
    requirements="需求描述..."
)
```

**MCP服务增强**：
- 如果配置了角色信息服务 → 自动补充角色信息
- 知识库搜索 → 搜索相关知识并添加到需求中

### 第二步：详细5阶段日程
```python
# 调用 generate_detailed_schedule
result = await generator.generate_detailed_schedule(
    character_description="角色设定...",
    plan_framework="第一步的计划框架",
    requirements="补充需求..."
)
```

**MCP服务增强**：
- 再次应用角色信息服务增强
- 生成包含地点、天气、情绪的详细日程

## 🔧 环境配置

### 必需的环境变量
```bash
# LLM提供商配置
LLM_PROVIDER=doubao                    # 或 openai
ARK_API_KEY=your_api_key              # 豆包API密钥
# 或
OPENAI_API_KEY=your_api_key           # OpenAI API密钥
```

### 可选的环境变量
```bash
LLM_MODEL_NAME=ep-20250221154410-vh78x  # 指定模型
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3  # API基础URL
```

## 📊 返回数据格式

### 日程计划框架结果
```json
{
  "generation_id": "plan_1703123456",
  "type": "schedule_plan",
  "success": true,
  "content": "生成的计划框架内容...",
  "character_description": "原始角色描述",
  "enhanced_character_description": "MCP服务增强后的角色描述",
  "requirements": "原始需求",
  "enhanced_requirements": "MCP服务增强后的需求",
  "role_service_used": true,
  "generation_time": 2.5,
  "generated_at": "2023-12-21T10:30:00",
  "completed_at": "2023-12-21T10:30:02"
}
```

### 详细日程结果
```json
{
  "generation_id": "schedule_1703123456",
  "type": "detailed_schedule",
  "success": true,
  "content": "生成的详细日程内容...",
  "phases_data": {
    "morning": {
      "name": "上午",
      "time_range": "06:00-11:00",
      "activities": [
        {
          "activity_name": "晨间阅读",
          "details": "在咖啡店阅读天文学相关书籍...",
          "location": "咖啡厅",
          "weather": "阳光明媚",
          "emotion": "平静"
        }
      ]
    }
    // ... 其他时间段
  },
  "role_service_used": true,
  "generation_time": 3.2
}
```

## 🎯 使用场景

### 1. 角色扮演游戏
- 为NPC生成详细的日程安排
- 基于角色背景创建真实的生活节奏

### 2. 故事创作
- 为小说角色设计日常生活
- 确保角色行为符合设定

### 3. 时间管理
- 生成个性化的日程规划
- 结合个人特点的时间安排

## 🔍 调试和日志

### 启用详细日志
```bash
export PYTHONPATH=.
python -m logging --level=DEBUG mcp_servers/roleplay_data_server.py --test
```

### 关键日志信息
- `✅ 已从角色信息服务获取角色信息`
- `✅ 已从知识库服务获取 X 条相关知识`
- `✅ 已自动配置角色扮演数据生成服务知识库`

## ⚠️ 注意事项

1. **首次运行**：知识库初始化需要时间，请耐心等待
2. **API配置**：确保LLM API密钥正确配置
3. **网络连接**：需要稳定的网络连接访问LLM服务
4. **资源占用**：知识库向量化会占用一定的内存和存储空间

## 🛠️ 故障排除

### 常见问题

**Q: 知识库初始化失败**
```bash
# 检查文件是否存在
ls -la mcp_servers/roleplay_data_README.md

# 检查权限
chmod 644 mcp_servers/roleplay_data_README.md
```

**Q: LLM调用失败**
```bash
# 检查环境变量
echo $ARK_API_KEY
echo $LLM_PROVIDER

# 测试网络连接
curl -I https://ark.cn-beijing.volces.com
```

**Q: 角色信息服务未生效**
- 确保MCP角色信息服务器正常运行
- 检查角色信息数据文件是否存在
- 查看日志中是否有角色信息服务相关的错误信息

## 📞 支持

如果遇到问题，请查看：
1. 控制台日志输出
2. MCP服务器连接状态
3. 环境变量配置是否正确 