# 角色信息管理增强功能总结

## 🎯 解决的问题

1. **文件类型限制**：原来只支持 `.txt` 文件，现在支持 **CSV 文件上传**
2. **缺乏自动向量化**：上传文件后现在会**自动切割并存入向量数据库**
3. **预览逻辑错误**：预览功能现在**基于已有数据**，不依赖输入内容
4. **重复文件处理**：新增**文件内容查重机制**，避免重复处理相同内容
5. **分类名称混乱**：现在使用**向量数据库集合名称**作为统一分类

## ✨ 新增功能

### 1. CSV 文件支持与优化切割
- **角色信息**、**角色知识**、**世界书** 现在都支持 `.txt` 和 `.csv` 文件
- **CSV 按行切割**：每行作为一个独立的知识片段存储
- **TXT 智能切割**：按段落和句子进行智能分割，控制长度
- 支持多种编码格式：UTF-8、GBK、GB2312

### 2. 文件内容查重机制 🆕
- **MD5 哈希检测**：基于文件内容计算唯一标识
- **重复内容跳过**：相同内容的文件自动跳过处理
- **处理记录存储**：保存已处理文件的信息到 `workspace/file_content_hashes.json`
- **智能提示**：明确显示哪些文件被跳过、哪些成功处理

### 3. 统一集合名称分类 🆕
- **知识库**：统一使用 `knowledge_collection` 作为分类
- **世界书**：统一使用 `worldbook_collection` 作为分类
- **向量数据库映射**：直接对应 ChromaDB 的集合名称
- **元数据丰富**：保存来源文件、切割类型、索引信息

### 4. 智能预览功能
- **基于角色名称**查询已有数据，无需输入内容
- 显示完整统计信息和美化的显示界面
- 支持滚动浏览长内容

## 🛠️ 技术实现

### 核心改进

1. **查重算法**
```python
def _calculate_content_hash(self, content: str) -> str:
    """计算文件内容的MD5哈希"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def _is_content_already_processed(self, content: str, file_name: str) -> bool:
    """检查文件内容是否已经被处理过"""
    content_hash = self._calculate_content_hash(content)
    return content_hash in self.processed_files
```

2. **优化切割策略**
```python
if file_ext == 'csv':
    # CSV文件按行切割，每行一个片段
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if len(line.strip()) >= 10:  # 跳过空行或太短的行
            chunks.append({
                "content": line.strip(),
                "metadata": {
                    "source": source_file,
                    "chunk_index": i,
                    "chunk_type": "csv_row"
                }
            })
else:
    # TXT文件智能切割（段落+句子）
    paragraphs = content.split('\n\n')
    # ... 智能分割逻辑
```

3. **集合名称统一**
```python
# 知识库存储
"keyword": "knowledge_collection"  # 使用集合名称

# 世界书存储  
"concept": "worldbook_collection"  # 使用集合名称
"category": "worldbook_collection"
```

### 修改的文件

1. **`src/web/handlers/event_handlers.py`** (重大更新)
   - 新增查重机制相关方法
   - 优化 `_auto_vectorize_content()` 切割策略
   - 修改所有文件上传处理方法
   - 统一使用集合名称作为分类

2. **`src/web/components/config_panel.py`**
   - 添加 CSV 文件类型支持

3. **`src/web/app.py`**
   - 修复预览按钮事件绑定

## 📋 使用指南

### 1. 文件查重机制
- **自动检测**：上传文件时自动检查内容是否重复
- **状态提示**：明确显示 "✅ 成功处理" 或 "⚠️ 跳过重复"
- **记录查看**：检查 `workspace/file_content_hashes.json` 了解处理历史

### 2. CSV 优化处理
```csv
角色特征,温和善良的性格
技能,精通火焰魔法  
背景,出生在魔法学院
```
每行会作为独立片段存储，便于精确检索。

### 3. 向量数据库查询
- **知识检索**：在 `knowledge_collection` 集合中搜索
- **世界书检索**：在 `worldbook_collection` 集合中搜索
- **统一管理**：所有同类数据在同一集合中，便于管理

## 🔍 测试验证

### 新增测试场景

1. **查重功能测试**
   - 上传相同内容的文件，验证跳过处理
   - 检查 `file_content_hashes.json` 记录正确性
   - 验证状态提示信息

2. **CSV 按行切割测试**
   - 上传多行 CSV 文件
   - 验证每行独立存储
   - 确认元数据正确记录

3. **集合名称验证**
   - 检查向量数据库中的分类名称
   - 验证查询功能正常工作

## 🚀 性能优化

- **查重效率**：O(1) 哈希查找，快速检测重复内容
- **存储优化**：避免重复存储相同内容，节省空间
- **切割精度**：CSV 按行切割，TXT 智能分段，提高检索精度
- **元数据丰富**：详细的来源和类型信息，便于追溯

## 📁 文件结构

```
workspace/
├── file_content_hashes.json    # 文件内容哈希记录 🆕
├── vectordb/                   # 向量数据库
│   ├── knowledge_collection/   # 知识库集合
│   └── worldbook_collection/   # 世界书集合
└── output/                     # 其他输出文件
```

## 🔧 配置说明

### 查重记录格式
```json
{
  "abc123def456": {
    "original_file": "character_info.csv",
    "category": "角色信息", 
    "processed_time": "2025-01-27 14:30:15",
    "content_length": 1024
  }
}
```

### 元数据结构
```python
# CSV 行元数据
{
    "source": "file.csv",
    "chunk_index": 0,
    "chunk_type": "csv_row"
}

# TXT 段落元数据  
{
    "source": "file.txt",
    "paragraph_index": 1,
    "sentence_range": "0-5",
    "chunk_type": "paragraph_split"
}
```

## 📈 后续增强建议

1. **批量去重**：支持批量清理重复数据
2. **版本控制**：为文件内容添加版本管理
3. **增量更新**：支持文件内容的增量更新
4. **搜索优化**：基于元数据的高级搜索功能
5. **可视化管理**：提供向量数据库的可视化管理界面

---

**更新时间**：2025年1月27日  
**版本**：v2.0  
**状态**：✅ 已完成优化并测试

### 🆕 v2.0 新增特性
- ✅ 文件内容查重机制
- ✅ CSV 按行精确切割  
- ✅ 统一集合名称分类
- ✅ 丰富的元数据支持
- ✅ 智能状态提示 