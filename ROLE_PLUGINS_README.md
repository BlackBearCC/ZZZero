# 🎭 角色插件系统使用指南

## 概述

角色插件系统是ZZZero AI Agent框架的全局配置功能，提供两种类型的角色信息增强：

1. **角色资料插件** - 直接填入prompt的角色描述信息
2. **角色知识库插件** - 通过向量搜索提供动态知识增强

## 🏗️ 系统架构

```
WebUI 配置面板 → 角色插件管理器 → MCP工具管理器 → ReactAgent
                     ↓
               角色资料插件 + 角色知识库插件
                     ↓
               自动注入到有权限的MCP服务
```

## 🚀 主要特性

### 1. 全局配置
- 角色信息作为全局配置，所有MCP服务都可以接入
- 通过Web界面统一管理和配置
- 配置自动持久化，重启应用后保持有效

### 2. 权限控制
- 基于插件权限系统，只有授权的MCP服务才能使用
- 目前只有角色扮演数据生成服务（`roleplay`）有使用权限
- Agent根据权限决定是否开放使用

### 3. 智能注入
- **有权限且配置了插件**：工具调用时自动注入角色信息，无需手动输入
- **无权限或未配置**：保持原有行为，需要手动输入参数

## 📝 角色资料插件

### 配置内容
- **角色名称**：角色的名字或代号
- **角色资料内容**：详细的角色描述信息
- **角色标签**：便于分类的标签（可选）

### 注入方式
角色资料直接注入到工具的`character_description`参数中：
- 如果工具调用时没有提供角色描述，则直接使用插件中的角色资料
- 如果已有角色描述，则在前面添加插件角色资料作为补充

### 配置示例
```python
plugin_manager.configure_profile(
    name="艾莉丝·薇拉诺瓦",
    content="25岁独立艺术家和咖啡店店主，温柔创意...",
    tags=["艺术家", "咖啡店主", "温柔", "创意"],
    enabled=True
)
```

## 📚 角色知识库插件

### 配置内容
- **知识库名称**：知识库的显示名称
- **向量库路径**：向量数据库的存储路径
- **知识库描述**：描述知识库的内容和用途
- **搜索结果数量限制**：每次搜索返回的最大结果数（默认3条）

### 工作原理
1. 从工具调用的`requirements`参数中提取关键词
2. 使用关键词搜索向量知识库
3. 将搜索结果注入到`requirements`参数中

### 配置示例
```python
plugin_manager.configure_knowledge_base(
    name="艾莉丝专属知识库",
    path="./workspace/vectordb/alice_knowledge",
    description="包含艺术技巧、咖啡制作、园艺知识",
    search_limit=3,
    enabled=True
)
```

## 🌐 Web界面使用

### 1. 角色资料配置
在"🎭 角色插件配置"面板中：
1. 勾选"启用角色资料插件"
2. 填写角色名称和详细资料
3. 可选择添加标签（用逗号分隔）
4. 点击"保存角色插件配置"

### 2. 角色知识库配置
1. 勾选"启用角色知识库插件"
2. 填写知识库名称和向量库路径
3. 添加知识库描述
4. 设置搜索结果数量限制
5. 点击"保存角色插件配置"

### 3. 状态监控
- 实时显示插件的启用和可用状态
- 显示详细的配置信息
- 支持一键清空配置

## 🔧 开发者接口

### 获取角色插件管理器
```python
from core.plugins import get_role_plugin_manager

plugin_manager = get_role_plugin_manager()
```

### 检查插件权限
```python
# 在MCP工具管理器中
has_permission = tool_manager.has_role_plugin_permission("roleplay")
```

### 获取角色上下文
```python
# 获取综合的角色上下文信息
keywords = ["绘画", "咖啡", "创作"]
context = await plugin_manager.get_role_context(keywords)

# context包含：
# - "profile": 角色资料内容
# - "knowledge": 知识库搜索结果列表
```

### 自动注入角色信息
```python
# 在工具调用时自动增强参数
enhanced_args = await tool_manager.inject_role_context_to_arguments(
    server_id="roleplay",
    tool_name="generate_schedule_plan", 
    arguments=original_args
)
```

## 📊 配置文件格式

角色插件配置保存在`workspace/role_plugins_config.json`：

```json
{
  "role_profile": {
    "enabled": true,
    "name": "艾莉丝·薇拉诺瓦",
    "content": "角色详细描述...",
    "tags": ["艺术家", "咖啡店主"],
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:00:00"
  },
  "role_knowledge_base": {
    "enabled": true,
    "name": "艾莉丝专属知识库",
    "path": "./workspace/vectordb/alice_knowledge",
    "description": "专业知识库",
    "search_limit": 3,
    "created_at": "2024-01-01T12:00:00"
  }
}
```

## 🧪 测试和演示

运行测试脚本：
```bash
python test_role_plugins.py
```

测试内容包括：
- 角色资料和知识库配置
- 插件状态检查
- 角色上下文获取
- MCP工具集成测试
- 配置持久化验证

## 💡 使用场景

### 1. 角色扮演对话
- 配置角色资料，让AI基于特定角色身份进行对话
- 知识库提供角色相关的专业知识支持

### 2. 内容生成
- 自动生成符合角色特点的日程安排
- 基于角色背景创作故事或对话

### 3. 个性化助手
- 打造具有特定专业背景的AI助手
- 结合角色知识库提供专业咨询

## ⚠️ 注意事项

1. **权限限制**：目前只有角色扮演服务器支持角色插件
2. **知识库路径**：确保向量库路径正确且可访问
3. **配置验证**：启用插件前确保必要字段已填写
4. **性能考虑**：知识库搜索会增加响应时间
5. **数据安全**：角色资料可能包含敏感信息，注意保护

## 🔮 未来扩展

- 支持更多MCP服务器使用角色插件
- 集成真实的向量数据库（ChromaDB、Faiss等）
- 支持多角色配置和切换
- 角色资料的版本管理
- 更智能的关键词提取算法
- 角色对话历史记录和学习功能 