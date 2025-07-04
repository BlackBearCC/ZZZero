# 批量日程生成器使用说明

## 概述

批量日程生成器是一个本地命令行工具，可以自动生成多个批次的日程安排，每个批次都有随机配置的天数、角色和地点，生成的结果保存为CSV格式，支持增量更新。

## 功能特点

- 🚀 **本地启动**：直接运行main.py，无需前端界面
- 📅 **批次生成**：从指定日期开始，按批次顺序生成日程
- 🎲 **随机配置**：每批次随机7-30天，3-9个角色，3-9个地点
- 🔗 **连续性保证**：下一批次会使用上一批次的总结避免断档
- 📊 **CSV输出**：每批次完成后CSV增量更新
- 📋 **详细记录**：同时保存JSON格式的详细数据

## 快速开始

### 基础用法

```bash
# 使用默认配置（从2025-07-02开始，生成10个批次）
python batch_schedule_generator.py

# 自定义开始日期和批次数量
python batch_schedule_generator.py --start-date 2025-07-02 --batch-count 20
```

### 参数说明

- `--start-date`: 开始日期，格式为YYYY-MM-DD，默认2025-07-02
- `--batch-count`: 批次数量，默认10个批次

## 随机配置规则

每个批次的配置都是随机生成的：

### 时间配置
- **天数范围**: 7-30天随机
- **开始日期**: 上一批次结束日期的下一天
- **时间段**: 固定5个时间段（夜间、上午、中午、下午、晚上）

### 角色配置
- **数量**: 3-9个角色随机选择
- **来源**: 从`config/yunhub_characters.json`中随机选择
- **排除**: 自动排除主角方知衡（主角单独处理）

### 地点配置
- **数量**: 3-9个地点随机选择
- **来源**: 从`config/yunhub_locations.json`中随机选择
- **覆盖**: 尽量涵盖不同区域的地点

### 其他配置
- **角色分布**: balanced（平衡分布）
- **剧情整合**: moderate（中等整合度）
- **节假日**: 自动包含节假日信息
- **地点多样性**: 启用
- **情感多样性**: 启用

## 输出文件

### 目录结构
```
workspace/batch_schedule_output/
├── batch_schedules_20250702.csv          # 主要的CSV汇总文件
├── batch_001_2025-07-02.json            # 批次1的详细JSON数据
├── batch_002_2025-07-15.json            # 批次2的详细JSON数据
├── ...                                   # 其他批次的JSON文件
└── batch_summary_20250125_143022.txt    # 最终总结报告
```

### CSV文件格式

| 列名 | 说明 |
|------|------|
| 批次编号 | 批次的序号（1, 2, 3...） |
| 日程ID | 数据库中的唯一标识符 |
| 开始日期 | 批次开始日期 |
| 结束日期 | 批次结束日期 |
| 总天数 | 该批次包含的天数 |
| 参与角色 | 该批次涉及的角色列表 |
| 活动地点 | 该批次涉及的地点列表 |
| 周期计划 | 主角对该时期的整体计划 |
| 关键事件 | 该批次的主要事件摘要 |
| 情感发展 | 情感关系的发展情况 |
| 遗留问题 | 传递给下一批次的信息 |

## 连续性机制

为了确保各批次之间的故事连续性：

1. **历史记录**: 每个批次完成后，关键信息被记录到历史中
2. **总结传递**: 下一批次生成时会包含上一批次的总结信息
3. **自然衔接**: LLM会根据历史信息确保故事的自然连接
4. **避免断档**: 角色关系、事件影响等会延续到下一批次

## 日志和调试

### 日志文件
- **控制台输出**: 实时显示进度和状态
- **日志文件**: `batch_schedule_generator.log` 记录详细日志

### 典型日志信息
```
2025-01-25 14:30:22 - INFO - 批量日程生成器初始化完成
2025-01-25 14:30:25 - INFO - 开始生成第 1 批次日程...
2025-01-25 14:30:25 - INFO - 批次 1 配置:
2025-01-25 14:30:25 - INFO -   日期范围: 2025-07-02 - 2025-07-15 (14天)
2025-01-25 14:30:25 - INFO -   角色数量: 5
2025-01-25 14:30:25 - INFO -   地点数量: 7
```

## 故障排除

### 常见问题

1. **LLM初始化失败**
   - 检查环境变量`DOUBAO_API_KEY`是否正确设置
   - 确认网络连接正常

2. **角色/地点数据加载失败**
   - 检查`config/yunhub_characters.json`文件是否存在
   - 检查`config/yunhub_locations.json`文件是否存在

3. **数据库保存失败**
   - 检查`workspace/databases/`目录权限
   - 确认SQLite数据库文件可写

4. **CSV写入失败**
   - 检查`workspace/batch_schedule_output/`目录权限
   - 确认磁盘空间充足

### 中断和恢复

- **用户中断**: 使用Ctrl+C可以安全中断程序
- **自动恢复**: 目前不支持自动恢复，需要重新运行
- **部分结果**: 已完成的批次数据会保留在CSV文件中

## 性能说明

### 预期时间
- **单批次**: 约1-3分钟（取决于天数和复杂度）
- **10批次**: 约15-30分钟
- **API限制**: 批次间有2秒延迟避免API限流

### 资源消耗
- **内存**: 约100-500MB
- **存储**: 每批次约1-5MB（JSON文件）
- **网络**: 取决于LLM API调用

## 示例运行

```bash
# 启动生成器
python batch_schedule_generator.py --start-date 2025-07-02 --batch-count 5

# 输出示例
🚀 批量日程生成器启动
📅 开始日期: 2025-07-02
🔢 批次数量: 5
📁 输出目录: workspace/batch_schedule_output/

==================================================
正在处理第 1/5 批次
==================================================
批次 1 配置:
  日期范围: 2025-07-02 - 2025-07-15 (14天)
  角色数量: 5
  地点数量: 7
  选择角色: 青雀, 丹恒, 三月七, 瓦尔特, 希儿
  选择地点: 星际和平公司, 中央广场, 歌剧院, 咖啡厅, 图书馆, 天文台, 研究所

[日程生成] 正在分析日期范围、角色信息和配置参数，准备生成详细日程...
[数据库保存] 正在将生成的日程数据保存到数据库...
[数据库保存] 日程数据保存成功！日程ID：SCHEDULE_20250125_143045

批次 1 完成，下次开始日期: 2025-07-16
✅ 批量生成完成!
📊 查看结果: workspace/batch_schedule_output/batch_schedules_20250702.csv
```

## 注意事项

1. **运行环境**: 确保Python环境包含所有必需的依赖
2. **API配额**: 注意LLM API的使用配额限制
3. **存储空间**: 确保有足够的磁盘空间存储结果
4. **运行时间**: 大批次数量需要较长时间，建议分批运行
5. **数据备份**: 重要数据建议及时备份 