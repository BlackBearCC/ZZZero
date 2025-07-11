# CSV处理工具

通用的CSV文件处理工具，支持删除指定字段、检查重复数据、清理关键词等功能。

## 功能特性

- ✅ 删除指定字段
- ✅ 检查字段内容重复并生成报告
- ✅ 清理关键词字段的重复项
- ✅ 支持批量处理
- ✅ 自动生成处理报告
- ✅ 支持多种编码格式（UTF-8, GBK）
- ✅ 详细的日志记录

## 使用方法

### 命令行使用

#### 基本使用
```bash
# 删除"重要程度"字段
python scripts/csv_processor.py config/fangzhiheng_profile_with_key.csv -r 重要程度

# 指定输出文件
python scripts/csv_processor.py config/fangzhiheng_profile_with_key.csv -o config/fangzhiheng_profile_clean.csv -r 重要程度

# 检查所有字段的重复
python scripts/csv_processor.py config/fangzhiheng_profile_with_key.csv -d

# 检查特定字段的重复
python scripts/csv_processor.py config/fangzhiheng_profile_with_key.csv -d 关键词 类型

# 清理关键词重复并删除字段
python scripts/csv_processor.py config/fangzhiheng_profile_with_key.csv -r 重要程度 -c

# 批量处理多个文件
python scripts/csv_processor.py "config/*.csv" -b -r 重要程度
```

#### 参数说明
- `input_file`: 输入CSV文件路径（必需）
- `-o, --output`: 输出文件路径（可选，默认为原文件名_processed.csv）
- `-r, --remove-columns`: 要删除的字段名称（可指定多个）
- `-d, --check-duplicates`: 检查重复的字段名称（不指定则检查所有字段）
- `-c, --clean-keywords`: 清理关键词字段的重复项
- `--keyword-column`: 关键词字段名称（默认：关键词）
- `--keyword-separator`: 关键词分隔符（默认：|）
- `-b, --batch`: 批量处理模式（输入文件支持通配符）

### Python脚本使用

```python
from scripts.csv_processor import CSVProcessor

# 创建处理器实例
processor = CSVProcessor()

# 处理单个文件
result = processor.process_file(
    input_file="config/fangzhiheng_profile_with_key.csv",
    output_file="config/fangzhiheng_profile_clean.csv",
    remove_columns=["重要程度"],
    clean_keyword_duplicates=True
)

# 批量处理
results = processor.batch_process(
    input_pattern="config/*.csv",
    remove_columns=["重要程度"],
    clean_keyword_duplicates=True
)
```

## 处理示例

### 针对方知衡配置文件的处理

```bash
# 删除"重要程度"字段，清理关键词重复，检查所有字段重复
python scripts/csv_processor.py config/fangzhiheng_profile_with_key.csv \
    -o config/fangzhiheng_profile_clean.csv \
    -r 重要程度 \
    -c \
    -d
```

处理后将生成：
- `config/fangzhiheng_profile_clean.csv` - 处理后的CSV文件
- `config/fangzhiheng_profile_clean_report.txt` - 详细处理报告
- `csv_processor.log` - 处理日志

## 输出文件

### 处理后的CSV文件
删除指定字段，清理重复关键词后的干净数据文件。

### 处理报告
包含以下信息：
- 原始文件和处理后文件的基本信息
- 删除的字段列表
- 重复数据分析报告
- 处理统计信息

### 日志文件
详细的处理过程日志，包括：
- 文件加载信息
- 字段删除操作
- 重复数据检测结果
- 关键词清理统计
- 错误和警告信息

## 依赖要求

```
pandas>=1.3.0
```

安装依赖：
```bash
pip install pandas
```

## 注意事项

1. **编码支持**: 工具会自动尝试UTF-8和GBK编码
2. **备份**: 建议在处理重要文件前先备份
3. **内存使用**: 大文件处理时注意内存使用情况
4. **字段名**: 字段名需要完全匹配（区分大小写）
5. **关键词分隔符**: 默认使用`|`分隔，可通过参数修改

## 错误处理

- 文件不存在或无法读取时会报错退出
- 指定的删除字段不存在时会给出警告但继续处理
- 编码错误时会自动尝试其他编码格式
- 所有错误和警告都会记录在日志文件中