# 角色扮演数据生成服务 - 简化版

## 🎯 功能描述
为方知衡（天文教授）生成详细的日程安排，基于年度CSV规划文件，输出每天5个时间段的具体活动安排。

## 🛠️ MCP工具

### `generate_schedule`
生成角色扮演日程安排，包含每天5个时间段（上午/中午/下午/晚上/夜间）的具体活动。

**参数：**
- `max_days` (integer): 生成的天数，范围1-557天，默认7天

**返回：**
- 成功时返回生成结果和CSV文件路径
- 包含每日概要、活动安排等详细信息

**输出CSV格式：**
```csv
天数,日期,星期,时间段,活动安排,当日概要
1,2025-06-24,星期二,上午,"晨跑; 阅读期刊; 撰写论文","完成论文初稿..."
```

## 🚀 ReactAgent调用示例

```python
# 生成7天日程
result = await call_tool("generate_schedule", {"max_days": 7})

# 生成30天日程  
result = await call_tool("generate_schedule", {"max_days": 30})

# 生成3天日程（演示）
result = await call_tool("generate_schedule", {"max_days": 3})
```

## 📊 特点
- ✅ 只需一个参数：`max_days`
- ✅ 角色设定已内置（方知衡天文教授）
- ✅ CSV文件路径已固定
- ✅ 渐进式概要更新（每天概要供下一天参考）
- ✅ 两步生成流程（中等安排→具体安排）
- ✅ 输出标准CSV格式

## 📁 输出位置
- 生成的CSV文件保存在：`workspace/simple_schedule_output/`
- 文件命名格式：`schedule_{天数}days_{时间戳}.csv`

## 🔧 技术架构
1. **第一步**：基于年度事件生成中等粒度的日期安排框架
2. **第二步**：逐天生成5时间段的具体活动安排
3. **概要传递**：每天生成的概要自动传递给下一天使用

## ⚙️ 环境配置

### LLM配置（必需）
```bash
export ARK_API_KEY="your-api-key"                    # 豆包API密钥
export LLM_PROVIDER="doubao"                         # 默认豆包
export LLM_MODEL_NAME="ep-20250221154410-vh78x"     # 默认模型
export DOUBAO_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
```

## 📊 输出示例

### 成功返回格式
```json
{
  "generation_id": "simple_1234567890",
  "success": true,
  "max_days": 7,
  "csv_events_count": 0,
  "medium_arrangements_count": 2,
  "daily_results": [
    {
      "day": 1,
      "date": "2025-06-24",
      "weekday": "星期二",
      "success": true,
      "daily_summary": "完成论文初稿，指导研究生...",
      "morning": ["晨跑", "阅读期刊", "撰写论文"],
      "noon": ["午餐", "整理笔记"],
      "afternoon": ["研究生指导", "数据分析"],
      "evening": ["天文台观测", "论文修改"],
      "night": ["阅读专著"]
    }
  ],
  "output_csv_file": "workspace/simple_schedule_output/schedule_7days_20250624_175333.csv",
  "generation_time": 35.2
}
```

适合ReactAgent自动化调用，参数简单，输出格式标准化。 